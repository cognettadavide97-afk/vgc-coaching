"""Data retention: anonimizzazione dei clienti inattivi (GDPR art. 5.1.e).

Anonimizzazione e non cancellazione: prenotazioni e pacchetti restano nel
database per lo storico e le statistiche, ma il cliente collegato smette di
essere identificabile. La cancellazione vera esiste a parte, per il caso in
cui sia il cliente a chiederla esplicitamente.
"""

import os
from datetime import timedelta
from sqlalchemy.orm import Session, joinedload
from backend.models.users import User
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

    anonimizzati = 0
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
            anonimizzati += 1

    if anonimizzati:
        db.commit()

    return anonimizzati
