# CLAUDE.md

## Comandi

```bash
./venv/Scripts/python.exe -m pytest     # suite completa, copertura di backend/
./venv/Scripts/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Sempre dalla radice del repository, **sempre tramite il venv**: il `python` di sistema è 3.14 e non ha le
dipendenze (`pytest` nudo fallisce con `ModuleNotFoundError: sqlalchemy`). Il venv è **Python 3.11.9**, la
stessa minor che `nixpacks.toml` fissa per il deploy su Railway. Nessun build: il frontend non ha bundler;
le migrazioni girano da sole all'avvio.

**Ogni push su `master` va in produzione su Railway, se i test della CI passano** ("Wait for CI" attivo dal 2026-11-11; deployment verificati su GitHub il 2026-11-09): prima
di pushare, `git log origin/master..master` dice cosa parte. Dopo 60 giorni senza push GitHub spegne il
monitor di produzione (`monitor.yml`): si riattiva da Actions → Enable workflow, mai con commit finti.

## Orari

Nel database i `DateTime` sono **naive in UTC**. Si converte solo ai bordi, via
`services/timezone_service.py`: uscita pubblica in UTC esplicito, pannello ed email in ora di Roma.
**Non convertire altrove.**

## NON TOCCARE SENZA CHIEDERE

Le motivazioni sono nell'intervento fra parentesi di `_archivio_audit/PIANO_ANALISI_2026-09.md`: leggerle prima.
I documenti cancellati il 2026-09-11, citati da alcuni commenti: `git show 2f912d2:_archivio_docs/<file>`.

- `routers/admin/clients.py` — il `db.flush()` prima dei due bulk delete; toglierlo rompe la FK
  `package_id` su MySQL con un 1451 sull'endpoint del diritto all'oblio (B1, intervento 2).
- `models/slots.py` — `blocked_external`/`blocked_admin` sono l'unico modo per distinguere uno slot
  **bloccato** da uno **prenotato**: entrambi falsi con `is_available` falso significa venduto (B2, 4-5).
- `routers/admin/bookings.py` — le due guardie 409 prima di `libera_slot_prenotazione`: senza, si
  rimette in vendita l'orario del cliente subentrato (B3, intervento 3).
- `services/booking_service.py` — l'id evento si azzera **solo** se Google conferma la cancellazione;
  gli slot si liberano comunque (R5, intervento 7).
- `services/google_oauth_service.py` — chiave di cache `(refresh_token, client_id)` e `raise` sul
  token vuoto: separano Gmail da Drive (R17, intervento 6).
- `routers/booking.py:178-245` — Google Calendar chiamato dentro la transazione che blocca lo slot, fino
  a 60 s (timeout di default) contro i 50 s di attesa di un lock MySQL (R4, interventi 11-12).
- `scheduler.py:35-47` e `:351` — env var lette a livello di modulo e `BackgroundScheduler()` senza
  timezone: toccarlo sposta l'orario reale di tutti i job (R11/D3, interventi 13/17).
- `services/availability_service.py:68` — gli slot delle regole si generano solo fino a fine mese
  corrente: a fine mese il calendario è quasi vuoto. È voluto (intervento 38).
- `routers/admin/__init__.py` — `get_admin` e l'import dei sotto-router in fondo (D1/D2, 15/16).
- `tests/conftest.py` — il listener `PRAGMA foreign_keys=ON` allinea SQLite a MySQL sui vincoli, ma
  collation, bulk delete e locking di riga restano diversi: si prova sul MySQL locale. La fixture autouse
  `integrazioni_esterne_finte` sostituisce con no-op **dieci** funzioni di Calendar, email e Discord, solo
  nei tre router pubblici, mentre il `.env` vero si carica all'import: una suite verde non dice nulla su
  quelle integrazioni. Lo schema dei test nasce da `create_all`, non dalle migrazioni.
- **I commenti didattici spiegano il *perché*: non rimuoverli.** Non sono rumore da ripulire in un
  refactor — sono il solo posto in cui vivono le ragioni di metà delle voci qui sopra.
- Costanti duplicate backend/frontend: `TABELLA_PREZZI`/`data-price`, `ORE_INIZIO_VALIDE_2H` (R9/R10, 22-23).

## Regole di lavoro

- Prima di modificare codice, **descrivi il piano e attendi conferma esplicita**.
- Dopo ogni modifica, **esegui la suite e mostra l'output reale** del comando.
