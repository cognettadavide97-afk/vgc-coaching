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
- `routers/booking.py:277-317` — l'evento Google Calendar si crea **dopo** il commit e le notifiche: dentro la
  transazione teneva il lock su slot e credito fino a 60 s contro i 50 s di attesa di MySQL, e chi prenotava lo
  stesso slot riceveva un 500 (R4, voci 11-12, provato sul MySQL locale). L'id si salva solo se la prenotazione
  è ancora `confirmed`, altrimenti l'evento si elimina: una cancellazione arrivata durante la chiamata non lo trova.
- `scheduler.py:38-48` e `:399` — env var lette a livello di modulo e `BackgroundScheduler(job_defaults=...)`
  senza timezone: toccarlo sposta l'orario reale di tutti i job (R11/D3, interventi 13/17).
  `TOLLERANZA_RITARDI` (`misfire_grace_time=None`) fa partire in ritardo invece di saltare: con il default di
  1 s un avviso di `sorveglia_job` farebbe saltare gli altri job (voce 47).
- `routers/admin/__init__.py` — `get_admin` e l'import dei sotto-router in fondo (D1/D2, 15/16).
- `tests/conftest.py` — il listener `PRAGMA foreign_keys=ON` allinea SQLite a MySQL sui vincoli, ma
  collation, bulk delete e locking di riga restano diversi: si prova sul MySQL locale. Le righe in cima,
  **prima di ogni import del backend**, svuotano le 11 credenziali delle integrazioni e puntano
  `DATABASE_URL` a SQLite: spostate dopo gli import non hanno più effetto. La fixture `rete_esterna_bloccata`
  fa fallire ogni connessione fuori dal loopback (voce 51). Le undici funzioni no-op di
  `integrazioni_esterne_finte` restano solo per log puliti: una suite verde non dice nulla su quelle
  integrazioni. `agenda_google_vuota` e `orizzonte_aperto` invece servono al funzionamento (4.4): senza,
  ogni prenotazione dei test darebbe 503 o cadrebbe fuori orizzonte. Lo schema dei test nasce da
  `create_all`, non dalle migrazioni.
- **I commenti didattici spiegano il *perché*: non rimuoverli.** Non sono rumore da ripulire in un
  refactor — sono il solo posto in cui vivono le ragioni di metà delle voci qui sopra.
- Costanti duplicate backend/frontend: `TABELLA_PREZZI`/`data-price` (R9/R10, 22-23).

## Regole di lavoro

- Prima di modificare codice, **descrivi il piano e attendi conferma esplicita**.
- Dopo ogni modifica, **esegui la suite e mostra l'output reale** del comando.
