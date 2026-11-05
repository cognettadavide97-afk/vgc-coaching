# CLAUDE.md

## Comandi

```bash
./venv/Scripts/python.exe -m pytest     # suite completa, copertura di backend/
./venv/Scripts/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Sempre dalla radice del repository, **sempre tramite il venv**. Il `python` di sistema è 3.14 e non ha
le dipendenze: `pytest` nudo fallisce con `ModuleNotFoundError: sqlalchemy`. Il venv è **Python 3.11.9**
e non è una scelta locale — `nixpacks.toml` fissa `python311` per il deploy su Railway, quindi è la
stessa minor della produzione. Nessun build: il frontend non ha bundler; le migrazioni girano da sole
all'avvio.

## Orari

Nel database i `DateTime` sono **naive in UTC**. Si converte solo ai bordi, via
`services/timezone_service.py`: uscita pubblica in UTC esplicito, pannello ed email in ora di Roma.
**Non convertire altrove.**

## NON TOCCARE SENZA CHIEDERE

Gli interventi si chiudono spuntando la voce in `PIANO.md` con il riferimento al commit; il dettaglio
di cosa è stato fatto e perché sta nel messaggio di commit, non in un documento. Le motivazioni delle
voci qui sotto sono nell'intervento indicato fra parentesi di `_archivio_audit/PIANO_ANALISI_2026-09.md`:
leggerle prima di intervenire.

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
- `routers/booking.py:178-245` — Google Calendar chiamato dentro la transazione che blocca lo slot,
  senza timeout (R4, interventi 11-12).
- `scheduler.py:35-47` — env var lette a livello di modulo e `BackgroundScheduler()` senza timezone:
  toccarlo sposta l'orario reale di tutti i job (R11/D3, interventi 13/17).
- `routers/admin/__init__.py` — `get_admin` e l'import dei sotto-router in fondo (D1/D2, 15/16).
- `tests/conftest.py` — due cose che rendono la suite diversa da come sembra: il listener
  `PRAGMA foreign_keys=ON` allinea SQLite a MySQL sui vincoli, e la fixture autouse
  `integrazioni_esterne_finte` sostituisce con no-op **dieci** funzioni di Calendar, email e Discord —
  una suite verde non dice quindi nulla su quelle tre integrazioni. E nemmeno con il `PRAGMA` attivo
  una suite verde dimostra che il codice funzioni su **MySQL**: collation, bulk delete e locking di
  riga restano diversi, e lo sviluppo locale ha un MySQL vero su cui provare.
- **I commenti didattici spiegano il *perché*: non rimuoverli.** Non sono rumore da ripulire in un
  refactor — sono il solo posto in cui vivono le ragioni di metà delle voci qui sopra.
- Costanti duplicate backend/frontend: `TABELLA_PREZZI`/`data-price`, `ORE_INIZIO_VALIDE_2H`
  (R9/R10, interventi 22-23).

## Regole di lavoro

- Prima di modificare codice, **descrivi il piano e attendi conferma esplicita**.
- Dopo ogni modifica, **esegui la suite e mostra l'output reale** del comando.
