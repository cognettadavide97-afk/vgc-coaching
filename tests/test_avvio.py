# Questo file testa una cosa diversa da tutti gli altri: non il comportamento
# di un endpoint, ma cosa succede nel momento in cui il programma viene
# IMPORTATO — prima ancora che qualcuno faccia una richiesta.
#
# Il problema che protegge (REVISIONE_2026-09-01.md, ritrovamenti R1 e R17):
# run_migrations() e avvia_scheduler() erano chiamate a livello di modulo in
# backend/main.py, cioè si eseguivano al solo "import backend.main". Ma quel
# import lo fa anche tests/conftest.py per ottenere l'app da testare — quindi
# lanciare la suite significava, senza volerlo:
#   - applicare le migrazioni Alembic al database indicato da DATABASE_URL
#     (in locale, con un .env popolato, il database di SVILUPPO VERO);
#   - far partire un thread APScheduler con gli 8 job periodici, che usano il
#     SessionLocal reale e non l'override dei test;
#   - in caso di errore, mandare un alert Discord VERO al canale del coach
#     (invia_alert_sistema non è tra le funzioni sostituite da conftest.py).
#
# Perché il test gira in un SOTTOPROCESSO invece che qui dentro: quando pytest
# esegue questo file, backend.main è già stato importato da conftest.py, quindi
# l'eventuale danno sarebbe già fatto e non più osservabile. L'unico modo di
# testare "cosa succede all'import" è farne uno pulito in un processo nuovo e
# guardare cosa combina.

import os
import subprocess
import sys
from pathlib import Path

RADICE_PROGETTO = Path(__file__).resolve().parent.parent

# Il programma da eseguire nel sottoprocesso: importa l'app e riferisce se nel
# frattempo è comparso il thread dello scheduler. threading.enumerate() elenca
# i thread vivi in quel momento; APScheduler chiama il proprio "APScheduler",
# quindi basta cercarlo per nome.
PROGRAMMA = (
    "import threading;"
    "import backend.main;"
    "vivi = [t.name for t in threading.enumerate()];"
    "print('SCHEDULER_AVVIATO' if 'APScheduler' in vivi else 'NESSUNO_SCHEDULER')"
)


def _ambiente_isolato() -> dict:
    """
    Variabili d'ambiente per il sottoprocesso. Due accortezze importanti:

    1. DATABASE_URL punta a uno SQLite in memoria, mai al database vero. Nota
       che load_dotenv() (chiamato da backend/database.py) NON sovrascrive le
       variabili già presenti nell'ambiente: impostandola qui, quella del .env
       viene ignorata.
    2. DISCORD_WEBHOOK_URL viene azzerata di proposito. Se questo test girasse
       su una macchina con il .env reale e il codice fosse ancora quello
       vecchio, l'import proverebbe le migrazioni, fallirebbe (il DDL è MySQL,
       il database è SQLite) e manderebbe un alert Discord VERO — cioè il test
       riprodurrebbe esattamente il danno che vuole prevenire. Con la stringa
       vuota, invia_alert_sistema salta l'invio e si limita a un warning.
    """
    ambiente = dict(os.environ)
    ambiente["DATABASE_URL"] = "sqlite:///:memory:"
    ambiente["JWT_SECRET"] = "test-secret-non-usato-in-produzione"
    ambiente["DISCORD_WEBHOOK_URL"] = ""
    return ambiente


def test_import_non_avvia_scheduler_ne_esegue_migrazioni():
    """
    Importare backend.main non deve avere NESSUN effetto collaterale: né
    avviare lo scheduler, né toccare il database. Gli avvii veri avvengono
    solo quando parte davvero un server (handler lifespan di FastAPI).
    """
    risultato = subprocess.run(
        [sys.executable, "-c", PROGRAMMA],
        capture_output=True,
        text=True,
        cwd=RADICE_PROGETTO,
        env=_ambiente_isolato(),
        timeout=120,
    )

    assert risultato.returncode == 0, f"l'import è fallito:\n{risultato.stderr}"

    # 1. Nessun thread dello scheduler.
    assert "NESSUNO_SCHEDULER" in risultato.stdout, (
        "importare backend.main ha avviato il thread APScheduler: gli 8 job "
        "periodici girerebbero anche durante i test, sul database reale"
    )

    # 2. Nessun tentativo di migrazione. Se run_migrations() girasse
    #    all'import, con uno SQLite e migrazioni scritte per MySQL fallirebbe
    #    e finirebbe nel proprio blocco except, che logga "Errore migrazioni".
    #    L'assenza di entrambe le righe è quindi la prova che non è stata
    #    nemmeno tentata.
    log = risultato.stderr
    assert "Errore migrazioni" not in log, (
        "importare backend.main ha tentato di eseguire le migrazioni Alembic "
        "sul database indicato da DATABASE_URL"
    )
    assert "Migrazioni eseguite con successo" not in log, (
        "importare backend.main ha eseguito le migrazioni Alembic"
    )
