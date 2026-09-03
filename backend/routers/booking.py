"""Endpoint delle prenotazioni.

La creazione è l'operazione più delicata dell'applicazione: coordina
database, calendario, email e notifiche, e concentra i controlli di
sicurezza sull'identità di chi prenota. Contiene inoltre gli endpoint di
cancellazione self-service e di gestione delle recensioni.
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.users import User
from backend.models.package import Package
from backend.models.review import Review
from backend.schemas.booking import BookingCreate, BookingResponse, BookingResponseStudente
from backend.schemas.review import ReviewCreate, ReviewResponse, ReviewPubblica
from backend.services.email_service import invia_conferma_cliente, invia_notifica_admin
from backend.services.timezone_service import utc_to_rome, ora_utc_naive
from backend.services.calendar_service import crea_evento_calendario
from backend.services.discord_service import invia_notifica_discord
from backend.services.booking_service import libera_slot_prenotazione
from backend.routers.users import get_studente, get_studente_opzionale
from backend.rate_limit import limiter
from typing import List, Optional

MAX_PRENOTAZIONI_ATTIVE = 2

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# Listino deciso dal server: il client non invia mai un prezzo. 20 EUR/ora
# lineare; le sessioni singole sono limitate a 1-2 ore, oltre esistono i
# pacchetti.
TABELLA_PREZZI = {1: 2000, 2: 4000}

# Orari di inizio ammessi per le sessioni da 2 ore (ora italiana). Con
# ricevimento 15:00-19:00, ammettere anche le 16:00 creerebbe blocchi
# incompatibili fra loro (15-17 e 16-18) e lascerebbe ore isolate
# difficili da vendere. Vincolo di prodotto, non tecnico.
ORE_INIZIO_VALIDE_2H = {15, 17}


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

    slot = db.query(Slot).filter(Slot.id == booking.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Nessun processo marca gli slot come scaduti: senza questo controllo
    # una richiesta diretta potrebbe confermare un appuntamento nel passato,
    # generando evento ed email per una sessione impossibile.
    if slot.start_time <= ora_utc_naive():
        raise HTTPException(status_code=400, detail="This slot is in the past")

    # Il calendario genera solo slot da 1 ora: una sessione da 2 ore occupa
    # lo slot scelto e quello successivo, se esiste ed è libero.
    # slot_secondario resta None per le sessioni da 1 ora.
    #
    # Il controllo è ripetuto qui anche se il frontend propone solo
    # combinazioni valide: l'interfaccia è scavalcabile con una richiesta
    # diretta. Vale per tutti i controlli di questa funzione.
    slot_secondario = None
    if booking.duration_hours != slot.duration_hours:
        if booking.duration_hours == 2 and slot.duration_hours == 1:
            if utc_to_rome(slot.start_time).hour not in ORE_INIZIO_VALIDE_2H:
                raise HTTPException(
                    status_code=400,
                    detail="A 2-hour session can only start at 15:00 or 17:00"
                )
            inizio_secondario = slot.start_time + timedelta(hours=1)
            slot_secondario = db.query(Slot).filter(
                Slot.start_time == inizio_secondario,
                Slot.duration_hours == 1
            ).first()
            if not slot_secondario or not slot_secondario.is_available:
                raise HTTPException(
                    status_code=400,
                    detail="The following hour isn't available, so a 2-hour session can't start here"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"The requested duration ({booking.duration_hours}h) does not match the selected slot's duration ({slot.duration_hours}h)"
            )

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
    # confermate con slot ancora futuro.
    prenotazioni_attive = db.query(Booking).join(Booking.slot).filter(
        Booking.user_id == user.id,
        Booking.status == "confirmed",
        Slot.start_time >= ora_utc_naive()
    ).count()
    if prenotazioni_attive >= MAX_PRENOTAZIONI_ATTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"You already have {MAX_PRENOTAZIONI_ATTIVE} active bookings. Cancel or complete a session before booking another one."
        )

    # Riserva atomica dello slot.
    #
    # Un controllo seguito da una scrittura ("se è libero, occupalo")
    # lascerebbe una finestra fra lettura e scrittura in cui una seconda
    # richiesta troverebbe lo slot ancora libero, producendo due
    # prenotazioni sullo stesso orario. È una race condition, e si
    # manifesta solo sotto concorrenza reale.
    #
    # L'UPDATE condizionale sposta la verifica dentro la scrittura: il
    # database garantisce che una sola richiesta possa trovare la
    # condizione vera.
    esito = db.execute(
        update(Slot)
        .where(Slot.id == booking.slot_id, Slot.is_available == True)
        .values(is_available=False)
    )
    # rowcount a zero significa che la condizione non era più vera: un'altra
    # richiesta ha riservato lo slot per prima.
    if esito.rowcount == 0:
        db.rollback()  # annulla qualunque modifica non ancora salvata in questa sessione
        raise HTTPException(status_code=400, detail="Slot not available")

    # Stessa riserva per il secondo slot delle sessioni da 2 ore. Il
    # rollback annulla anche la prima, non ancora committata: o si
    # riservano entrambi gli slot, o nessuno.
    if slot_secondario:
        esito_secondario = db.execute(
            update(Slot)
            .where(Slot.id == slot_secondario.id, Slot.is_available == True)
            .values(is_available=False)
        )
        if esito_secondario.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="Slot not available")
    # ─────────────────────────────────────────────────────────────

    # Prezzo zero se la sessione scala un pacchetto: l'importo è già stato
    # incassato all'acquisto e conteggiarlo di nuovo falserebbe gli incassi.
    price = 0 if package else TABELLA_PREZZI[booking.duration_hours]

    slot_rome = utc_to_rome(slot.start_time)
    data_slot = slot_rome.strftime("%d/%m/%Y")
    ora_slot = slot_rome.strftime("%H:%M")

    # La conferma è immediata, quindi l'evento si crea subito. Un errore
    # qui lascia la prenotazione senza evento, senza farla fallire.
    event_id = crea_evento_calendario(
        nome_cliente=user.nome,
        email_cliente=user.email,
        categoria=user.categoria,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata_ore=booking.duration_hours,
        note_cliente=booking.note_cliente
    )

    db_booking = Booking(
        user_id=user.id,
        slot_id=booking.slot_id,
        slot_id_secondario=slot_secondario.id if slot_secondario else None,
        duration_hours=booking.duration_hours,
        price_cents=price,
        service_type=booking.service_type,
        note_cliente=booking.note_cliente,
        vod_link=booking.vod_link,
        replay_code=booking.replay_code,
        status="confirmed",
        calendar_event_id=event_id,
        package_id=package.id if package else None,
        # Stringa casuale che autentica il link di recensione inviato dopo
        # la sessione, senza richiedere un login.
        review_token=secrets.token_urlsafe(32)
    )
    db.add(db_booking)

    if package:
        package.sessioni_usate += 1

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
        prezzo=price
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
    if prenotazione.slot.start_time <= ora_utc_naive():
        raise HTTPException(status_code=400, detail="This session has already happened, it can no longer be cancelled")

    prenotazione.status = "cancelled"
    libera_slot_prenotazione(prenotazione, db)
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
