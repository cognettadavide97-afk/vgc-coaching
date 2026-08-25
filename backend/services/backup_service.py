# Backup del database di produzione — vedi il commento nel README (sezione
# "Backup") per il perché esiste: il piano Railway attuale (Hobby) NON
# include backup automatici né point-in-time recovery per il database
# MySQL (verificato direttamente nella dashboard: "Backups and
# point-in-time recovery (PITR) are only available for customers on the
# Pro plan"). Senza questo file, un problema al volume del database
# significherebbe perdere per sempre tutti i dati — nessuna rete di
# sicurezza.
#
# Come funziona, in breve: una volta al giorno (vedi il job schedulato in
# backend/scheduler.py) questo modulo genera un vero dump SQL (schema +
# dati, restorabile con un comando "mysql < file.sql" standard, esattamente
# come farebbe il comando mysqldump) e lo carica su Google Drive — un posto
# DIVERSO da Railway, apposta: un backup che vive sullo stesso posto che
# potrebbe rompersi non protegge da nulla.
#
# ATTENZIONE, scoperta fatta testando questo file contro Drive vero: NON usa
# il service account già configurato per Google Calendar (vedi
# calendar_service.py), a differenza di quanto si potrebbe pensare essendo
# lo stesso progetto Google Cloud. Un service account NON ha una propria
# quota di archiviazione su Drive — anche condividendo una cartella con lui
# in modalità Editor, ogni file che CREA conta sulla SUA quota (zero), non
# su quella del proprietario della cartella, e Google rifiuta l'upload con
# un errore "storageQuotaExceeded" a runtime (le Shared Drive risolverebbero,
# ma sono una funzionalità Google Workspace, non disponibile su un account
# Gmail personale gratuito). La soluzione che funziona davvero è la stessa
# di email_service.py: OAuth con l'account Google VERO del coach (non un
# service account) — i file creati contano sulla sua quota reale (15GB
# gratuiti). Il refresh token si ottiene con scripts/reauth_drive.py (stesso
# meccanismo di scripts/reauth_gmail.py, scope diverso).
#
# Perché un dump scritto a mano invece della libreria mysqldump vera: il
# progetto gira su Railway con nixpacks (vedi nixpacks.toml), che non
# include il client MySQL di default — aggiungerlo vorrebbe dire introdurre
# una dipendenza di sistema in più, con un nome di pacchetto Nix da
# indovinare e verificare solo dopo un deploy reale. Usando solo PyMySQL
# (già una dipendenza del progetto) per leggere schema e dati riga per
# riga, il dump resta puro Python, portabile, e verificabile in locale
# prima di fidarsene in produzione.

import os
import io
import logging
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv
from backend.services.google_oauth_service import credenziali_oauth_google

load_dotenv()

# OAuth con l'account Google vero del coach (non un service account — vedi
# il commento in cima al file sul perché). Riusa lo stesso client OAuth già
# creato per Gmail (GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET, vedi
# email_service.py): è la stessa app registrata su Google Cloud, a cui
# aggiungiamo solo lo scope Drive (https://www.googleapis.com/auth/drive.file
# — concesso una volta sola al momento dell'autorizzazione via
# scripts/reauth_drive.py, non ripetuto ad ogni chiamata) nella schermata di
# consenso — non serve creare un secondo client OAuth. DRIVE_REFRESH_TOKEN è
# invece un token SEPARATO da GMAIL_REFRESH_TOKEN, non lo stesso riusato:
# tenerli separati significa che se uno dei due scade o va revocato, l'altro
# continua a funzionare indipendentemente.
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
DRIVE_REFRESH_TOKEN = os.getenv("DRIVE_REFRESH_TOKEN")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BACKUP_FOLDER_ID")

BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# Quante righe raggruppare in un solo statement INSERT durante il dump
# (vedi crea_dump_sql) — non configurabile da env, è un dettaglio
# implementativo del dump, non una scelta operativa come le due sopra.
RIGHE_PER_INSERT = 500

logger = logging.getLogger(__name__)


def _get_drive_service():
    credenziali = credenziali_oauth_google(DRIVE_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
    return build("drive", "v3", credentials=credenziali)


def crea_dump_sql(engine) -> str:
    """
    Genera un dump SQL completo (schema + dati) del database collegato a
    "engine" — un vero file .sql, restorabile con un client MySQL standard
    (`mysql nome_db < backup.sql`), non un formato proprietario.

    engine è un parametro esplicito (non importato direttamente da
    backend.database) apposta per poter passare un motore diverso nei
    test, invece di dipendere sempre dal database reale configurato in
    produzione.
    """
    connessione = engine.raw_connection()
    try:
        cursore = connessione.cursor()
        cursore.execute("SHOW TABLES")
        tabelle = [riga[0] for riga in cursore.fetchall()]

        righe_dump = [
            "-- Backup automatico VGC Coaching",
            f"-- Generato il {datetime.now(timezone.utc).isoformat()} UTC",
            "SET FOREIGN_KEY_CHECKS=0;",
            ""
        ]

        # I nomi delle tabelle vengono da SHOW TABLES sul NOSTRO stesso
        # database (mai da input di un utente) — interpolarli direttamente
        # nell'SQL qui sotto è sicuro esattamente per lo stesso motivo per
        # cui lo è nel resto del progetto: non è un dato esterno non
        # fidato, viene dallo schema del database stesso.
        for tabella in tabelle:
            cursore.execute(f"SHOW CREATE TABLE `{tabella}`")
            _, create_stmt = cursore.fetchone()
            righe_dump.append(f"DROP TABLE IF EXISTS `{tabella}`;")
            righe_dump.append(create_stmt + ";")
            righe_dump.append("")

            cursore.execute(f"SELECT * FROM `{tabella}`")
            colonne = [descrizione[0] for descrizione in cursore.description]
            righe = cursore.fetchall()

            if righe:
                colonne_sql = ", ".join(f"`{c}`" for c in colonne)
                # RIGHE_PER_INSERT righe per ogni statement INSERT, invece
                # di uno statement per riga: un mysqldump vero fa lo
                # stesso, per un motivo concreto — un ripristino
                # (`mysql < backup.sql`) con uno statement per riga
                # obbligherebbe il database a un giro di andata/ritorno per
                # ogni singola riga della tabella; raggruppandole, lo
                # stesso ripristino richiede una frazione delle query.
                for inizio in range(0, len(righe), RIGHE_PER_INSERT):
                    blocco = righe[inizio:inizio + RIGHE_PER_INSERT]
                    # connessione.escape() (metodo di PyMySQL) trasforma
                    # ogni valore Python nel suo letterale SQL sicuro:
                    # stringhe tra apici con i caratteri speciali
                    # "scappati", None diventa NULL, date/numeri formattati
                    # correttamente — stesso compito di mysqldump, scritto
                    # a mano qui perché il binario mysqldump non è
                    # disponibile nell'ambiente di produzione (vedi il
                    # commento in cima al file).
                    valori_blocco = ", ".join(
                        "(" + ", ".join(connessione.escape(v) for v in riga) + ")"
                        for riga in blocco
                    )
                    righe_dump.append(f"INSERT INTO `{tabella}` ({colonne_sql}) VALUES {valori_blocco};")
                righe_dump.append("")

        righe_dump.append("SET FOREIGN_KEY_CHECKS=1;")
        return "\n".join(righe_dump)
    finally:
        connessione.close()


def _carica_su_drive(servizio, contenuto: str, nome_file: str):
    media = MediaIoBaseUpload(
        io.BytesIO(contenuto.encode("utf-8")),
        mimetype="application/sql"
    )
    servizio.files().create(
        body={"name": nome_file, "parents": [DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id"
    ).execute()


def _elimina_backup_scaduti(servizio):
    """
    Cancella dalla cartella Drive i backup più vecchi di BACKUP_RETENTION_DAYS
    giorni — senza questo, i backup si accumulerebbero all'infinito (un file
    nuovo ogni giorno, per sempre), esattamente il tipo di crescita
    illimitata già evitato altrove nel progetto (vedi
    backend/services/retention_service.py).
    """
    soglia = (datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    risultato = servizio.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and createdTime < '{soglia}'",
        fields="files(id, name)"
    ).execute()

    for file in risultato.get("files", []):
        servizio.files().delete(fileId=file["id"]).execute()
        logger.info(f"Backup scaduto eliminato da Drive: {file['name']}")


def esegui_backup_database(engine) -> bool:
    """
    Orchestratore chiamato dallo scheduler (vedi backend/scheduler.py):
    genera il dump, lo carica su Drive, ripulisce i backup scaduti.
    Restituisce True/False invece di sollevare l'eccezione — il chiamante
    decide se e come avvisare il coach in caso di fallimento (stesso
    pattern di verifica_credenziali_gmail in
    backend/services/email_service.py).
    """
    if not DRIVE_FOLDER_ID or not DRIVE_REFRESH_TOKEN:
        logger.warning("GOOGLE_DRIVE_BACKUP_FOLDER_ID o DRIVE_REFRESH_TOKEN non configurati — salto il backup")
        return False

    try:
        dump = crea_dump_sql(engine)
        nome_file = f"vgc-coaching-backup-{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.sql"

        servizio = _get_drive_service()
        _carica_su_drive(servizio, dump, nome_file)
        _elimina_backup_scaduti(servizio)

        logger.info(f"Backup database completato: {nome_file}")
        return True
    except Exception:
        logger.exception("Backup database fallito")
        return False
