# CLAUDE.md

App di prenotazione per sessioni di coaching VGC: il pubblico sceglie uno slot e prenota (login
Discord opzionale), il coach gestisce disponibilità, prenotazioni, clienti, pacchetti e recensioni da
un pannello admin. Backend FastAPI + MySQL, frontend statico servito dallo stesso processo.

## Comandi

```bash
pip install -r requirements-dev.txt                    # runtime + test (include requirements.txt)
uvicorn backend.main:app --host 0.0.0.0 --port 8000    # avvio (in prod: --port $PORT)
pytest                                                 # 186 test, copertura di backend/ di default
```

Sempre dalla radice del repository. Nessun build: il frontend non ha bundler né `package.json`; le
migrazioni girano da sole all'avvio del server.

## Architettura

`backend/main.py` costruisce l'app, applica le migrazioni Alembic all'avvio (con backup preventivo, e un
errore **non** blocca l'avvio) e avvia lo scheduler. Monta 7 router (`slots`, `booking`, `users`,
`consulenza`, `pacchetti_richieste`, `discord_auth` e `admin/` con 6 sotto-router sotto `/admin`) che
validano con gli schemi Pydantic di `backend/schemas/`, leggono e scrivono gli 8 model SQLAlchemy di
`backend/models/` e delegano a `backend/services/` (timezone, disponibilità, auth, email, calendario,
backup, retention): i router chiamano i servizi, i servizi non importano i router. `scheduler.py` esegue
8 job periodici sugli stessi servizi, ognuno con sessione DB propria; `frontend/` è JS vanilla su
`/static` e parla col backend solo via HTTP (all'esterno: Gmail, Drive, Calendar, Discord).

## Convenzioni e vincoli non negoziabili

- **Italiano** per nomi, docstring e commenti. I commenti didattici spiegano *perché*: non rimuoverli.
- **Orari**: nel DB `DateTime` naive in UTC; si converte solo ai bordi via `timezone_service.py` (uscita
  pubblica in UTC esplicito, pannello ed email in ora di Roma). Non convertire altrove.
- **I servizi verso l'esterno non propagano eccezioni**: catturano, loggano e restituiscono
  `None`/`False`/lista vuota. Chi li chiama non può contare su un `try/except`.
- **Il prezzo lo decide il server** (`routers/booking.py`, `TABELLA_PREZZI`), mai il client.
- **Percorsi relativi** (`alembic.ini`, `frontend/`, gli HTML): avviato altrove, il processo parte e serve 404.
- **Env**: solo `DATABASE_URL` è fatale se manca, il resto degrada in silenzio; aggiornare `.env.example`.
- **Migrazioni**: catena lineare, mai rami; ogni modifica ai model richiede una nuova revisione.
- **I test girano su SQLite in memoria**, senza chiavi esterne e con confronti case-sensitive, mentre la
  produzione è MySQL: una suite verde non dimostra che il codice funzioni su MySQL.

## NON TOCCARE SENZA CHIEDERE

Punti fragili censiti in `PROBLEMI.md`; leggere la voce prima di intervenire.

- `routers/admin/clients.py:115-132` — `db.delete` pendenti + bulk delete rompono la FK `package_id` su MySQL (B1).
- `blocked_external`/`blocked_admin` scritti **solo** a `True`: uno slot bloccato non è sbloccabile né
  eliminabile, riaprirlo è una decisione di prodotto (B2).
- `routers/admin/bookings.py:105-120` — `aggiorna_stato` non è una macchina a stati: libera lo slot di un altro cliente (B3).
- `routers/booking.py:178-245` — Google Calendar chiamato dentro la transazione che blocca lo slot, senza timeout (R4).
- `services/booking_service.py:20-22` — l'id evento è azzerato anche se Google non l'ha cancellato (R5).
- Costanti duplicate backend/frontend: `TABELLA_PREZZI`/`data-price` (R9), `ORE_INIZIO_VALIDE_2H` (R10).
- `scheduler.py:35-47` — env var lette a livello di modulo e `BackgroundScheduler()` senza timezone:
  toccarlo sposta l'orario reale di tutti i job (R11, D3).
- `routers/admin/__init__.py` — `get_admin` e l'import dei sotto-router in fondo: la catena
  `booking → users → admin → 6 sotto-router` si percorre a ogni import (D1, D2).
- `services/google_oauth_service.py:23,33-42` — cache indicizzata solo sul refresh token (R17).
- `tests/conftest.py` — `PRAGMA foreign_keys=ON` è corretto ma fa emergere difetti oggi invisibili.

## Regole di lavoro
- Prima di modificare codice, descrivi il piano e attendi conferma esplicita.
- Una modifica per volta. Non raggruppare interventi non correlati.
- Dopo ogni modifica, esegui la suite di test e mostra l'output reale.
- Se un'istruzione di questo file contraddice il codice, segnalalo invece di adeguarti.