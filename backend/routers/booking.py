"""Endpoint delle prenotazioni.

La creazione è l'operazione più delicata dell'applicazione: coordina
database, calendario, email e notifiche, e concentra i controlli di
sicurezza sull'identità di chi prenota. Contiene inoltre gli endpoint di
cancellazione self-service e di gestione delle recensioni.
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.ora_prenotata import OraPrenotata
from backend.models.slots import Slot
from backend.models.users import User
from backend.models.package import Package
from backend.models.review import Review
from backend.schemas.booking import BookingCreate, BookingResponse, BookingResponseStudente
from backend.schemas.review import ReviewCreate, ReviewResponse, ReviewPubblica
from backend.services.email_service import invia_conferma_cliente, invia_notifica_admin
from backend.services.timezone_service import utc_to_rome, ora_utc_naive
from backend.services.calendar_service import CalendarioNonRaggiungibile, crea_evento_calendario, elimina_evento_calendario
from backend.services.disponibilita_service import ora_prenotabile
from backend.services.discord_service import invia_alert_sistema, invia_notifica_discord
from backend.services.booking_service import libera_slot_prenotazione, restituisci_credito_pacchetto
from backend.routers.users import get_studente, get_studente_opzionale
from backend.rate_limit import limiter
from typing import List, Optional

MAX_PRENOTAZIONI_ATTIVE = 2

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# Listino deciso dal server: il client non invia mai un prezzo. 20 EUR/ora
# lineare; le sessioni singole sono limitate a 1-2 ore, oltre esistono i
# pacchetti.
TABELLA_PREZZI = {1: 2000, 2: 4000}


@router.post("/", response_model=BookingResponse)
@limiter.limit("5/minute")
def create_booking(
    request: Request,
    booking: BookingCreate,
    db: Session = Depends(get_db),
    studente: Optional[User] = Depends(get_studente_opzionale)
):
    # Il login non è richiesto: i pagamenti non passano dall'applicazione,
    # quindi non serve un account per prenotare.

    # L'orario richiesto. Dal pezzo 4.4 il sito manda l'inizio; le pagine
    # vecchie ancora nella cache dei browser mandano uno slot, da cui si
    # ricava (ponte che sparisce con la tabella slots, nel 4.6).
    slot = slot_secondario = None
    if booking.slot_id is not None:
        slot = db.query(Slot).filter(Slot.id == booking.slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        inizio = slot.start_time
        if booking.duration_hours == 2:
            slot_secondario = db.query(Slot).filter(Slot.start_time == inizio + timedelta(hours=1)).first()
    else:
        inizio = booking.start_time

    # Senza questo controllo una richiesta diretta potrebbe confermare un
    # appuntamento nel passato, generando evento ed email per una sessione
    # impossibile. La verifica sulle ore in vendita più sotto la escluderebbe
    # comunque, ma con un messaggio che non direbbe il motivo.
    if inizio <= ora_utc_naive():
        raise HTTPException(status_code=400, detail="This slot is in the past")

    # Identità del prenotante. `booking.user_id` da solo non è una prova:
    # è un intero sequenziale che chiunque può scrivere in una richiesta
    # diretta, e permetterebbe di creare prenotazioni a nome di terzi,
    # consumando il loro limite di prenotazioni attive e generando eventi
    # ed email non richiesti.
    #
    # Con login, l'identità viene dal token e i campi del corpo sono
    # ignorati. Senza login non esiste un token, quindi l'unica verifica
    # possibile è la corrispondenza fra email dichiarata e utente indicato.
    # Non elimina il rischio, ma alza il costo dell'attacco da "indovina un
    # id" a "conosci già l'email della vittima".
    if studente:
        user = studente
    else:
        # L'email è opzionale nello schema perché lo studente autenticato
        # non la invia, ma su questo ramo è obbligatoria. Senza questo
        # controllo la richiesta finirebbe nel 403 sottostante, che
        # descriverebbe un problema diverso da quello reale.
        if not booking.email:
            raise HTTPException(
                status_code=422,
                detail="email is required when booking without logging in"
            )
        user = db.query(User).filter(User.id == booking.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.email != booking.email:
            raise HTTPException(status_code=403, detail="user_id and email do not match")

    # Redenzione di un pacchetto. Esistenza, proprietà, capienza e durata
    # sono riverificate qui: il prezzo azzerato mostrato dall'interfaccia
    # non è una prova.
    #
    # La proprietà va confrontata con l'id preso dal token, mai con
    # `booking.user_id`. Confrontare due valori entrambi scelti dal
    # chiamante non protegge nulla: sarebbe sufficiente inviare insieme
    # l'id del pacchetto e quello del suo proprietario. Per questo l'uso di
    # un pacchetto richiede il login: senza, non esiste un'identità
    # verificata a cui legarne la proprietà.
    package = None
    if booking.package_id is not None:
        if not studente:
            raise HTTPException(status_code=401, detail="Log in with Discord to use a package")
        package = db.query(Package).filter(Package.id == booking.package_id).first()
        if not package or package.user_id != studente.id:
            raise HTTPException(status_code=404, detail="Package not found")
        if package.sessioni_usate >= package.sessioni_totali:
            raise HTTPException(status_code=400, detail="This package has no sessions left")
        if package.durata_sessione_ore != booking.duration_hours:
            raise HTTPException(
                status_code=400,
                detail=f"This package covers {package.durata_sessione_ore}h sessions, not {booking.duration_hours}h"
            )

    # Limite anti-abuso: senza pagamento anticipato nulla impedirebbe a una
    # sola persona di occupare più slot. Contano solo le prenotazioni
    # confermate con sessione ancora futura.
    prenotazioni_attive = db.query(Booking).filter(
        Booking.user_id == user.id,
        Booking.status == "confirmed",
        Booking.start_time >= ora_utc_naive()
    ).count()
    if prenotazioni_attive >= MAX_PRENOTAZIONI_ATTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"You already have {MAX_PRENOTAZIONI_ATTIVE} active bookings. Cancel or complete a session before booking another one."
        )

    # L'ora dev'essere fra quelle in vendita: la stessa domanda dell'elenco
    # pubblico (GET /disponibilita/), ripetuta qui anche se il sito propone
    # solo orari validi, perché l'interfaccia è scavalcabile con una
    # richiesta diretta. Vale per tutti i controlli di questa funzione.
    # Viene prima di ogni scrittura: l'attesa di Google non tiene lock aperti
    # su righe che altre prenotazioni aspettano (voci 11-12).
    try:
        in_vendita = ora_prenotabile(db, inizio, booking.duration_hours)
    except CalendarioNonRaggiungibile:
        # Nel dubbio nessuna vendita, come nell'elenco pubblico (pezzo 4.1).
        raise HTTPException(status_code=503, detail="Availability temporarily unavailable")
    if not in_vendita:
        raise HTTPException(status_code=400, detail="Slot not available")

    # Pagine vecchie: lo slot da cui prenotano si segna occupato, come prima
    # del 4.4, così la loro lista smette di offrirlo. È solo un riflesso per
    # quelle pagine, non una guardia: in vendita lo dice la verifica qui
    # sopra, e la doppia vendita la ferma la tabella ore_prenotate più sotto.
    for s in (slot, slot_secondario):
        if s:
            s.is_available = False

    # Riserva atomica del credito del pacchetto. Il controllo "ha ancora
    # sessioni?" più sopra è separato dalla scrittura, e due richieste
    # simultanee dello stesso cliente lo passerebbero entrambe, spendendo un
    # credito due volte: è la race condition spiegata alla guardia sulle
    # ore, più sotto. L'UPDATE condizionale sposta la verifica dentro la
    # scrittura. Come quella guardia, sta prima del commit e quindi prima di
    # Google Calendar, che si chiama solo a prenotazione salvata: un rifiuto
    # a evento già creato lascerebbe un appuntamento fantasma, che il
    # rollback non cancella perché sta fuori dal database.
    if package:
        esito_pacchetto = db.execute(
            update(Package)
            .where(Package.id == package.id, Package.sessioni_usate < Package.sessioni_totali)
            .values(sessioni_usate=Package.sessioni_usate + 1)
        )
        if esito_pacchetto.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="This package has no sessions left")
    # ─────────────────────────────────────────────────────────────

    # Prezzo zero se la sessione scala un pacchetto: l'importo è già stato
    # incassato all'acquisto e conteggiarlo di nuovo falserebbe gli incassi.
    price = 0 if package else TABELLA_PREZZI[booking.duration_hours]

    slot_rome = utc_to_rome(inizio)
    data_slot = slot_rome.strftime("%d/%m/%Y")
    ora_slot = slot_rome.strftime("%H:%M")

    db_booking = Booking(
        user_id=user.id,
        # Gli slot solo per le prenotazioni delle pagine vecchie (vedi sopra).
        slot_id=slot.id if slot else None,
        slot_id_secondario=slot_secondario.id if slot_secondario else None,
        start_time=inizio,
        duration_hours=booking.duration_hours,
        price_cents=price,
        service_type=booking.service_type,
        note_cliente=booking.note_cliente,
        vod_link=booking.vod_link,
        replay_code=booking.replay_code,
        status="confirmed",
        # calendar_event_id resta vuoto: l'evento si crea dopo il commit, più sotto.
        package_id=package.id if package else None,
        # Stringa casuale che autentica il link di recensione inviato dopo
        # la sessione, senza richiedere un login.
        review_token=secrets.token_urlsafe(32)
    )
    db.add(db_booking)
    # flush e non commit: la prenotazione riceve il suo id, che serve alle
    # righe qui sotto, ma niente è ancora salvato.
    db.flush()

    # Guardia sulle ore vendute (models/ora_prenotata.py).
    #
    # Un controllo seguito da una scrittura ("se è libera, occupala")
    # lascerebbe una finestra fra lettura e scrittura in cui una seconda
    # richiesta troverebbe l'ora ancora libera, producendo due prenotazioni
    # sullo stesso orario: la verifica "in vendita?" più sopra è proprio un
    # controllo di quel tipo. È una race condition, e si manifesta solo
    # sotto concorrenza reale.
    #
    # Qui la verifica sta dentro la scrittura: una riga per ogni ora della
    # sessione, e il database rifiuta un'ora già presente, quindi una sola
    # richiesta può riuscire. Con due richieste davvero simultanee, MySQL fa
    # aspettare la seconda scrittura finché la prima non è salvata, poi la
    # rifiuta. Fino al 4.3 lo stesso compito lo faceva un UPDATE condizionale
    # sullo slot, che senza slot non ha più niente da occupare.
    for ora in range(booking.duration_hours):
        db.add(OraPrenotata(inizio=db_booking.start_time + timedelta(hours=ora), booking_id=db_booking.id))
    try:
        db.flush()
    except IntegrityError:
        # Il rollback annulla anche la riserva del credito, gli slot delle
        # pagine vecchie e la prenotazione stessa: o tutto, o niente.
        db.rollback()
        raise HTTPException(status_code=400, detail="Slot not available")

    db.commit()
    db.refresh(db_booking)

    # Notifiche dopo il commit: sono accessorie, e un loro fallimento non
    # deve invalidare una prenotazione già salvata.
    invia_conferma_cliente(
        email_cliente=user.email,
        nome_cliente=user.nome,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata=booking.duration_hours,
        prezzo=price,
        riferimento=f"prenotazione {db_booking.id}"
    )

    invia_notifica_admin(
        nome_cliente=user.nome,
        email_cliente=user.email,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata=booking.duration_hours,
        note_cliente=booking.note_cliente
    )

    invia_notifica_discord(
        nome_cliente=user.nome,
        discord_tag=user.discord_tag,
        service_type=booking.service_type,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata_ore=booking.duration_hours,
        note_cliente=booking.note_cliente
    )

    # L'evento Google Calendar si crea a prenotazione salvata, non dentro la
    # transazione (voci 11-12). Le riserve qui sopra tengono un lock sulle
    # righe di slot e pacchetto fino al commit: con Google in mezzo, una
    # risposta lenta (fino a 60 s di timeout) faceva aspettare ogni altra
    # prenotazione dello stesso slot o pacchetto, e oltre i 50 s di attesa
    # MySQL rispondeva con un errore 1205, cioè un 500. Dopo le notifiche e
    # non prima: se da qui in poi qualcosa va storto, cliente e coach sono
    # già stati avvisati.
    event_id = crea_evento_calendario(
        nome_cliente=user.nome,
        categoria=user.categoria,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata_ore=booking.duration_hours,
        riferimento=f"prenotazione {db_booking.id}"
    )
    if event_id:
        # Il prezzo dell'ordine nuovo: finché Google non risponde la
        # prenotazione esiste senza id evento, e una cancellazione arrivata
        # in quel momento non trova niente da eliminare. L'id si salva quindi
        # solo se la prenotazione è ancora confermata, con la stessa
        # scrittura condizionale delle riserve; altrimenti l'evento appena
        # creato si elimina, o resterebbe in agenda per una sessione che non
        # esiste più.
        esito_evento = db.execute(
            update(Booking)
            .where(Booking.id == db_booking.id, Booking.status == "confirmed")
            .values(calendar_event_id=event_id)
        )
        db.commit()
        if esito_evento.rowcount == 0:
            elimina_evento_calendario(event_id)
    else:
        # La prenotazione resta valida anche senza evento, ma il coach usa
        # l'agenda per ricordarsi le sessioni: senza avviso la scoprirebbe
        # mancante solo guardandola.
        invia_alert_sistema(
            "Evento Calendar non creato",
            f"La prenotazione {db_booking.id} è confermata ma non ha un evento su "
            "Google Calendar: aggiungilo a mano. Il dettaglio è nei log di Railway."
        )

    return db_booking


@router.patch("/{booking_id}/cancella", response_model=BookingResponseStudente)
def cancella_prenotazione_cliente(
    booking_id: int,
    studente: User = Depends(get_studente),
    db: Session = Depends(get_db)
):
    """Cancellazione self-service di una propria prenotazione futura.

    Solo cancellazione, senza riprogrammazione: per un altro orario il
    cliente ripete la prenotazione. Verifica che la prenotazione appartenga
    allo studente autenticato, sia ancora attiva e non sia già passata.
    """
    prenotazione = db.query(Booking).filter(Booking.id == booking_id).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Booking not found")
    if prenotazione.user_id != studente.id:
        raise HTTPException(status_code=403, detail="This booking doesn't belong to you")
    if prenotazione.status != "confirmed":
        raise HTTPException(status_code=400, detail="This booking is not active")
    if prenotazione.start_time <= ora_utc_naive():
        raise HTTPException(status_code=400, detail="This session has already happened, it can no longer be cancelled")

    prenotazione.status = "cancelled"
    libera_slot_prenotazione(prenotazione, db)
    # Qui la prenotazione era per forza confirmed (controllo sopra): se era
    # pagata con un pacchetto, la sessione torna disponibile (decisione P7).
    restituisci_credito_pacchetto(prenotazione, db)
    db.commit()
    db.refresh(prenotazione)
    return prenotazione


@router.get("/recensioni/pubbliche", response_model=List[ReviewPubblica])
def recensioni_pubbliche(db: Session = Depends(get_db)):
    """Vetrina pubblica delle recensioni approvate, più recenti prima.

    Espone solo voto, commento, data e nome di battesimo: nessun contatto
    né riferimento interno, così una recensione resta attribuibile senza
    rivelare l'identità completa di chi l'ha scritta.
    """
    # Endpoint pubblico e potenzialmente molto chiamato: joinedload evita
    # due query aggiuntive per ogni recensione.
    recensioni = db.query(Review).options(
        joinedload(Review.booking).joinedload(Booking.user)
    ).filter(
        Review.approvata == True
    ).order_by(Review.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "voto": r.voto,
            "commento": r.commento,
            # Solo il nome di battesimo.
            "nome_cliente": r.booking.user.nome.split(" ")[0],
            "created_at": r.created_at
        }
        for r in recensioni
    ]


@router.post("/{booking_id}/recensione", response_model=ReviewResponse)
@limiter.limit("5/minute")
def lascia_recensione(request: Request, booking_id: int, recensione: ReviewCreate, db: Session = Depends(get_db)):
    """Registra la recensione di una sessione.

    Pubblico, raggiunto dal link inviato per email. L'autenticazione è il
    token casuale generato alla prenotazione: solo chi ha ricevuto quella
    email può conoscerlo. Una sola recensione per prenotazione.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # compare_digest e non ==: il confronto a tempo costante non rivela
    # quanti caratteri iniziali coincidono, chiudendo un attacco a tempo.
    if not booking.review_token or not secrets.compare_digest(recensione.token, booking.review_token):
        raise HTTPException(status_code=403, detail="Invalid token")

    esistente = db.query(Review).filter(Review.booking_id == booking_id).first()
    if esistente:
        raise HTTPException(status_code=400, detail="You've already left a review for this session")

    db_review = Review(
        booking_id=booking_id,
        voto=recensione.voto,
        commento=recensione.commento
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review
