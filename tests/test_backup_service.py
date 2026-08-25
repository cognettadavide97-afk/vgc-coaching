# Copre l'orchestrazione di backend/services/backup_service.py
# (esegui_backup_database): quando salta il backup per configurazione
# mancante, quando lo esegue con successo, quando fallisce a metà.
#
# NON copre crea_dump_sql (la generazione vera del dump SQL): usa sintassi
# specifica di MySQL (SHOW TABLES, SHOW CREATE TABLE), che SQLite — il
# database usato da questa suite (vedi tests/conftest.py) — non supporta.
# È stata verificata manualmente contro il MySQL locale di sviluppo
# (schema + dati + escaping di un valore con apice, es. "O'Brien",
# controllati a mano), non con un test automatico: portare la suite a
# dipendere da un vero server MySQL avrebbe rotto la promessa di
# tests/conftest.py di poter girare "ovunque, anche in CI, senza un server
# MySQL disponibile".

import backend.services.backup_service as backup_service


def test_backup_senza_folder_id_configurato_salta_e_restituisce_false(monkeypatch):
    monkeypatch.setattr(backup_service, "DRIVE_FOLDER_ID", None)

    risultato = backup_service.esegui_backup_database(engine=None)

    assert risultato is False


def test_backup_completo_chiama_dump_upload_e_pulizia(monkeypatch):
    monkeypatch.setattr(backup_service, "DRIVE_FOLDER_ID", "cartella-finta")
    monkeypatch.setattr(backup_service, "DRIVE_REFRESH_TOKEN", "token-finto")

    chiamate = {}
    monkeypatch.setattr(backup_service, "crea_dump_sql", lambda engine: "-- dump finto")
    monkeypatch.setattr(backup_service, "_get_drive_service", lambda: "servizio-finto")
    monkeypatch.setattr(
        backup_service, "_carica_su_drive",
        lambda servizio, contenuto, nome_file: chiamate.update(
            servizio=servizio, contenuto=contenuto, nome_file=nome_file
        )
    )
    monkeypatch.setattr(
        backup_service, "_elimina_backup_scaduti",
        lambda servizio: chiamate.update(pulizia_eseguita=True)
    )

    risultato = backup_service.esegui_backup_database(engine="engine-finto")

    assert risultato is True
    assert chiamate["contenuto"] == "-- dump finto"
    assert chiamate["nome_file"].startswith("vgc-coaching-backup-")
    assert chiamate["nome_file"].endswith(".sql")
    assert chiamate["pulizia_eseguita"] is True


def test_backup_fallito_a_meta_restituisce_false_senza_sollevare(monkeypatch):
    # Se crea_dump_sql fallisce (es. connessione al database persa a metà
    # backup), esegui_backup_database non deve propagare l'eccezione: il
    # chiamante (backend/scheduler.py) si aspetta un booleano, non un
    # crash che fermerebbe l'intero scheduler.
    monkeypatch.setattr(backup_service, "DRIVE_FOLDER_ID", "cartella-finta")
    monkeypatch.setattr(backup_service, "DRIVE_REFRESH_TOKEN", "token-finto")
    monkeypatch.setattr(backup_service, "crea_dump_sql", lambda engine: (_ for _ in ()).throw(RuntimeError("connessione persa")))

    risultato = backup_service.esegui_backup_database(engine="engine-finto")

    assert risultato is False
