# AUDIT

Audit ricavato **solo dal codice eseguito**. Non sono stati usati come fonte: README, documenti di
progetto, commenti che dichiarano intenzioni, nomi di file o di funzione. I file di configurazione
(`nixpacks.toml`, `pytest.ini`, `alembic.ini`, `requirements*.txt`, `.github/workflows/*.yml`) sono
stati letti come dichiarazioni eseguite, per la sola sezione **Comandi**.

**Perimetro letto per intero**: `backend/` (45 file), `alembic/env.py` + le 18 revisioni,
`scripts/`, i file di configurazione, `frontend/js/*.js` e i tag `<script>`/`<link>` dei cinque HTML.
**Fuori perimetro** (dichiarato, non "non verificato"): `tests/` — letto solo `tests/conftest.py` per
la sezione Comandi — `frontend/css/`, il corpo degli HTML, le immagini e i font.

Dove il comportamento non è determinabile leggendo il codice, la voce è marcata **NON VERIFICATO**;
l'elenco completo è nella sezione finale.

---

## 1. Punto di ingresso

Il processo si avvia caricando `backend.main:app` (`nixpacks.toml:5`). Il modulo distingue due
momenti: ciò che accade all'**import** e ciò che accade all'**avvio del server**.

### 1.1 All'import di `backend/main.py`

In ordine di esecuzione:

1. `logging.basicConfig` con livello letto da `LOG_LEVEL` (default `"INFO"`) e formato fisso —
   `backend/main.py:21-23`. Avviene **prima** degli import del progetto (`backend/main.py:25-53`).
2. `from backend.rate_limit import limiter` (`backend/main.py:36`) → costruisce il `Limiter` con
   `key_func=get_remote_address` (`backend/rate_limit.py:12`).
3. `from backend.scheduler import avvia_scheduler` (`backend/main.py:37`) → l'import di
   `backend/scheduler.py` legge otto variabili d'ambiente a livello di modulo
   (`backend/scheduler.py:35-47`) e importa a catena tutti i servizi (`backend/scheduler.py:27-33`).
4. Import dei sette router (`backend/main.py:39-45`).
5. `from backend.database import engine, get_db` (`backend/main.py:51`) → `backend/database.py` esegue
   `load_dotenv()` (`backend/database.py:13`), legge `DATABASE_URL` e **solleva `RuntimeError` se
   manca** (`backend/database.py:15-20`), poi costruisce `engine` con `pool_pre_ping=True`
   (`backend/database.py:26`), `SessionLocal` (`:28`) e `Base` (`:30`).
6. `app = FastAPI(..., lifespan=lifespan)` — `backend/main.py:129`.
7. Registrazione del rate limiter: stato sull'app, handler per `RateLimitExceeded`, middleware —
   `backend/main.py:133-135`.
8. CORS: origini da `FRONTEND_ORIGINS` con default
   `"http://127.0.0.1:8000,http://localhost:8000"` spezzato sulle virgole (`backend/main.py:141-144`),
   metodi `GET, POST, PATCH, DELETE`, header `Authorization` e `Content-Type`
   (`backend/main.py:146-151`). `allow_credentials` non è passato.
9. Montaggio dei sette router (`backend/main.py:153-159`) e dello static su `/static` dalla directory
   relativa `frontend` (`backend/main.py:162`).
10. Registrazione delle rotte `/health` (`backend/main.py:172`), `/` (`:188`), `/about` (`:192`),
    `/privacy` (`:196`), `/admin-panel` (`:200`).

Nessuna query al database e nessuna chiamata di rete viene eseguita in questa fase dal codice del
progetto.

### 1.2 All'avvio del server (`lifespan`)

`backend/main.py:111-126`, in ordine:

1. `run_migrations()` (`backend/main.py:121` → `:72-108`):
   - rilegge `DATABASE_URL` (`:87`); se manca, logga un warning e **salta le migrazioni** (`:99-100`);
   - costruisce `Config("alembic.ini")` — percorso relativo — e vi sovrascrive `sqlalchemy.url`
     (`:89-90`);
   - `_migrazioni_in_sospeso()` (`:58-69`) apre una connessione (`:66`) e confronta la revisione
     corrente del database con la head degli script; se differiscono chiama
     `esegui_backup_database(engine)` e prosegue anche se fallisce (`:92-95`);
   - `command.upgrade(alembic_cfg, "head")` (`:97`);
   - qualsiasi eccezione viene loggata e notificata con `invia_alert_sistema(...)`, **senza
     interrompere l'avvio** (`:101-108`).
2. `avvia_scheduler()` (`backend/main.py:122` → `backend/scheduler.py:344-437`): registra otto job su
   un `BackgroundScheduler` e lo avvia.
3. `yield`; alla chiusura, `scheduler.shutdown()` (`backend/main.py:126`).

### 1.3 Ingresso del frontend

Non c'è un bundler né un entrypoint JS unico: ogni pagina carica direttamente i propri script.
`frontend/index.html:444-445` carica `i18n.js` poi `app.js`; `frontend/about.html:109-110` carica
`i18n.js` e `about.js`; `frontend/privacy.html:102` solo `i18n.js`; `frontend/recensione.html:59` solo
`recensione.js`; `frontend/admin.html:303` solo `admin.js` (nessun `i18n.js`).

---

## 2. Mappa dei moduli

Per "chi lo chiama" sono stati usati gli import effettivi (`from backend...` / `import backend...`),
non l'assonanza dei nomi.

### 2.1 Infrastruttura

| File | Responsabilità osservata | Esporta | Chi lo importa |
|---|---|---|---|
| `backend/main.py` | Costruzione dell'app, migrazioni all'avvio, avvio scheduler, rotte pagina e `/health` | `app` (`:129`), `lifespan` (`:112`), `run_migrations` (`:72`), `_migrazioni_in_sospeso` (`:58`), `health` (`:173`), `root`/`about`/`privacy`/`admin_panel` (`:189,193,197,201`) | Nessun modulo di `backend/`; è caricato da uvicorn (`nixpacks.toml:5`) e da `tests/conftest.py:27` |
| `backend/database.py` | Connessione, factory di sessioni, `Base`, dependency di sessione | `engine` (`:26`), `SessionLocal` (`:28`), `Base` (`:30`), `get_db` (`:33`) | `main.py:51`, `scheduler.py:23`, tutti i router, tutti i model, `alembic/env.py:15` |
| `backend/rate_limit.py` | Istanza condivisa del limiter per IP | `limiter` (`:12`) | `main.py:36`, `routers/admin/__init__.py:15`, `booking.py:28`, `users.py:24`, `consulenza.py:20`, `pacchetti_richieste.py:21` |
| `backend/scheduler.py` | Otto job periodici, ognuno con sessione DB propria | `controlla_e_invia_promemoria` (`:112`), `controlla_e_invia_richieste_recensione` (`:164`), `controlla_e_sincronizza_calendario` (`:206`), `genera_slot_giornaliero` (`:219`), `pulisci_slot_obsoleti` (`:239`), `controlla_credenziali` (`:252`), `controlla_una_credenziale` (`:272`), `controlla_e_anonimizza_clienti_inattivi` (`:304`), `controlla_e_esegui_backup_database` (`:326`), `avvia_scheduler` (`:344`), `CREDENZIALI_SORVEGLIATE` (`:71`) | `main.py:37` |
| `alembic/env.py` | Configurazione Alembic; in modalità online legge `DATABASE_URL` e la sovrascrive su `alembic.ini` | esegue direttamente `run_migrations_online()` (`:112-115`) | Eseguito da Alembic; raggiunto da `command.upgrade` in `main.py:97` |

Dettagli rilevanti di `alembic/env.py`: `fileConfig` è chiamata solo se il root logger non ha già
handler (`:38-39`); `run_migrations_online` fa `load_dotenv()` (`:82`), solleva `RuntimeError` senza
`DATABASE_URL` (`:86-88`), usa `NullPool` (`:98`) e racchiude le migrazioni in una sola transazione
(`:108-109`).

### 2.2 Model (SQLAlchemy)

`backend/models/__init__.py:9-16` importa le otto classi. `alembic/env.py:14` importa da qui sei nomi
e usa `Base.metadata` come `target_metadata` (`alembic/env.py:19`).

| Model | Tabella | Colonne (righe) | Note dal codice |
|---|---|---|---|
| `User` (`models/users.py:8`) | `users` | `id, nome, email(unique), telefono, categoria, discord_tag, discord_id(unique), created_at, anonimizzato_at` — `:11-37` | `email` unica a livello DB (`:17`); `anonimizzato_at` scritto solo da `retention_service.py:55` |
| `Slot` (`models/slots.py:11`) | `slots` | `id, start_time(index), duration_hours, is_available, blocked_external, blocked_admin, created_at` — `:14-36` | `start_time` indicizzato (`:23`) |
| `Booking` (`models/booking.py:13`) | `bookings` | `id, user_id, slot_id, slot_id_secondario, duration_hours, price_cents, service_type, status(index), note_cliente, note_admin, vod_link, replay_code, calendar_event_id, reminder_sent, package_id, review_token(unique), review_email_sent, created_at` — `:16-55` | Due FK verso `slots` (`:19,24`) → relazioni con `foreign_keys` esplicito (`:62-63`) |
| `Package` (`models/package.py:14`) | `packages` | `id, user_id, tipo, sessioni_totali, sessioni_usate, durata_sessione_ore, prezzo_cents, created_at` — `:17-34` | |
| `Review` (`models/review.py:9`) | `reviews` | `id, booking_id(unique), voto, commento, approvata, created_at` — `:12-24` | `booking_id` unique → una recensione per prenotazione (`:15`) |
| `ClientNote` (`models/client_note.py:13`) | `client_notes` | `id, user_id, nota, created_at` — `:16-19` | |
| `AvailabilityRule` (`models/availability_rule.py:12`) | `availability_rules` | `id, giorno_settimana, ora_inizio, ora_fine, durata_slot_ore, attiva, created_at` — `:15-34` | `attiva` non è scritta da nessun endpoint: `AvailabilityRuleCreate` non la contiene (`schemas/availability.py:8-12`) e il router non la valorizza (`routers/admin/availability.py:134-139`); è letta solo da `scheduler.py:230` |
| `AvailabilityException` (`models/availability_exception.py:12`) | `availability_exceptions` | `id, data_inizio, data_fine, motivo, created_at` — `:15-23` | Colonne `Date`, non `DateTime` (`:19-20`) |

### 2.3 Migrazioni

18 revisioni in `alembic/versions/`, catena lineare senza rami ricostruita dai campi
`revision`/`down_revision`:

`1972ef07e768` (base, `down_revision = None`, riga 16) → `a4568987d2e7` → `d1af2a35c949` →
`98489ff817ea` → `37a82dbead86` → `f56a5f50b503` → `dcfea9cf2bb0` → `60a355bf4f97` → `cc755d0d6a6b` →
`17c843945785` → `0bfc529cd9fd` → `a1c92f7e4b18` → `b3d84a19e6f2` → `c5f612a8d9e3` → `d4a72e0f8b31` →
`a1b2c3d4e5f6` → `215aa000de4b` → **`2eac6f32b19b` (head)**.

`2eac6f32b19b` è head perché nessun file la dichiara come `down_revision`; il suo `upgrade()` aggiunge
`users.anonimizzato_at` (`alembic/versions/2eac6f32b19b_aggiungi_anonimizzato_at_a_users.py:24`).

### 2.4 Router

| File | Prefisso | Chi lo importa |
|---|---|---|
| `routers/slots.py` | `/slots` (`:17`) | `main.py:39` |
| `routers/booking.py` | `/bookings` (`:33`) | `main.py:40` |
| `routers/users.py` | `/users` (`:27`) | `main.py:41`; `get_or_create_user` da `consulenza.py:14` e `pacchetti_richieste.py:14`; `get_studente`/`get_studente_opzionale` da `booking.py:27`; `STUDENT_TOKEN_COOKIE` da `discord_auth.py:23` |
| `routers/admin/__init__.py` | `/admin` (`:17`) | `main.py:42`; `get_admin` importato da tutti i sotto-router e da `slots.py:12`, `users.py:20` |
| `routers/discord_auth.py` | `/auth/discord` (`:28`) | `main.py:43` |
| `routers/consulenza.py` | `/consulenze` (`:22`) | `main.py:44` |
| `routers/pacchetti_richieste.py` | `/pacchetti-richieste` (`:23`) | `main.py:45` |
| `routers/admin/{dashboard,bookings,clients,availability,packages,reviews}.py` | nessuno (`APIRouter()` senza prefix), inclusi in `/admin` da `routers/admin/__init__.py:63-68` | `routers/admin/__init__.py:61` (import in fondo al file, dopo la definizione di `get_admin`) |

`get_admin` (`routers/admin/__init__.py:23-37`) legge il token via `OAuth2PasswordBearer` (`:20`),
chiama `verifica_token` e solleva 401 se il token non è valido.
`get_studente_opzionale` (`routers/users.py:35-49`) legge il cookie `student_token` (`:32`), verifica
il token e carica l'utente; `get_studente` (`:52-56`) trasforma l'assenza in 401.

### 2.5 Schemi Pydantic

| File | Classi | Note dal codice |
|---|---|---|
| `schemas/slots.py` | `SlotCreate` (`:13`), `SlotResponse` (`:60`) | `duration_hours` deve valere 1, altrimenti `ValueError` (`:39-44`); `start_time` senza fuso viene interpretato come ora di Roma e convertito in UTC naive (`:46-57`); in uscita `start_time` è serializzato con offset UTC esplicito (`:68-78`) |
| `schemas/booking.py` | `BookingCreate` (`:12`), `BookingResponse` (`:46`), `BookingStatoUpdate` (`:65`), `BookingNoteUpdate` (`:71`), `BookingResponseStudente` (`:77`) | Nessun campo prezzo in ingresso (`:19-43`); `duration_hours: Literal[1,2]` (`:34`); `service_type` ristretto a quattro valori (`:9`); `BookingResponseStudente` non contiene `note_admin` (`:83-95`) |
| `schemas/users.py` | `UserCreate` (`:15`), `UserIdResponse` (`:24`), `UserResponse` (`:37`) | `email: EmailStr` (`:18`); `categoria` ristretta a junior/senior/master (`:12`) |
| `schemas/review.py` | `ReviewCreate` (`:8`), `ReviewResponse` (`:14`), `ReviewApprovazione` (`:25`), `ReviewPubblica` (`:29`) | `voto` vincolato 1..5 (`:10`) |
| `schemas/availability.py` | `AvailabilityRuleCreate` (`:8`), `AvailabilityRuleResponse` (`:37`), `AvailabilityExceptionCreate` (`:49`), `AvailabilityExceptionResponse` (`:55`) | `giorno_settimana` 0..6 (`:14-19`); `durata_slot_ore` deve valere 1 (`:21-34`) |
| `schemas/package.py` | `PackageCreate` (`:10`), `PackageResponse` (`:20`) | In ingresso solo `user_id` e `tipo` (`:16-17`) |
| `schemas/consulenza.py` | `ConsulenzaCreate` (`:11`) | Solo schema di ingresso |
| `schemas/pacchetto_richiesta.py` | `PacchettoRichiestaCreate` (`:13`) | `tipo` ristretto a intro/team/tour (`:10`) |
| `schemas/client_note.py` | `ClientNoteCreate` (`:7`), `ClientNoteResponse` (`:13`) | `user_id` non è nel corpo |

### 2.6 Servizi

| File | Responsabilità osservata | Esporta | Chi lo importa |
|---|---|---|---|
| `services/auth_service.py` | bcrypt + JWT, due tipi di token distinti dal claim `type` | `verifica_credenziali` (`:29`), `crea_token` (`:39`), `crea_token_studente` (`:54`), `verifica_token` (`:80`), `verifica_token_studente` (`:91`), `EXPIRE_MINUTES` (`:21`) | `routers/admin/__init__.py:14`, `users.py:21`, `discord_auth.py:22` |
| `services/timezone_service.py` | Conversioni UTC↔Roma e confronto intervalli | `ROME_TZ` (`:17`), `utc_to_rome` (`:20`), `formatta_data_ora_rome` (`:34`), `ora_utc_naive` (`:45`), `intervalli_si_sovrappongono` (`:55`) | `auth_service.py:15`, `availability_service.py:15`, `calendar_service.py:21`, `retention_service.py:13`, `schemas/slots.py:10`, `scheduler.py:29`, `booking.py:23`, `slots.py:14`, `users.py:22`, i quattro router admin |
| `services/availability_service.py` | Generazione slot da regola, sovrapposizioni, blocchi, pulizia | `slot_si_sovrappone` (`:18`), `genera_slot_da_regola` (`:45`), `elimina_slot_obsoleti` (`:109`), `applica_blocco_eccezionale` (`:143`) | `slots.py:13`, `routers/admin/availability.py:22`, `scheduler.py:31` |
| `services/booking_service.py` | Effetti della cancellazione: elimina evento calendario e rilibera gli slot, **senza commit** (`:13-31`) | `libera_slot_prenotazione` (`:13`) | `booking.py:26`, `routers/admin/bookings.py:13`, `routers/admin/clients.py:14` |
| `services/package_service.py` | Catalogo statico dei pacchetti con sessioni, durata e prezzi (`:7-29`) | `CATALOGO_PACCHETTI` (`:7`) | `users.py:23`, `routers/admin/packages.py:10`, `pacchetti_richieste.py:15` |
| `services/pagination_service.py` | Clamp dei parametri (`per_pagina` max 100, `:14`) e busta di risposta (`:19-29`) | `pagina_e_offset` (`:6`), `busta_paginazione` (`:19`) | `routers/admin/{bookings,clients,availability}.py` |
| `services/retention_service.py` | Anonimizzazione dei clienti inattivi | `anonimizza_clienti_inattivi` (`:23`), `RETENTION_MONTHS` (`:15`), `SUFFISSO_EMAIL_ANONIMIZZATA` (`:20`) | `scheduler.py:32` |
| `services/google_oauth_service.py` | Costruzione credenziali OAuth con cache per refresh token (`:23-47`) e sonda comune (`:50-85`) | `credenziali_oauth_google` (`:26`), `verifica_credenziali_google` (`:50`) | `email_service.py:19`, `backup_service.py:28`, `calendar_service.py:18` |
| `services/email_service.py` | Composizione HTML e invio via API Gmail | `_invia_via_gmail` (`:81`), `verifica_credenziali_gmail` (`:101`), `invia_conferma_cliente` (`:114`), `invia_promemoria_cliente` (`:155`), `invia_notifica_admin` (`:193`), `invia_conferma_richiesta_consulenza` (`:227`), `invia_notifica_richiesta_consulenza_admin` (`:249`), `invia_conferma_richiesta_pacchetto` (`:271`), `invia_notifica_richiesta_pacchetto_admin` (`:293`), `invia_richiesta_recensione` (`:316`) | `booking.py:22`, `consulenza.py:15`, `pacchetti_richieste.py:16`, `scheduler.py:27` |
| `services/discord_service.py` | Invio di embed a un webhook, timeout 5 s (`:47`) | `invia_notifica_discord` (`:54`), `invia_promemoria_discord` (`:84`), `invia_richiesta_consulenza_discord` (`:104`), `invia_alert_sistema` (`:128`), `invia_richiesta_pacchetto_discord` (`:142`), `SERVICE_LABELS` (`:25`) | `main.py:52`, `booking.py:25`, `consulenza.py:19`, `pacchetti_richieste.py:20`, `scheduler.py:28` |
| `services/calendar_service.py` | Google Calendar via service account | `get_calendar_service` (`:48`), `verifica_credenziali_calendario` (`:53`), `crea_evento_calendario` (`:75`), `leggi_eventi_calendario` (`:142`), `sincronizza_slot_con_calendario` (`:191`), `elimina_evento_calendario` (`:234`) | `booking.py:24`, `booking_service.py:10`, `routers/admin/availability.py:20`, `scheduler.py:30` |
| `services/backup_service.py` | Dump SQL in Python, upload su Drive, pulizia dei backup scaduti | `verifica_credenziali_drive` (`:49`), `crea_dump_sql` (`:73`), `esegui_backup_database` (`:156`) | `main.py:53`, `scheduler.py:33` |

Comportamento comune ai servizi verso l'esterno: nessuno propaga eccezioni.
`calendar_service` cattura e restituisce `None`/lista vuota (`:137-139`, `:186-188`, `:243-244`);
`email_service` cattura in ogni funzione di invio (es. `:151-152`); `discord_service` salta l'invio se
il webhook non è configurato (`:39-41`) e cattura ogni errore (`:50-51`); `backup_service` restituisce
`False` (`:163-165`, `:177-179`).

### 2.7 Script

| File | Cosa esegue | Punto di ingresso |
|---|---|---|
| `scripts/_env_utils.py` | Riscrittura di una variabile nel `.env` locale, o append se assente (`:24-39`) | Importato da `hash_admin_password.py:23`, `reauth_gmail.py:38`, `reauth_drive.py:31` |
| `scripts/hash_admin_password.py` | Chiede la password con `getpass` (`:28-29`), genera hash bcrypt (`:41`), propone di scriverlo nel `.env` (`:46-48`); sostituisce una eventuale riga `ADMIN_PASSWORD=` (`:71-83`) | `main()` sotto `__main__` (`:88-89`) |
| `scripts/reauth_gmail.py` | `InstalledAppFlow` con scope `gmail.send` (`:53`, `:79-86`), stampa il refresh token, aggiorna `GMAIL_REFRESH_TOKEN` nel `.env` (`:111-112`) | `:115-116` |
| `scripts/reauth_drive.py` | Come sopra con scope `drive.file` (`:46`), aggiorna `DRIVE_REFRESH_TOKEN` (`:96-97`); usa lo stesso `GMAIL_CLIENT_ID/SECRET` (`:48-49`) | `:100-101` |

### 2.8 Frontend

| File | Responsabilità osservata | Endpoint chiamati |
|---|---|---|
| `frontend/js/i18n.js` | Dizionario it/en (`:13-285`), `t` (`:294`), `tf` (`:300`), `applyTranslations` (`:310`), `setLang` (`:326`) che salva `lang` in `localStorage` (`:328`) ed emette l'evento `langchange` (`:333`) | nessuno |
| `frontend/js/app.js` | Wizard di prenotazione in tre step, login Discord opzionale, form consulenza e pacchetti | `GET /users/me` (`:102`), `GET /users/me/prenotazioni` (`:154`), `PATCH /bookings/{id}/cancella` (`:196`), `POST /auth/discord/logout` (`:225`), `GET /slots/` (`:291`), `GET /users/pacchetti-attivi` (`:421`), `POST /users/` (`:491`), `POST /bookings/` (`:515`), `POST /consulenze/` (`:570`), `POST /pacchetti-richieste/` (`:625`) |
| `frontend/js/admin.js` | Pannello admin completo; il token JWT vive **solo in memoria** (`:12`, azzerato da `logout()` `:139-143`) e viaggia in `Authorization: Bearer` (`:147-152`) | 26 chiamate, elencate nella tabella §2.9 |
| `frontend/js/about.js` | Vetrina recensioni approvate (`:12-39`), invocata all'ultima riga (`:41`) | `GET /bookings/recensioni/pubbliche` (`:17`) |
| `frontend/js/recensione.js` | Legge `booking_id` e `token` dalla query string (`:5-7`), invia la recensione (`:42`), blocca il form se i parametri mancano (`:65-67`) | `POST /bookings/{id}/recensione` (`:42`) |

### 2.9 Inventario degli endpoint HTTP

Autenticazione: **pubblico** = nessuna dependency; **admin** = `Depends(get_admin)` (JWT `type=admin`
in header `Authorization`); **studente** = cookie `student_token` (JWT `type=student`);
**studente opz.** = `get_studente_opzionale`; **token in corpo** = confronto con `Booking.review_token`.

| Metodo | Path | Auth | Rate limit | Definito in | Chiamato dal frontend |
|---|---|---|---|---|---|
| GET, HEAD | `/health` | pubblico | — | `main.py:172` | `.github/workflows/monitor.yml:48` |
| GET | `/` | pubblico | — | `main.py:188` | — |
| GET | `/about` | pubblico | — | `main.py:192` | — |
| GET | `/privacy` | pubblico | — | `main.py:196` | — |
| GET | `/admin-panel` | pubblico | — | `main.py:200` | — |
| GET | `/static/*` | pubblico | — | `main.py:162` | tutti gli HTML |
| GET | `/slots/` | pubblico | — | `slots.py:20` | `app.js:291` |
| POST | `/slots/` | admin | — | `slots.py:50` | `admin.js:1095` |
| POST | `/users/` | pubblico | 5/min (`users.py:133`) | `users.py:129` | `app.js:491` |
| GET | `/users/` | admin | — | `users.py:59` | — |
| GET | `/users/me` | studente | — | `users.py:64` | `app.js:102` |
| GET | `/users/me/prenotazioni` | studente | — | `users.py:70` | `app.js:154` |
| GET | `/users/pacchetti-attivi` | studente | — | `users.py:140` | `app.js:421` |
| POST | `/bookings/` | studente opz. | 5/min (`booking.py:48`) | `booking.py:47` | `app.js:515` |
| PATCH | `/bookings/{booking_id}/cancella` | studente | — | `booking.py:281` | `app.js:196` |
| GET | `/bookings/recensioni/pubbliche` | pubblico | — | `booking.py:310` | `about.js:17` |
| POST | `/bookings/{booking_id}/recensione` | token in corpo | 5/min (`booking.py:340`) | `booking.py:339` | `recensione.js:42` |
| POST | `/consulenze/` | pubblico | 5/min (`consulenza.py:26`) | `consulenza.py:25` | `app.js:570` |
| POST | `/pacchetti-richieste/` | pubblico | 5/min (`pacchetti_richieste.py:27`) | `pacchetti_richieste.py:26` | `app.js:625` |
| GET | `/auth/discord/login` | pubblico | — | `discord_auth.py:47` | link in `app.js:85` |
| GET | `/auth/discord/callback` | pubblico | — | `discord_auth.py:79` | Discord (redirect) |
| POST | `/auth/discord/logout` | pubblico | — | `discord_auth.py:188` | `app.js:225` |
| POST | `/admin/login` | pubblico (form-urlencoded) | 5/min (`admin/__init__.py:42`) | `admin/__init__.py:40` | `admin.js:112` |
| GET | `/admin/dashboard` | admin | — | `admin/dashboard.py:18` | `admin.js:247` |
| GET | `/admin/analytics` | admin | — | `admin/dashboard.py:79` | `admin.js:308` |
| GET | `/admin/prenotazioni` | admin | — | `admin/bookings.py:22` | `admin.js:345` |
| PATCH | `/admin/prenotazioni/{id}/stato` | admin | — | `admin/bookings.py:92` | `admin.js:432` |
| PATCH | `/admin/prenotazioni/{id}/note` | admin | — | `admin/bookings.py:123` | `admin.js:454` |
| GET | `/admin/export/csv` | admin | — | `admin/bookings.py:140` | `admin.js:1137` |
| GET | `/admin/clienti` | admin | — | `admin/clients.py:22` | `admin.js:469` |
| DELETE | `/admin/clienti/{user_id}` | admin | — | `admin/clients.py:95` | `admin.js:543` |
| GET | `/admin/clienti/{user_id}/note` | admin | — | `admin/clients.py:136` | `admin.js:591` |
| POST | `/admin/clienti/{user_id}/note` | admin | — | `admin/clients.py:151` | `admin.js:618` |
| GET | `/admin/slots` | admin | — | `admin/availability.py:30` | `admin.js:816` |
| POST | `/admin/slots/sync-calendario` | admin | — | `admin/availability.py:62` | `admin.js:877` |
| DELETE | `/admin/slots/{slot_id}` | admin | — | `admin/availability.py:75` | `admin.js:1114` |
| GET | `/admin/disponibilita/regole` | admin | — | `admin/availability.py:110` | `admin.js:898` |
| POST | `/admin/disponibilita/regole` | admin | — | `admin/availability.py:120` | `admin.js:949` |
| DELETE | `/admin/disponibilita/regole/{id}` | admin | — | `admin/availability.py:155` | `admin.js:980` |
| GET | `/admin/disponibilita/blocchi` | admin | — | `admin/availability.py:174` | `admin.js:994` |
| POST | `/admin/disponibilita/blocchi` | admin | — | `admin/availability.py:184` | `admin.js:1044` |
| DELETE | `/admin/disponibilita/blocchi/{id}` | admin | — | `admin/availability.py:213` | `admin.js:1075` |
| GET | `/admin/pacchetti` | admin | — | `admin/packages.py:19` | `admin.js:709` |
| POST | `/admin/pacchetti` | admin | — | `admin/packages.py:27` | `admin.js:685` |
| GET | `/admin/recensioni` | admin | — | `admin/reviews.py:18` | `admin.js:752` |
| PATCH | `/admin/recensioni/{id}` | admin | — | `admin/reviews.py:59` | `admin.js:801` |

`GET /admin-panel` (`main.py:200-202`) restituisce `frontend/admin.html` **senza alcun controllo di
autenticazione**: la protezione è sugli endpoint `/admin/*`, non sulla pagina.

---

## 3. Flusso dei dati

### 3.1 Prenotazione dal sito pubblico

Ingresso: form di `index.html` letto da `app.js`.

1. `app.js:491-501` invia `POST /users/` con `nome`, `email`, `categoria`, `discord_tag`,
   `telefono: null`.
2. `users.py:134-137` → `get_or_create_user` (`users.py:104-126`): cerca per email (`:111`) e, se non
   trova, inserisce e committa (`:115-125`). Risposta ridotta al solo `id`
   (`schemas/users.py:24-34`).
3. `app.js:515-531` invia `POST /bookings/` con `user_id`, `email`, `slot_id`, `duration_hours`,
   `service_type`, `note_cliente`, `vod_link`, `replay_code`, `package_id`. Nessun header di
   autenticazione: il cookie `student_token`, se esiste, viaggia da solo.
4. `booking.py:49-278`, in ordine di esecuzione:
   - validazione Pydantic di `BookingCreate` (durata ∈ {1,2}, `service_type` fra quattro valori);
   - slot esistente (`:58-60`) e non nel passato (`:65-66`);
   - se `duration_hours=2` su slot da 1 h: ora italiana di inizio ∈ {15,17} (`:78-82`), esiste ed è
     libero lo slot dell'ora successiva (`:83-92`);
   - identità: se il cookie identifica uno studente, `user = studente` e i campi del corpo sono
     ignorati (`:110-111`); altrimenti `email` è obbligatoria (`:117-121`), l'utente è caricato per
     `user_id` (`:122`) e l'email deve corrispondere, altrimenti 403 (`:125-126`);
   - pacchetto: richiede il login (`:140-141`), deve appartenere allo studente (`:142-144`), avere
     crediti (`:145-146`) e la durata giusta (`:147-151`);
   - limite di 2 prenotazioni attive per utente (`:31`, `:156-165`);
   - **riserva atomica**: `UPDATE slots SET is_available=0 WHERE id=? AND is_available=1`
     (`:178-182`); `rowcount == 0` → `rollback` e 400 (`:185-187`); stessa cosa per lo slot secondario
     (`:192-200`);
   - prezzo deciso dal server: `0` con pacchetto, altrimenti `TABELLA_PREZZI[durata]` = 2000 o 4000
     centesimi (`:38`, `:205`);
   - **uscita di rete prima del commit**: `crea_evento_calendario(...)` (`:213-221`), che restituisce
     `None` in caso di errore (`calendar_service.py:137-139`);
   - inserimento del `Booking` con `review_token = secrets.token_urlsafe(32)` (`:223-239`),
     incremento `sessioni_usate` del pacchetto (`:242-243`), `commit` (`:245`);
   - **dopo il commit**, tre notifiche: email al cliente (`:250-257`), email a `EMAIL_ADMIN`
     (`:259-266`), embed Discord (`:268-276`).

Destinazioni finali: tabelle `users`, `slots`, `bookings`, `packages`; Google Calendar; API Gmail (due
messaggi); webhook Discord.

### 3.2 Cancellazione self-service

`app.js:196-198` → `PATCH /bookings/{id}/cancella` → `booking.py:282-307`: la prenotazione deve
esistere (`:293-295`), appartenere allo studente (`:296-297`), essere `confirmed` (`:298-299`) e non
essere già passata (`:300-301`). Poi `status="cancelled"` (`:303`) e
`libera_slot_prenotazione` (`:304`), che elimina l'evento sul calendario e azzera
`calendar_event_id` (`booking_service.py:20-22`), rimette `is_available=True` sullo slot principale
(`:24-26`) e sull'eventuale secondario (`:28-31`); commit unico nel router (`:305`).

### 3.3 Login Discord (OAuth2)

1. `GET /auth/discord/login` (`discord_auth.py:47-76`): genera uno `state` casuale (`:57`), redirige a
   `https://discord.com/api/oauth2/authorize` con scope `identify email` (`:59-67`) e imposta il cookie
   `discord_oauth_state`, `httponly`, `samesite=lax`, `max_age=600`, `secure` solo se
   `DISCORD_OAUTH_REDIRECT_URI` inizia con `https://` (`:40`, `:72-75`).
2. `GET /auth/discord/callback` (`:79-185`): confronto costante dello `state` (`:93-97`); scambio del
   codice su `https://discord.com/api/oauth2/token` con timeout 10 s (`:103-116`); lettura del profilo
   su `https://discord.com/api/users/@me` (`:119-125`); ogni eccezione → redirect `/?discord_error=1`
   (`:126-128`).
3. Risoluzione identità: ricerca per `discord_id` (`:148`), fallback per email ammesso solo se
   `verified` è vero (`:150-157`); collega o crea l'utente (`:159-167`) e committa (`:169`).
4. Sessione: JWT `type=student` (`auth_service.py:54-67`) messo nel cookie `student_token`, `httponly`,
   `max_age = EXPIRE_MINUTES*60` (`discord_auth.py:175-184`).
5. `POST /auth/discord/logout` cancella il cookie (`:188-197`).

### 3.4 Richieste di contatto (consulenza e pacchetti)

`POST /consulenze/` (`consulenza.py:27-48`) e `POST /pacchetti-richieste/`
(`pacchetti_richieste.py:28-56`) seguono lo stesso schema: registrano il contatto con
`get_or_create_user` (`consulenza.py:30`, `pacchetti_richieste.py:30`), poi inviano email al cliente,
email a `EMAIL_ADMIN` ed embed Discord. Nessuna riga viene creata in `packages` o `bookings`. La
risposta è un messaggio fisso (`consulenza.py:48`, `pacchetti_richieste.py:56`). Il nome leggibile del
pacchetto è letto dal catalogo con accesso diretto `CATALOGO_PACCHETTI[richiesta.tipo]`
(`pacchetti_richieste.py:32`), ammissibile perché `tipo` è già ristretto a tre valori
(`schemas/pacchetto_richiesta.py:10,17`).

### 3.5 Recensioni

Il token è generato alla prenotazione (`booking.py:238`) e finisce nel link costruito dallo scheduler:
`{PUBLIC_BASE_URL}/static/recensione.html?booking_id=..&token=..` (`scheduler.py:194`), inviato da
`invia_richiesta_recensione` (`email_service.py:316-339`). `recensione.js:5-7` rilegge i due parametri
dalla query string e `POST /bookings/{id}/recensione` li invia nel corpo (`recensione.js:42-50`).
Il server confronta il token con `secrets.compare_digest` (`booking.py:354`), rifiuta la seconda
recensione sulla stessa prenotazione (`:357-359`) e crea la riga con `approvata=False` per default
(`models/review.py:22`). La pubblicazione avviene solo via `PATCH /admin/recensioni/{id}`
(`admin/reviews.py:59-73`); la vetrina pubblica espone voto, commento, **solo il nome di battesimo**
(`booking.py:332`) e la data.

### 3.6 Pannello di amministrazione

1. `admin.js:112-116` invia username e password come `application/x-www-form-urlencoded` a
   `POST /admin/login`.
2. `admin/__init__.py:43-55`: `verifica_credenziali` confronta lo username con `ADMIN_USERNAME` e la
   password con `bcrypt.checkpw` su `ADMIN_PASSWORD_HASH` (`auth_service.py:29-36`); in caso di
   successo emette un JWT `type=admin` con scadenza `EXPIRE_MINUTES` (`auth_service.py:39-51`).
3. Il token resta in una variabile JavaScript (`admin.js:12`), non in `localStorage`, e viene allegato
   come `Authorization: Bearer` a ogni chiamata (`admin.js:147-152`). Ricaricando la pagina si perde.
4. Liste paginate: `pagina_e_offset` limita `per_pagina` a 100 (`pagination_service.py:14`), la
   risposta è `{items, totale, pagina, per_pagina, pagine_totali}` (`:21-29`).
5. Tutte le date mostrate nel pannello passano da `formatta_data_ora_rome`
   (`admin/bookings.py:58,86`, `admin/clients.py:87`, `admin/reviews.py:48`, `admin/availability.py:49`).
6. Export CSV: costruito in memoria con `csv.writer` (`admin/bookings.py:156-184`), codificato
   `utf-8-sig` e restituito come `StreamingResponse` con `Content-Disposition: attachment`
   (`:190-199`); il client lo riceve come blob e lo salva lato browser (`admin.js:1137-1154`).
7. Cancellazione cliente (`admin/clients.py:96-133`): per ogni prenotazione libera lo slot se
   `confirmed` (`:117-118`), elimina la recensione collegata (`:121-122`) e la prenotazione (`:123`);
   poi elimina note e pacchetti (`:127-128`) e infine l'utente (`:131`), con un solo commit (`:132`).

### 3.7 Disponibilità: dalla regola allo slot

`POST /admin/disponibilita/regole` (`admin/availability.py:121-153`) valida `ora_fine > ora_inizio`
(`:131-132`), salva la regola e chiama subito `genera_slot_da_regola` (`:146`).
`availability_service.py:45-106`: rifiuta durate diverse da 1 h (`:62-63`); calcola la prima occorrenza
del giorno della settimana (`:73-74`) e itera per settimane fino all'ultimo giorno del mese corrente
(`:68`, `:79-83`); per ogni slot converte l'orario **da ora di Roma a UTC naive** (`:93-94`), scarta
gli orari passati (`:96`), quelli già esistenti allo stesso `start_time` (`:97`) e quelli che si
sovrapporrebbero (`:98`); un solo commit finale (`:105`).

I blocchi eccezionali (`applica_blocco_eccezionale`, `availability_service.py:143-171`) estendono le
due date all'intera giornata italiana (`:151-152`), convertono in UTC (`:154-155`) e marcano gli slot
**liberi** dell'intervallo con `is_available=False, blocked_admin=True` (`:160-168`).

La sincronizzazione calendario (`calendar_service.py:191-231`) carica gli slot liberi futuri (`:204`),
fa **una sola** lettura del calendario sull'intervallo complessivo (`:214-217`), e per ogni
sovrapposizione marca `is_available=False, blocked_external=True` (`:224-227`). Gli eventi "tutto il
giorno" sono trattati come giornate italiane (`:172-178`).

### 3.8 Job periodici (`avvia_scheduler`, `scheduler.py:344-437`)

| Job | Trigger | Cosa fa |
|---|---|---|
| `controlla_promemoria` | interval, `REMINDER_CHECK_INTERVAL_MINUTES` (`:351-356`) | Prenotazioni `confirmed`, `reminder_sent=False`, con slot fra adesso e adesso+`REMINDER_HOURS_BEFORE` (`:122-127`); invia email + Discord e committa **dentro il ciclo** (`:139-157`) |
| `controlla_recensioni` | interval, `REVIEW_CHECK_INTERVAL_MINUTES` (`:357-362`) | Pre-filtro su slot iniziati da almeno 2 h (`:177-181`), verifica esatta della fine sessione (`:190-192`), invia il link di recensione e marca `review_email_sent` (`:194-198`) |
| `sincronizza_calendario` | interval, `CALENDAR_SYNC_INTERVAL_MINUTES` (`:363-368`) | `sincronizza_slot_con_calendario` (`:214`) |
| `genera_slot_giornaliero` | cron 03:00 (`:377-383`) | Per ogni regola con `attiva=True` (`:230`) chiama `genera_slot_da_regola` (`:233`) |
| `controlla_retention_clienti` | cron 03:01 (`:403-409`) | `anonimizza_clienti_inattivi`; alert Discord solo se il conteggio è > 0, senza dati personali (`:313-320`) |
| `pulisci_slot_obsoleti` | cron 03:02 (`:413-419`) | `elimina_slot_obsoleti`: elimina gli slot passati non referenziati da nessuna prenotazione, né come `slot_id` né come `slot_id_secondario` (`availability_service.py:124-139`) |
| `controlla_credenziali` | cron domenica 03:30 (`:393-400`) | Per Gmail, Drive e Calendar (`:71-95`) esegue la sonda e avvisa **solo alla transizione** di stato, usando il dizionario di modulo `_ultimo_controllo_credenziali` (`:53`, `:280-300`) |
| `backup_database` | cron domenica 04:00 (`:428-435`) | `esegui_backup_database(engine)`; alert Discord solo se fallisce (`:333-340`) |

Lo scheduler è costruito senza timezone esplicita (`scheduler.py:350`): gli orari cron sono quelli del
fuso in cui gira il processo — **NON VERIFICATO** quale sia in esecuzione.

### 3.9 Backup del database

`esegui_backup_database` (`backup_service.py:156-179`): esce con `False` se mancano
`GOOGLE_DRIVE_BACKUP_FOLDER_ID` o `DRIVE_REFRESH_TOKEN` (`:163-165`); altrimenti `crea_dump_sql`
(`:73-124`) apre una `raw_connection`, esegue `SHOW TABLES` (`:83`), `SHOW CREATE TABLE` (`:96`) e
`SELECT *` per tabella (`:102`), producendo `DROP TABLE`/`CREATE`/`INSERT` a blocchi di 500 righe
(`:44`, `:110-118`), racchiusi fra `SET FOREIGN_KEY_CHECKS=0/1` (`:89`, `:121`). Il dump viene caricato
su Drive con nome `vgc-coaching-backup-<YYYY-MM-DD_HHMM>.sql` (`:169`, `:127-136`) e i file più vecchi
di `BACKUP_RETENTION_DAYS` vengono eliminati (`:139-153`).

Questo dump usa sintassi MySQL (`SHOW CREATE TABLE`, `FOREIGN_KEY_CHECKS`) ed è coerente con la
presenza di `PyMySQL` in `requirements.txt:40`; il motore effettivo dipende però da `DATABASE_URL`
(**NON VERIFICATO**).

### 3.10 Convenzione sugli orari

Nel database gli orari sono `DateTime` naive. La conversione avviene ai bordi:
- ingresso admin: `SlotCreate` interpreta come ora di Roma e salva in UTC (`schemas/slots.py:46-57`);
- generazione da regola: stessa conversione (`availability_service.py:93-94`);
- uscita verso il browser pubblico: offset UTC esplicito (`schemas/slots.py:68-78`,
  `users.py:99`), e il JavaScript formatta nel fuso del dispositivo (`app.js:238-248`);
- uscita verso il pannello admin ed email: stringhe già in ora di Roma
  (`timezone_service.py:34-42`).

---

## 4. Dipendenze esterne

### 4.1 Servizi di rete contattati

| Servizio | Endpoint nel codice | Da dove |
|---|---|---|
| API Gmail | `build("gmail","v1")` + `users().messages().send` | `email_service.py:96-98` |
| Google Drive | `build("drive","v3")`, `files().create/list/delete` | `backup_service.py:70`, `:132-136`, `:146-152` |
| Google Calendar | `build("calendar","v3")`, `events().insert/list/delete` | `calendar_service.py:50`, `:129-132`, `:154-160`, `:238-241` |
| Google OAuth token endpoint | `https://oauth2.googleapis.com/token` | `google_oauth_service.py:40`, `calendar_service.py:42` |
| Discord OAuth2 | `authorize`, `token`, `users/@me` | `discord_auth.py:42-44` |
| Discord webhook | `requests.post(DISCORD_WEBHOOK_URL, timeout=5)` | `discord_service.py:47` |

### 4.2 Librerie

Da `requirements.txt`, quelle effettivamente importate dal codice:
`fastapi` (`main.py:25`), `starlette`/`uvicorn` (avvio, `nixpacks.toml:5`), `sqlalchemy`
(`database.py:9-10`), `alembic` (`main.py:47-50`), `PyMySQL` (usata via `DATABASE_URL`; nessun import
diretto), `pydantic` (`schemas/*`), `email-validator` (richiesta da `EmailStr`,
`schemas/users.py:8`), `python-dotenv` (`database.py:11` e altri sei moduli), `python-jose`
(`auth_service.py:13`), `bcrypt` (`auth_service.py:11`, `scripts/hash_admin_password.py:17`),
`slowapi` (`main.py:32-34`, `rate_limit.py:7-8`), `apscheduler` (`scheduler.py:21`),
`google-api-python-client` (`email_service.py:18`, `calendar_service.py:19`, `backup_service.py:25-26`),
`google-auth` (`google_oauth_service.py:16-17`, `calendar_service.py:17`), `google-auth-oauthlib`
(`scripts/reauth_gmail.py:44`, `scripts/reauth_drive.py:37`), `requests` (`discord_service.py:13`,
`discord_auth.py:15`), `tzdata` (per `ZoneInfo("Europe/Rome")`, `timezone_service.py:13,17`),
`python-multipart` (necessaria per `OAuth2PasswordRequestForm`, `admin/__init__.py:13`).

Sviluppo/test: `pytest`, `httpx`, `pytest-cov` (`requirements-dev.txt:7-9`), che include
`requirements.txt` (`:5`).

Il frontend non ha dipendenze: nessun `package.json` nel repository, nessun tag `<script src>` verso un
host esterno (`frontend/*.html`, unici script: `/static/js/*.js`).

### 4.3 Variabili d'ambiente

Ricavate dalle chiamate `os.getenv` nel codice; `.env` è caricato da `load_dotenv()`
(`database.py:13`, `auth_service.py:17`, `email_service.py:21`, `discord_service.py:16`,
`calendar_service.py:23`, `backup_service.py:30`, `alembic/env.py:82`).

| Variabile | Letta in | Default nel codice | Se manca |
|---|---|---|---|
| `DATABASE_URL` | `database.py:15`, `main.py:87`, `alembic/env.py:86` | nessuno | **Fatale all'import** (`database.py:20`). In `main.py:99-100` la sola assenza salta le migrazioni |
| `LOG_LEVEL` | `main.py:21` | `"INFO"` | — |
| `FRONTEND_ORIGINS` | `main.py:141`, `scheduler.py:44` | `"http://127.0.0.1:8000,http://localhost:8000"` | — |
| `JWT_SECRET` | `auth_service.py:19` | nessuno | Nessun controllo esplicito: `SECRET_KEY` resta `None` e l'effetto emerge in `jwt.encode`/`jwt.decode` (`auth_service.py:50,73`) — **NON VERIFICATO** l'esito esatto |
| `JWT_ALGORITHM` | `auth_service.py:20` | `"HS256"` | — |
| `JWT_EXPIRE_MINUTES` | `auth_service.py:21` | `480` | — |
| `ADMIN_USERNAME` | `auth_service.py:23` | nessuno | Login sempre rifiutato (`:31`) |
| `ADMIN_PASSWORD_HASH` | `auth_service.py:26` | nessuno | Login sempre rifiutato (`:31-32`) |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` | `email_service.py:23-25` (i primi due anche `backup_service.py:35-36`, `scripts/reauth_*.py`) | nessuno | Nessun controllo: l'invio fallisce dentro `try/except` e viene solo loggato (`email_service.py:151-152`) |
| `EMAIL_MITTENTE` | `email_service.py:26` | nessuno | Idem |
| `EMAIL_ADMIN` | `email_service.py:27` | nessuno | Destinatario delle notifiche al coach (`:221`, `:265`, `:310`) |
| `COACH_DISCORD_TAG`, `COACH_TELEGRAM_CONTACT` | `email_service.py:28-29` | nessuno | Interpolati nel corpo email (`:140-141`, `:178-179`) |
| `DISCORD_WEBHOOK_URL` | `discord_service.py:18` | nessuno | Invio saltato con warning (`:39-41`) |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_OAUTH_REDIRECT_URI` | `discord_auth.py:31-33` | nessuno | Nessun controllo; `DISCORD_OAUTH_REDIRECT_URI` decide anche il flag `secure` dei cookie (`:40`) |
| `GOOGLE_CALENDAR_ID`, `GOOGLE_SERVICE_ACCOUNT_EMAIL`, `GOOGLE_PRIVATE_KEY` | `calendar_service.py:26-30` | `GOOGLE_PRIVATE_KEY` → `""` con `\n` letterali riconvertiti (`:30`) | Le chiamate falliscono dentro `try/except` (`:137-139`) |
| `DRIVE_REFRESH_TOKEN`, `GOOGLE_DRIVE_BACKUP_FOLDER_ID` | `backup_service.py:37-38` | nessuno | Backup saltato, ritorno `False` (`:163-165`) |
| `BACKUP_RETENTION_DAYS` | `backup_service.py:40` | `"30"` | — |
| `RETENTION_MONTHS` | `retention_service.py:15` | `"24"` | — |
| `REMINDER_HOURS_BEFORE` | `scheduler.py:35` | `"24"` | — |
| `REMINDER_CHECK_INTERVAL_MINUTES` | `scheduler.py:36` | `"5"` | — |
| `REVIEW_CHECK_INTERVAL_MINUTES` | `scheduler.py:38` | `"60"` | — |
| `CALENDAR_SYNC_INTERVAL_MINUTES` | `scheduler.py:47` | `"60"` | — |
| `PUBLIC_BASE_URL` | `scheduler.py:42` | prima origine di `FRONTEND_ORIGINS`, altrimenti `http://127.0.0.1:8000` (`:43-45`) | — |
| `PORT` | `nixpacks.toml:5` | nessuno | Fornita dall'ambiente di esecuzione |

`.env.example` elenca le stesse variabili; `.env` è escluso dal versionamento (`.gitignore:1`).

### 4.4 File e percorsi richiesti a runtime

Tutti relativi alla directory di lavoro del processo:
`alembic.ini` (`main.py:89`), `alembic/` (`alembic.ini:8`), `frontend/` (`main.py:162`),
`frontend/index.html`, `about.html`, `privacy.html`, `admin.html` (`main.py:190,194,198,202`).
Il processo deve quindi essere avviato dalla radice del repository.

---

## 5. Comandi

Ricavati dai file di configurazione del progetto.

**Avvio (produzione dichiarata)** — `nixpacks.toml`:
```
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```
(`nixpacks.toml:5`), su Python 3.11 (`nixpacks.toml:2`). Non esistono `Dockerfile`, `Procfile` o
`package.json` nel repository.

**Avvio locale**: nessun file dichiara un comando diverso; vale lo stesso entrypoint
`backend.main:app`, da eseguire nella radice del progetto per via dei percorsi relativi (§4.4).

**Installazione**:
```
pip install -r requirements.txt        # runtime
pip install -r requirements-dev.txt    # runtime + test (include il precedente, requirements-dev.txt:5)
```

**Test**:
```
pytest
```
`pytest.ini:9` aggiunge la radice a `sys.path`; `pytest.ini:17` attiva sempre
`--cov=backend --cov-report=term-missing`; `pytest.ini:2` limita la raccolta a `tests/`.
La CI (`.github/workflows/tests.yml`) esegue `pytest` (`:41`) su Python 3.11 (`:27`) dopo
`pip install -r requirements-dev.txt` (`:30`), con `DATABASE_URL="sqlite:///:memory:"` e
`JWT_SECRET="test-secret-non-usato-in-produzione"` (`:43-44`), su ogni `push` e ogni `pull_request`
(`:11-13`). `tests/conftest.py` sostituisce `get_db` con un SQLite in memoria (`:32-48`) e disattiva il
rate limiter (`:55`).

**Migrazioni**: applicate automaticamente all'avvio del server, con backup preventivo se ce ne sono di
pendenti (`main.py:92-97`). `alembic.ini:8` punta a `alembic/` e `alembic.ini:91` lascia
`sqlalchemy.url` vuota, sovrascritta a runtime da `DATABASE_URL` (`alembic/env.py:94`). Nessun file del
progetto dichiara un comando Alembic da riga di comando.

**Script one-off** (tutti con `if __name__ == "__main__"`):
```
python scripts/hash_admin_password.py   # scripts/hash_admin_password.py:88
python scripts/reauth_gmail.py          # scripts/reauth_gmail.py:115
python scripts/reauth_drive.py          # scripts/reauth_drive.py:100
```

**Build**: nessun passo di build per il frontend — nessun `package.json`, nessun bundler, gli HTML
caricano direttamente i `.js` da `/static` (`frontend/index.html:444-445`).

**Monitoraggio**: `.github/workflows/monitor.yml` interroga
`https://vgc-coaching-production.up.railway.app/health` (`:48`) ogni 15 minuti (`:23`), con tre
tentativi (`:60-67`), avvisa su Discord solo alle transizioni di stato (`:93-97`) ed esce con codice di
errore quando il sito è giù (`:116`).

---

## 6. NON VERIFICATO

1. **Valori effettivi delle variabili d'ambiente in esecuzione.** Non sono nel codice; `.env` è escluso
   dal versionamento (`.gitignore:1`). Serverebbe accesso all'ambiente di esecuzione.
2. **Motore di database realmente usato.** Dipende da `DATABASE_URL` (`database.py:15`). Il dump usa
   sintassi MySQL (`backup_service.py:83,89,96`) e `PyMySQL` è fra le dipendenze
   (`requirements.txt:40`), ma la stringa di connessione non è nel repository.
3. **Fuso orario dei job cron.** `BackgroundScheduler()` è costruito senza timezone
   (`scheduler.py:350`): gli orari 03:00/03:01/03:02/03:30/04:00 sono nel fuso del processo, che il
   codice non determina.
4. **Comportamento con `JWT_SECRET` assente.** `auth_service.py:19` non ha default né controllo;
   l'esito dipende da come `python-jose` gestisce una chiave `None` in `jwt.encode`
   (`auth_service.py:50`). Non deducibile dal codice del progetto.
5. **Risposte dei servizi esterni** (Google Gmail/Drive/Calendar, Discord). Dal codice sono visibili
   solo le richieste inviate e la gestione degli errori; non cosa restituiscono, né se le credenziali
   configurate abbiano i permessi necessari. In particolare `verifica_credenziali_google`
   (`google_oauth_service.py:79-85`) prova solo il refresh del token, non un'operazione applicativa.
6. **Chi esegue `nixpacks.toml`.** Il file dichiara comando e runtime (`nixpacks.toml:2,5`), ma la
   piattaforma che lo interpreta non è determinabile dal repository. L'unico riferimento a un host è
   l'URL in `.github/workflows/monitor.yml:48`.
7. **Corrispondenza fra gli `id` DOM usati dal JavaScript e quelli presenti negli HTML.** Sono stati
   letti i tag `<script>`/`<link>` di tutti gli HTML e, per verifica puntuale, il campo
   `nuovo-slot-durata` (`frontend/admin.html:218-220`) e i pulsanti durata
   (`frontend/index.html:198,201`); il corpo completo dei cinque HTML è fuori perimetro, quindi non è
   verificata l'esistenza di tutti gli altri `id` referenziati da `app.js` e `admin.js`.
8. **Contenuto di `tests/`** oltre a `conftest.py`, di `frontend/css/` e delle 18 migrazioni
   nel dettaglio delle singole operazioni: fuori perimetro. Delle migrazioni è stata verificata solo la
   catena `revision`/`down_revision` (riga 15-16 di ciascun file) e l'`upgrade()` della head.
