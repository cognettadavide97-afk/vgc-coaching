"""Data retention: anonimizzazione dei clienti inattivi (GDPR art. 5.1.e).

Anonimizzazione e non cancellazione: prenotazioni e pacchetti restano nel
database per lo storico e le statistiche — data, importo, tipo di servizio,
esito — ma smettono di essere riconducibili a una persona. Spariscono gli
identificativi sulla riga `users` e il testo libero scritto a mano, che è
l'altro posto in cui un nome finisce: le note del coach e le note di
prenotazione. La cancellazione vera esiste a parte, per il caso in cui sia
il cliente a chiederla esplicitamente.
"""

import os
from datetime import timedelta
from sqlalchemy.orm import Session, joinedload
from backend.models.users import User
from backend.models.booking import Booking
from backend.models.client_note import ClientNote
from backend.services.timezone_service import ora_utc_naive

RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", "24"))

# Suffisso dell'email generata al posto di quella reale: serve solo a
# rendere evidente a colpo d'occhio un record anonimizzato. Il marcatore
# autorevole è `User.anonimizzato_at`, non il formato dell'email.
SUFFISSO_EMAIL_ANONIMIZZATA = "@anonimizzato.local"


def anonimizza_clienti_inattivi(db: Session) -> int:
    """Anonimizza i clienti inattivi da oltre `RETENTION_MONTHS` mesi.

    L'attività è la più recente fra registrazione, prenotazioni e pacchetti.
    Restituisce il numero di clienti anonimizzati in questa esecuzione.
    """
    # Approssimazione voluta a 30 giorni per mese: su una soglia di mesi lo
    # scarto è irrilevante e evita una dipendenza in più.
    ora = ora_utc_naive()
    soglia = ora - timedelta(days=30 * RETENTION_MONTHS)

    # joinedload evita una query per cliente nel ciclo sottostante.
    clienti_attivi = db.query(User).filter(
        User.anonimizzato_at.is_(None)
    ).options(
        joinedload(User.bookings),
        joinedload(User.packages)
    ).all()

    id_anonimizzati = []
    for utente in clienti_attivi:
        date_attivita = [utente.created_at]
        date_attivita += [b.created_at for b in utente.bookings]
        date_attivita += [p.created_at for p in utente.packages]
        ultima_attivita = max(d for d in date_attivita if d is not None)

        if ultima_attivita < soglia:
            utente.nome = "Cliente anonimizzato"
            utente.email = f"anonimizzato-{utente.id}{SUFFISSO_EMAIL_ANONIMIZZATA}"
            utente.telefono = None
            utente.discord_tag = None
            utente.discord_id = None
            utente.anonimizzato_at = ora
            id_anonimizzati.append(utente.id)

    if id_anonimizzati:
        # Azzerare la sola riga `users` non anonimizza nessuno: le note sono
        # testo libero scritto a mano, e lì dentro finiscono nome, cognome,
        # tag Discord, a volte un recapito. Restano leggibili e restano
        # collegate al cliente per `user_id`/`booking_id`, quindi senza questi
        # due statement la promessa del docstring qui sopra — e quella fatta al
        # pubblico nell'informativa privacy — sarebbe falsa. È anche il punto
        # in cui questa via si allineava male con l'altra: `elimina_cliente`
        # (routers/admin/clients.py) le note le rimuove davvero.
        #
        # Le note del coach si cancellano invece di svuotarsi perché
        # `client_notes.nota` è NOT NULL: l'alternativa sarebbe un segnaposto,
        # cioè righe che non dicono più niente su un cliente non più
        # identificabile. Le prenotazioni invece RESTANO — data, importo e
        # servizio servono alle statistiche di incasso — e si azzerano solo i
        # due campi di testo, entrambi nullable.
        #
        # Due statement soli, fuori dal ciclo: dentro sarebbero due query per
        # cliente, e una singola esecuzione ne tratta molti.
        #
        # A differenza di `admin/clients.py` qui NON serve un db.flush() prima:
        # con autoflush=False (backend/database.py) queste due istruzioni di
        # massa raggiungono il database prima delle modifiche accodate sugli
        # utenti, ma non dipendono da quelle — filtrano su id già noti — e
        # nessuna chiave esterna lega queste righe ai campi cambiati su `users`.
        #
        # synchronize_session=False: le prenotazioni già caricate in memoria dal
        # joinedload qui sopra conservano il testo vecchio, ma il commit che
        # segue le scade tutte, quindi ogni lettura successiva ripassa dal
        # database.
        db.query(ClientNote).filter(
            ClientNote.user_id.in_(id_anonimizzati)
        ).delete(synchronize_session=False)

        db.query(Booking).filter(
            Booking.user_id.in_(id_anonimizzati)
        ).update(
            {Booking.note_cliente: None, Booking.note_admin: None},
            synchronize_session=False
        )

        db.commit()

    return len(id_anonimizzati)
