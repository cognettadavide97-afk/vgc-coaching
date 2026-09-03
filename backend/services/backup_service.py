"""Backup giornaliero del database su Google Drive.

Il piano di hosting in uso non include backup né point-in-time recovery
per il database: senza questo modulo un guasto al volume significherebbe
perdita totale dei dati. La destinazione è deliberatamente esterna
all'hosting — un backup sullo stesso sistema che può rompersi non protegge.

Due scelte non ovvie, entrambe imposte dall'ambiente:

- **Non usa il service account** configurato per Google Calendar. Un
  service account non ha quota di archiviazione propria su Drive: i file
  che crea vengono rifiutati con `storageQuotaExceeded` anche dentro una
  cartella condivisa in scrittura. Serve OAuth con un account reale, il
  cui refresh token si ottiene con `scripts/reauth_drive.py`.
- **Il dump è scritto in Python** anziché delegato a `mysqldump`, che non
  è presente nell'immagine di produzione. Usare solo PyMySQL, già
  dipendenza del progetto, evita di introdurre una dipendenza di sistema
  verificabile solo dopo un deploy.
"""

import os
import io
import logging
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv
from backend.services.google_oauth_service import credenziali_oauth_google

load_dotenv()

# Riusa il client OAuth di Gmail (stessa app registrata, con in più lo
# scope Drive), ma un refresh token distinto: se uno dei due viene revocato
# o scade, l'altra integrazione continua a funzionare.
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
DRIVE_REFRESH_TOKEN = os.getenv("DRIVE_REFRESH_TOKEN")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BACKUP_FOLDER_ID")

BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# Dettaglio implementativo del dump, non una scelta operativa: per questo
# non è configurabile da variabile d'ambiente.
RIGHE_PER_INSERT = 500

logger = logging.getLogger(__name__)


def _get_drive_service():
    credenziali = credenziali_oauth_google(DRIVE_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
    return build("drive", "v3", credentials=credenziali)


def crea_dump_sql(engine) -> str:
    """Genera un dump SQL completo (schema e dati) del database.

    Il risultato è un file .sql standard, ripristinabile con
    `mysql nome_db < backup.sql`. `engine` è un parametro esplicito e non
    un import diretto per poter passare un motore diverso nei test.
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

        # I nomi delle tabelle provengono da SHOW TABLES sullo schema
        # stesso, mai da input esterno: l'interpolazione è sicura.
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
                # INSERT multi-riga: con uno statement per riga il
                # ripristino richiederebbe un round-trip per ogni record.
                for inizio in range(0, len(righe), RIGHE_PER_INSERT):
                    blocco = righe[inizio:inizio + RIGHE_PER_INSERT]
                    # connessione.escape() converte ogni valore Python nel
                    # letterale SQL corretto (quoting, NULL, date).
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
    """Elimina dalla cartella Drive i backup oltre la retention configurata.

    Senza, i file si accumulerebbero indefinitamente al ritmo di uno al
    giorno.
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
    """Esegue dump, upload e pulizia dei backup scaduti.

    Restituisce l'esito invece di propagare l'eccezione: è il chiamante a
    decidere come segnalare un fallimento. Restituisce False anche quando
    l'integrazione non è configurata.
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
