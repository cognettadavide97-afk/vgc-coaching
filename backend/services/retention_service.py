# Data retention (Art. 5.1.e GDPR — "limitazione della conservazione"):
# i dati personali di un cliente non vanno tenuti più a lungo di quanto
# serva davvero. Qui "serve davvero" significa "finché la relazione con il
# servizio di coaching è attiva" (vedi frontend/privacy.html, sezione
# "Per quanto tempo i dati vengono conservati") — un cliente che non
# prenota/rinnova un pacchetto da RETENTION_MONTHS mesi viene considerato
# inattivo, e i suoi dati identificativi vengono anonimizzati in automatico.
#
# ANONIMIZZAZIONE, non cancellazione fisica: a differenza di
# DELETE /admin/clienti/{id} (backend/routers/admin.py, usato quando un
# cliente chiede espressamente la cancellazione), qui le prenotazioni e i
# pacchetti restano nel database — servono per lo storico incassi/analytics
# del pannello admin (dashboard, analytics, export CSV) — ma il cliente
# collegato smette di essere identificabile: nome, email, telefono e
# contatti Discord vengono sovrascritti con valori anonimi.

import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session, joinedload
from backend.models.users import User

# Configurabile da variabile d'ambiente (stesso pattern degli altri
# intervalli in backend/scheduler.py), con il default deciso per questo
# progetto: 24 mesi di inattività.
RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", "24"))

# Suffisso usato per generare l'email anonima al posto di quella vera —
# solo per leggibilità di chi guarda il database ("si vede a colpo d'occhio
# che questo cliente è stato anonimizzato"), NON più il modo in cui il job
# riconosce chi ha già processato: quello lo fa User.anonimizzato_at (vedi
# sotto), una colonna vera invece di una convenzione sul formato
# dell'email.
SUFFISSO_EMAIL_ANONIMIZZATA = "@anonimizzato.local"


def anonimizza_clienti_inattivi(db: Session) -> int:
    """
    Trova i clienti la cui ultima attività (registrazione, ultima
    prenotazione, ultimo pacchetto assegnato) risale a più di
    RETENTION_MONTHS mesi fa, e ne anonimizza i dati identificativi.
    Restituisce quanti clienti sono stati anonimizzati in questa
    esecuzione.
    """
    # Approssimazione voluta: 30 giorni per mese, non un calcolo calendariale
    # esatto (richiederebbe una libreria in più, tipo dateutil, solo per
    # questo) — per una soglia "di quanti mesi fa", uno scarto di qualche
    # giorno non cambia nulla nella pratica.
    ora = datetime.now(timezone.utc).replace(tzinfo=None)
    soglia = ora - timedelta(days=30 * RETENTION_MONTHS)

    # joinedload precarica bookings/packages di TUTTI i clienti in due JOIN
    # aggiuntivi nella STESSA query, invece di una query separata per
    # utente.bookings e una per utente.packages ad ogni giro del ciclo sotto
    # (un classico N+1: con 500 clienti sarebbero state 1001 query invece
    # di una sola) — stessa tecnica già usata per lo stesso motivo in
    # backend/scheduler.py.
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
