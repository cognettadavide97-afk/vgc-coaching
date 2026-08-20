# Questo è il file più importante del progetto: gestisce la creazione di
# una prenotazione, l'operazione che mette insieme praticamente tutti gli
# altri pezzi dell'app (database, calendario, email, Discord). Vedi
# backend/routers/users.py per la spiegazione generale di un router FastAPI.

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.users import User
from backend.models.package import Package
from backend.models.review import Review
from backend.schemas.booking import BookingCreate, BookingResponse
from backend.schemas.review import ReviewCreate, ReviewResponse
from backend.services.email_service import invia_conferma_cliente, invia_notifica_admin
from backend.services.timezone_service import utc_to_rome
from backend.services.calendar_service import crea_evento_calendario
from backend.services.discord_service import invia_notifica_discord
from backend.routers.admin import get_admin
from backend.rate_limit import limiter
from typing import List

MAX_PRENOTAZIONI_ATTIVE = 2

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# I prezzi sono fissi e decisi dal server, non dal client (vedi il commento
# in backend/schemas/booking.py sul perché BookingCreate non ha un campo
# prezzo). Questo dizionario associa "quante ore" a "quanti centesimi".
# 20€/ora lineare: 1h = 2000 cent, 2h = 4000 cent (le sessioni singole sono
# limitate a 1-2 ore; per sessioni più lunghe esistono i pacchetti, vedi
# backend/models/package.py).
TABELLA_PREZZI = {1: 2000, 2: 4000}


@router.get("/", response_model=List[BookingResponse])
def get_bookings(admin: str = Depends(get_admin), db: Session = Depends(get_db)):
    return db.query(Booking).all()


@router.post("/", response_model=BookingResponse)
@limiter.limit("5/minute")
def create_booking(request: Request, booking: BookingCreate, db: Session = Depends(get_db)):
    # Questo endpoint NON richiede login: chiunque può prenotare (guest
    # checkout) — è una scelta di prodotto esplicita del progetto ("il
    # pagamento non è gestito in-app, quindi non serve un vero account").

    slot = db.query(Slot).filter(Slot.id == booking.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Controllo di coerenza: la durata richiesta deve corrispondere
    # esattamente alla durata reale dello slot scelto (uno slot da 1 ora
    # non può diventare una prenotazione da 2 ore solo perché il client lo
    # chiede) — il frontend (frontend/js/app.js) evita già che questo
    # succeda nell'uso normale, ma il server non si fida MAI solo del
    # client: ricontrolla sempre, perché chiunque può mandare una richiesta
    # HTTP direttamente, scavalcando l'interfaccia grafica.
    if booking.duration_hours != slot.duration_hours:
        raise HTTPException(
            status_code=400,
            detail=f"The requested duration ({booking.duration_hours}h) does not match the selected slot's duration ({slot.duration_hours}h)"
        )

    user = db.query(User).filter(User.id == booking.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Redenzione pacchetto (opzionale): se il client indica un package_id
    # non ci fidiamo del prezzo "gratis" mostrato in UI — ricontrolliamo qui
    # che il pacchetto esista davvero, appartenga a QUESTO utente, abbia
    # ancora sessioni residue e che la sua durata combaci con quella
    # richiesta (tutti i pacchetti del catalogo attuale sono da 2 ore, vedi
    # backend/services/package_service.py, ma il controllo resta generico).
    package = None
    if booking.package_id is not None:
        package = db.query(Package).filter(Package.id == booking.package_id).first()
        if not package or package.user_id != booking.user_id:
            raise HTTPException(status_code=404, detail="Package not found")
        if package.sessioni_usate >= package.sessioni_totali:
            raise HTTPException(status_code=400, detail="This package has no sessions left")
        if package.durata_sessione_ore != booking.duration_hours:
            raise HTTPException(
                status_code=400,
                detail=f"This package covers {package.durata_sessione_ore}h sessions, not {booking.duration_hours}h"
            )

    # limite anti-abuso: senza pagamento anticipato, niente impedisce a una
    # stessa persona di occupare più slot contemporaneamente. Contiamo solo
    # le prenotazioni confermate con slot ancora futuro (quelle "attive").
    prenotazioni_attive = db.query(Booking).join(Slot).filter(
        Booking.user_id == booking.user_id,
        Booking.status == "confirmed",
        Slot.start_time >= datetime.now(timezone.utc).replace(tzinfo=None)
    ).count()
    if prenotazioni_attive >= MAX_PRENOTAZIONI_ATTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"You already have {MAX_PRENOTAZIONI_ATTIVE} active bookings. Cancel or complete a session before booking another one."
        )

    # ─────────────────────────────────────────────────────────────
    # QUESTA È LA PARTE PIÙ DELICATA DI TUTTO IL PROGETTO. Spieghiamola con
    # calma perché il "perché" è più importante del "come".
    #
    # Immagina che due studenti clicchino "Conferma" nello stesso identico
    # istante sullo stesso slot. Se il codice facesse semplicemente:
    #
    #   if slot.is_available:        # 1. leggi
    #       slot.is_available = False  # 2. scrivi
    #
    # esiste una finestra di tempo, piccolissima ma reale, tra il momento
    # in cui LEGGIAMO che lo slot è libero e il momento in cui SCRIVIAMO che
    # non lo è più. Se la seconda richiesta arriva a leggere lo slot proprio
    # in quella finestra — prima che la prima richiesta abbia scritto il suo
    # cambiamento — anche lei lo troverebbe ancora "libero", e finiremmo con
    # DUE prenotazioni sullo stesso slot. Questo si chiama "race condition"
    # (condizione di gara): il risultato dipende da chi "vince la gara" ad
    # arrivare per primo, in un modo imprevedibile e potenzialmente rotto.
    #
    # La soluzione qui è un UPDATE condizionale: invece di leggere e poi
    # scrivere in due passi separati, chiediamo al database di fare "leggi
    # e scrivi" come UNA SINGOLA operazione atomica (indivisibile). La
    # query dice letteralmente: "aggiorna questo slot mettendo is_available
    # a False, MA SOLO SE è ancora True in questo momento". MySQL garantisce
    # che, quando due richieste provano a fare questo nello stesso istante,
    # una delle due (chiunque arrivi fisicamente prima al database) blocca
    # temporaneamente quella riga finché non ha finito, e SOLO DOPO lascia
    # che l'altra richiesta proceda — che a quel punto troverà già
    # is_available=False, e quindi non modificherà nulla.
    esito = db.execute(
        update(Slot)
        .where(Slot.id == booking.slot_id, Slot.is_available == True)
        .values(is_available=False)
    )
    # esito.rowcount dice quante righe sono state DAVVERO modificate da
    # questo UPDATE. Se è 0, vuol dire che la condizione "is_available ==
    # True" non era più vera quando la nostra richiesta è arrivata — cioè
    # qualcun altro ci ha preceduto. In quel caso rifiutiamo la richiesta.
    if esito.rowcount == 0:
        db.rollback()  # annulla qualunque modifica non ancora salvata in questa sessione
        raise HTTPException(status_code=400, detail="Slot not available")
    # ─────────────────────────────────────────────────────────────

    # Se la prenotazione usa un pacchetto, la sessione è già stata pagata in
    # blocco al momento dell'acquisto del pacchetto: prezzo 0 qui, per non
    # farla contare due volte negli incassi.
    price = 0 if package else TABELLA_PREZZI[booking.duration_hours]

    slot_rome = utc_to_rome(slot.start_time)
    data_slot = slot_rome.strftime("%d/%m/%Y")
    ora_slot = slot_rome.strftime("%H:%M")

    # crea l'evento sul calendario Google del coach subito alla prenotazione,
    # dato che ora la conferma è immediata (nessun passaggio manuale admin dopo).
    # In caso di errore l'evento è semplicemente assente (non blocca la prenotazione).
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
        user_id=booking.user_id,
        slot_id=booking.slot_id,
        duration_hours=booking.duration_hours,
        price_cents=price,
        service_type=booking.service_type,
        note_cliente=booking.note_cliente,
        vod_link=booking.vod_link,
        replay_code=booking.replay_code,
        status="confirmed",
        calendar_event_id=event_id,
        package_id=package.id if package else None,
        # token_urlsafe genera una stringa casuale non indovinabile: è
        # quello che autentica il link di recensione post-sessione (vedi
        # backend/scheduler.py) senza richiedere un vero login cliente.
        review_token=secrets.token_urlsafe(32)
    )
    db.add(db_booking)

    if package:
        package.sessioni_usate += 1

    db.commit()
    db.refresh(db_booking)

    # Le tre notifiche seguenti vengono mandate DOPO che la prenotazione è
    # già salvata (db.commit() sopra) — così, anche se una di queste
    # dovesse fallire (vedi i commenti try/except in email_service.py e
    # discord_service.py), la prenotazione resta comunque valida: le
    # notifiche sono un "di più", non una condizione per il successo della
    # prenotazione stessa.
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


@router.post("/{booking_id}/recensione", response_model=ReviewResponse)
@limiter.limit("5/minute")
def lascia_recensione(request: Request, booking_id: int, recensione: ReviewCreate, db: Session = Depends(get_db)):
    """
    Endpoint pubblico raggiunto dal link mandato via email dopo la sessione
    (vedi backend/scheduler.py). Non richiede login: l'autenticazione è il
    "token" — una stringa casuale generata alla creazione della
    prenotazione (vedi create_booking sopra) che solo chi ha ricevuto
    quell'email può conoscere.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # secrets.compare_digest confronta due stringhe in "tempo costante": a
    # differenza di "==", il tempo impiegato non rivela quanti caratteri
    # iniziali combaciano, il che rende più difficile indovinare il token
    # provando molte richieste (attacco a tempistica).
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
