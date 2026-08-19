# STATO_PROGETTO.md — VGC Coaching App

> Documento generato leggendo il codice sorgente effettivo del repository (branch `master`, commit `abf67ca`, 2026-08-08), **aggiornato al commit `3260848`, 2026-08-19** dopo la sessione di deploy in produzione descritta nella sezione 10. Non presuppone la lettura di nessun'altra conversazione o documento precedente. `ANALYSIS.md` e `ROADMAP.md` (presenti nella root) descrivono una sessione di sviluppo precedente e sono coerenti con questo documento, ma in caso di conflitto **questo file e il codice sorgente hanno la precedenza**.

---

## 1. Struttura del progetto

Monolite Python/FastAPI che serve sia le API REST sia i file statici del frontend (HTML/CSS/JS vanilla, nessun framework, nessuna build step) da un unico processo. Persistenza su MySQL tramite SQLAlchemy, migrazioni con Alembic.

```
.
├── .env                    # segreti reali — MAI in git
├── .env.example             # template dei nomi di variabile, solo placeholder
├── .gitignore
├── ANALYSIS.md               # audit di una sessione di sviluppo precedente (storico)
├── README.md                 # guida setup/deploy
├── ROADMAP.md                 # piano di lavoro P0→P3 della sessione precedente, tutto segnato "fatto"
├── STATO_PROGETTO.md          # questo file
├── alembic.ini                # config Alembic (sqlalchemy.url vuoto, popolato a runtime da env.py)
├── nixpacks.toml               # comando di avvio per il deploy Railway (unica fonte di verità: procfile è stato rimosso)
├── requirements.txt             # dipendenze Python (equivalente a un pip freeze)
├── alembic/
│   ├── env.py                    # config runtime migrazioni, legge DATABASE_URL da .env, fallisce se assente
│   ├── script.py.mako             # template per nuove migrazioni
│   └── versions/                   # 11 migrazioni, vedi sezione 2 per la catena in ordine
├── backend/
│   ├── main.py                      # entrypoint: esegue le migrazioni, crea l'app, monta router/static/scheduler
│   ├── database.py                   # engine SQLAlchemy + sessionmaker + get_db()
│   ├── rate_limit.py                  # istanza condivisa slowapi Limiter (evita import circolari)
│   ├── scheduler.py                    # job periodico promemoria pre-sessione (APScheduler)
│   ├── models/
│   │   ├── __init__.py                   # raccoglie tutti i model per l'import (necessario ad Alembic)
│   │   ├── users.py                       # tabella users
│   │   ├── slots.py                        # tabella slots
│   │   ├── booking.py                       # tabella bookings
│   │   ├── client_note.py                    # tabella client_notes
│   │   ├── availability_rule.py               # tabella availability_rules
│   │   └── availability_exception.py           # tabella availability_exceptions
│   ├── routers/
│   │   ├── slots.py                       # GET/POST slot
│   │   ├── booking.py                      # GET/POST prenotazioni (endpoint più complesso del progetto)
│   │   ├── users.py                         # GET/POST utenti, profilo/storico studente loggato
│   │   ├── admin.py                          # login admin + tutti gli endpoint del pannello (file più grande)
│   │   └── discord_auth.py                    # login opzionale via Discord OAuth2
│   ├── schemas/
│   │   ├── users.py, booking.py, slots.py, client_note.py, availability.py   # validazione Pydantic in/out per ciascuna area
│   └── services/
│       ├── auth_service.py                   # crea/verifica JWT (admin e studente, claim "type" separato)
│       ├── timezone_service.py                # unica funzione utc_to_rome(), usata ovunque un orario va mostrato
│       ├── availability_service.py             # genera slot da regola ricorrente, controllo overlap, applica blocchi
│       ├── calendar_service.py                  # Google Calendar: crea/elimina/legge eventi
│       ├── email_service.py                      # invio email transazionali via SendGrid
│       └── discord_service.py                     # notifiche via webhook Discord
└── frontend/
    ├── index.html               # form pubblico di prenotazione (wizard a 3 step + login Discord opzionale)
    ├── admin.html                 # pannello admin (login + 4 sezioni: dashboard, prenotazioni, clienti, slot)
    ├── Architettura.txt             # documento obsoleto, descrive solo 3 file — NON riflette la struttura attuale, ignorarlo
    ├── css/style.css                 # stili pagina pubblica
    ├── css/admin.css                  # stili pannello admin
    ├── js/app.js                       # logica pagina pubblica (wizard, fetch API, login Discord)
    └── js/admin.js                      # logica pannello admin (dashboard, tabelle paginate, CRUD slot/disponibilità)
```

---

## 2. Schema del database

MySQL, 6 tabelle attive. Nessun ORM "autogenerate": ogni migrazione in `alembic/versions/` è scritta a mano.

### `users`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| nome | String(100) | NOT NULL |
| email | String(100) | UNIQUE, NOT NULL |
| telefono | String(20) | nullable |
| showdown_username | String(100) | nullable |
| discord_tag | String(100) | nullable — tag testuale inserito a mano nel form |
| discord_id | String(30) | nullable, UNIQUE — id Discord permanente, popolato solo via login OAuth2 |
| created_at | DateTime | default now() |

### `slots`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| start_time | DateTime | NOT NULL — **sempre UTC naive**, vedi §7 |
| duration_hours | Integer | NOT NULL, default 1 |
| is_available | Boolean | default True |
| blocked_external | Boolean | NOT NULL, default False — bloccato da sync Google Calendar |
| blocked_admin | Boolean | NOT NULL, default False — bloccato da un blocco eccezionale (ferie) |
| created_at | DateTime | default now() |

### `bookings`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| slot_id | Integer | FK → slots.id, NOT NULL |
| duration_hours | Integer | NOT NULL, default 1 |
| price_cents | Integer | NOT NULL — prezzo in centesimi, calcolato server-side |
| service_type | String(30) | NOT NULL — `vod_review` / `team_building` / `bo3_sparring` / `mentality_prep` |
| status | String(20) | default `confirmed` — `confirmed` / `cancelled` / `no_show` |
| note_cliente | Text | nullable |
| note_admin | Text | nullable — visibile solo al coach |
| vod_link | String(500) | nullable |
| replay_code | String(200) | nullable |
| calendar_event_id | String(200) | nullable — id evento Google Calendar collegato |
| reminder_sent | Boolean | NOT NULL, default False |
| created_at | DateTime | default now() |

Relazioni: `Booking.user` / `Booking.slot` (many-to-one); backref `User.bookings`, `Slot.booking`.

### `availability_rules`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| giorno_settimana | Integer | NOT NULL — 0=lunedì...6=domenica |
| ora_inizio / ora_fine | Time | NOT NULL — ora italiana |
| durata_slot_ore | Integer | NOT NULL, default 1 |
| attiva | Boolean | NOT NULL, default True — **campo presente ma non ancora usato per filtrare nulla nel codice** |
| created_at | DateTime | default now() |

### `availability_exceptions`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| data_inizio / data_fine | Date | NOT NULL, inclusive |
| motivo | String(200) | nullable |
| created_at | DateTime | default now() |

### `client_notes`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| nota | Text | NOT NULL |
| created_at | DateTime | default now() — usato anche per l'ordinamento cronologico |

Relazione: `ClientNote.user`, backref `User.note_tecniche`.

### Tabella rimossa
`payments` — esisteva nella migrazione iniziale, mai realmente usata (solo colonna `stripe_session_id` mai popolata), rimossa con la migrazione `d1af2a35c949_rimuovi_tabella_payments.py` insieme al model `backend/models/payment.py` (eliminato dal filesystem nel commit `abf67ca`).

### Catena delle migrazioni (ordine reale, per `down_revision`)
```
1972ef07e768  crea tabelle iniziali (users, slots, bookings, payments)
  → a4568987d2e7  aggiungi calendar_event_id a bookings
    → d1af2a35c949  rimuovi tabella payments
      → 98489ff817ea  aggiungi service_type a bookings (con backfill sulle righe esistenti)
        → 37a82dbead86  aggiungi discord_tag a users
          → f56a5f50b503  aggiungi blocked_external a slots
            → dcfea9cf2bb0  aggiungi vod_link e replay_code a bookings
              → 60a355bf4f97  aggiungi reminder_sent a bookings
                → cc755d0d6a6b  crea tabella client_notes
                  → 17c843945785  regole ricorrenti, blocchi eccezionali, blocked_admin
                    → 0bfc529cd9fd  aggiungi discord_id a users   [HEAD]
```

---

## 3. Endpoint API

### Pagine/static (`backend/main.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/` | no | serve `frontend/index.html` |
| GET | `/admin-panel` | no | serve `frontend/admin.html` |
| GET | `/static/*` | no | file statici da `frontend/` (css/js) |

### `/slots` (`backend/routers/slots.py`)
| Metodo | Path | Auth | Payload | Cosa fa |
|---|---|---|---|---|
| GET | `/slots/` | no | — | slot con `is_available=True` **e `start_time` non ancora passato** (fix 2026-08-19, prima mostrava anche slot mai prenotati ma con orario già trascorso) |
| GET | `/slots/{id}` | no | — | un singolo slot, **qualsiasi stato** (anche occupato/bloccato) |
| POST | `/slots/` | admin (JWT) | `SlotCreate{start_time, duration_hours}` | crea slot singolo; `start_time` interpretato come ora italiana e convertito in UTC; rifiuta con 400 se si sovrappone a uno slot esistente |

### `/bookings` (`backend/routers/booking.py`)
| Metodo | Path | Auth | Payload | Cosa fa |
|---|---|---|---|---|
| GET | `/bookings/` | admin | — | tutte le prenotazioni |
| POST | `/bookings/` | no (rate limit 5/min per IP) | `BookingCreate{user_id, slot_id, duration_hours, service_type, note_cliente?, vod_link?, replay_code?}` | valida durata==slot; rifiuta se l'utente ha già 2 prenotazioni attive; claim atomico dello slot (vedi §7); calcola prezzo server-side; crea evento Google Calendar; salva booking `confirmed`; invia email cliente+admin e notifica Discord |

### `/users` (`backend/routers/users.py`)
| Metodo | Path | Auth | Payload | Cosa fa |
|---|---|---|---|---|
| GET | `/users/` | admin | — | tutti gli utenti |
| GET | `/users/me` | studente (JWT Discord) | — | profilo proprio |
| GET | `/users/me/prenotazioni` | studente (JWT Discord) | — | storico proprie prenotazioni |
| POST | `/users/` | no (rate limit 5/min per IP) | `UserCreate{nome, email, telefono?, showdown_username?, discord_tag?}` | get-or-create per email |

### `/admin` (`backend/routers/admin.py`) — tutti richiedono JWT admin tranne `/admin/login`
| Metodo | Path | Payload | Cosa fa |
|---|---|---|---|
| POST | `/admin/login` | form `username`, `password` | verifica contro `ADMIN_USERNAME`/`ADMIN_PASSWORD`, restituisce JWT |
| GET | `/admin/dashboard` | — | totale prenotazioni, prenotazioni oggi (fuso Roma), incassato, prossimi 5 slot liberi |
| GET | `/admin/analytics` | — | sessioni/incasso ultimi 6 mesi, servizi più richiesti, tasso no-show, clienti nuovi/ricorrenti |
| GET | `/admin/prenotazioni` | query: `stato?`, `pagina`, `per_pagina` | lista paginata con dati cliente+slot |
| PATCH | `/admin/prenotazioni/{id}/stato` | query: `nuovo_stato` | cambia stato; se `cancelled` elimina evento calendario e riapre lo slot |
| PATCH | `/admin/prenotazioni/{id}/note` | query: `note` | imposta `note_admin` |
| GET | `/admin/clienti` | query: `pagina`, `per_pagina` | lista clienti paginata con statistiche aggregate (GROUP BY, no N+1) |
| GET | `/admin/clienti/{user_id}/note` | — | storico note tecniche, ordine cronologico |
| POST | `/admin/clienti/{user_id}/note` | `ClientNoteCreate{nota}` | aggiunge nota (rifiuta se vuota) |
| GET | `/admin/slots` | query: `pagina`, `per_pagina` | lista slot paginata, liberi e occupati |
| POST | `/admin/slots/sync-calendario` | — | legge Google Calendar e blocca (`blocked_external`) gli slot liberi sovrapposti a eventi esterni |
| GET | `/admin/disponibilita/regole` | — | lista regole ricorrenti |
| POST | `/admin/disponibilita/regole` | `AvailabilityRuleCreate{giorno_settimana, ora_inizio, ora_fine, durata_slot_ore}` | crea regola, genera subito gli slot per le prossime 8 settimane |
| DELETE | `/admin/disponibilita/regole/{id}` | — | elimina regola (non tocca gli slot già generati) |
| GET | `/admin/disponibilita/blocchi` | — | lista blocchi eccezionali |
| POST | `/admin/disponibilita/blocchi` | `AvailabilityExceptionCreate{data_inizio, data_fine, motivo?}` | crea blocco, blocca subito gli slot liberi nel periodo |
| DELETE | `/admin/disponibilita/blocchi/{id}` | — | elimina blocco (non riapre gli slot che aveva bloccato) |
| DELETE | `/admin/slots/{id}` | — | elimina slot; rifiuta con 400 se ha prenotazioni collegate (storico preservato) |
| GET | `/admin/export/csv` | — | scarica CSV di tutte le prenotazioni (non paginato, di proposito) |

### `/auth/discord` (`backend/routers/discord_auth.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/auth/discord/login` | no | redirect a Discord per il consenso OAuth2 |
| GET | `/auth/discord/callback` | no (chiamato da Discord) | scambia il code, trova/crea l'utente (per `discord_id` poi per email), redirect a `/` con `?student_token=...` |

---

## 4. Logica di business

**Prezzi** (`TABELLA_PREZZI` in `backend/routers/booking.py`, unica fonte autoritativa — il client non può influenzarli): 1 ora = €35 (3500 cent), 2 ore = €60 (6000 cent), 3 ore = €80 (8000 cent). Lo stesso listino è ripetuto in `frontend/index.html` (attributi `data-price`) solo per mostrarlo prima dell'invio — va aggiornato a mano in entrambi i posti se cambia.

**Stati prenotazione**: `confirmed` (default, assegnato subito al submit — nessuno stato "in attesa di pagamento", il pagamento non è gestito in-app) → `cancelled` (libera lo slot, elimina l'evento calendario) oppure `no_show` (non tocca slot/calendario, sessione già passata).

**Flusso cliente** (`frontend/index.html` + `js/app.js`): wizard a 3 step — (1) scelta slot + tipo servizio (4 opzioni fisse) + durata, (2) dati anagrafici (nome/email obbligatori, resto opzionale, precompilati se loggato via Discord), (3) riepilogo e conferma → POST `/bookings/`. Login Discord sempre opzionale (guest checkout è il percorso normale, non un fallback).

**Flusso admin** (`frontend/admin.html` + `js/admin.js`): login JWT → 4 sezioni: dashboard (numeri + grafici a barre CSS), prenotazioni (lista filtrabile/paginata, cambio stato, note, export CSV), clienti (lista paginata, mini-CRM con note tecniche), slot (creazione singola, regole ricorrenti, blocchi eccezionali, sync manuale con Google Calendar).

**Limite anti-abuso**: massimo 2 prenotazioni `confirmed` con slot futuro per lo stesso `user_id` (`MAX_PRENOTAZIONI_ATTIVE` in `booking.py`); rate limiting 5 richieste/minuto per IP su `POST /users/` e `POST /bookings/`.

---

## 5. Variabili d'ambiente richieste

Solo nomi e descrizione — **nessun valore reale va mai riportato in questo o altri documenti**.

| Nome | Obbligatoria | Descrizione |
|---|---|---|
| `DATABASE_URL` | Sì | connessione MySQL (`mysql+pymysql://...`), l'app fallisce esplicitamente all'avvio se manca |
| `SECRET_KEY` | No | non più usata direttamente, tenuta per compatibilità |
| `FRONTEND_ORIGINS` | No | origini CORS consentite, separate da virgola (default localhost) |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | Sì (per le email) | Credenziali OAuth2 per l'API Gmail (sostituiscono SendGrid dal 2026-08-19, vedi sezione 10) |
| `EMAIL_MITTENTE` | Sì (per le email) | indirizzo mittente |
| `EMAIL_ADMIN` | Sì (per le email) | indirizzo del coach per le notifiche |
| `COACH_DISCORD_TAG` | No | mostrato nelle email di conferma/promemoria |
| `COACH_TELEGRAM_CONTACT` | No | mostrato nelle email di conferma/promemoria |
| `DISCORD_WEBHOOK_URL` | No | webhook per le notifiche prenotazione al coach |
| `DISCORD_CLIENT_ID` | No (per login studenti) | app OAuth2 Discord |
| `DISCORD_CLIENT_SECRET` | No (per login studenti) | app OAuth2 Discord |
| `DISCORD_OAUTH_REDIRECT_URI` | No (per login studenti) | deve corrispondere esattamente a quanto configurato sul Discord Developer Portal |
| `ADMIN_USERNAME` | Sì | unico account admin |
| `ADMIN_PASSWORD` | Sì | confronto in chiaro con `==`, nessun hashing |
| `JWT_SECRET` | Sì | firma dei token JWT (admin e studenti) |
| `JWT_ALGORITHM` | No | default `HS256` |
| `JWT_EXPIRE_MINUTES` | No | default `480` |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | No (per Calendar) | service account Google |
| `GOOGLE_PRIVATE_KEY` | No (per Calendar) | chiave privata service account, formato PEM su riga singola con `\n` letterali |
| `GOOGLE_CALENDAR_ID` | No (per Calendar) | calendario del coach |
| `REMINDER_HOURS_BEFORE` | No | ore prima della sessione per il promemoria, default `24` |
| `REMINDER_CHECK_INTERVAL_MINUTES` | No | intervallo del job promemoria, default `5` |

---

## 6. Servizi esterni

- **Gmail API (OAuth2)** — email transazionali (conferma cliente, promemoria, notifica admin), tramite `backend/services/email_service.py`. **Sostituisce SendGrid dal 2026-08-19** (vedi sezione 10 per il perché). Ogni chiamata è avvolta in try/except: un errore d'invio non blocca mai la prenotazione. Nota operativa: il progetto Google Cloud OAuth resta in stato "Testing" (non verificato) per evitare di dover possedere un dominio — questo significa che `GMAIL_REFRESH_TOKEN` scade dopo 7 giorni di inattività dell'app, richiedendo di rifare l'autorizzazione OAuth2 una tantum.
- **Google Calendar** — service account (non OAuth utente), configurato via `GOOGLE_SERVICE_ACCOUNT_EMAIL`/`GOOGLE_PRIVATE_KEY`/`GOOGLE_CALENDAR_ID` in `backend/services/calendar_service.py`. Il calendario del coach deve essere condiviso esplicitamente con l'email del service account. Scrittura (crea/elimina evento a ogni prenotazione/cancellazione) + lettura (sync manuale via bottone admin, non periodica).
- **Discord** — due integrazioni indipendenti: (1) webhook in uscita (`DISCORD_WEBHOOK_URL`) per notificare il coach di ogni nuova prenotazione/promemoria, via `backend/services/discord_service.py`; (2) OAuth2 in entrata (`DISCORD_CLIENT_ID`/`SECRET`/`REDIRECT_URI`) per il login opzionale studenti, via `backend/routers/discord_auth.py`.
- **PayPal** — **rimosso completamente** (storico: era un flusso di pagamento manuale via bonifico, con stato prenotazione "pending" in attesa di conferma admin). Nessuna traccia nel codice attuale: nessun model, nessun endpoint, nessuna dipendenza.
- **Railway** — hosting per app + MySQL, build via Nixpacks (`nixpacks.toml`). **Riattivato e live dal 2026-08-19**: collaudo end-to-end completo in produzione superato (slot → prenotazione → email → Calendar → Discord → export CSV). URL pubblico: `https://vgc-coaching-production.up.railway.app` (dominio personalizzato non ancora acquistato, decisione consapevole dell'utente).

---

## 7. Vincoli tecnici e comportamenti non ovvi

1. **Tutti i datetime nel DB sono UTC "naive"** (senza `tzinfo`), per convenzione di progetto — mai per errore. La conversione verso l'ora italiana avviene solo in lettura, tramite `timezone_service.utc_to_rome()`, mai nei model. **Perché**: evita ambiguità sui confronti diretti nel database e centralizza la conversione in un unico punto.

2. **Claim dello slot con UPDATE condizionale**, non `SELECT` poi `UPDATE` (`backend/routers/booking.py`, `create_booking`): `UPDATE slots SET is_available=0 WHERE id=X AND is_available=1`, controllo di `rowcount`. **Perché**: elimina la race condition su due richieste concorrenti sullo stesso slot. Deliberatamente **non** è stato aggiunto un vincolo `UNIQUE` sullo slot in `bookings`, perché incompatibile con il flusso cancella/riprenota (uno slot cancellato deve poter essere riprenotato).

3. Il claim atomico protegge solo **lo stesso slot** da doppia prenotazione — per due slot **diversi** che si sovrappongono nel tempo, la protezione è `slot_si_sovrappone()` in `availability_service.py`, controllata solo alla **creazione** dello slot (`POST /slots/`, `genera_slot_da_regola`), non al momento della prenotazione.

4. **Le migrazioni Alembic girano automaticamente a ogni avvio dell'app** (`run_migrations()` in `backend/main.py`, chiamata a livello di modulo prima ancora che l'oggetto `app` esista), dentro un `try/except Exception` che **non blocca il boot** se falliscono — stampa solo l'errore. Un problema di migrazione può quindi manifestarsi più tardi con errori runtime meno chiari, invece che con un fallimento di avvio pulito.

5. **Slot creati prima del fix sui fusi orari mostrano un orario sbagliato**: prima del fix, il valore naive salvato andava interpretato come ora di Roma; ora lo stesso valore viene letto come UTC. Accettato consapevolmente perché il progetto non ha dati reali da preservare.

6. `AvailabilityRule.attiva` esiste come colonna ma **non è ancora usata per filtrare nulla** nel codice — predisposta per uno sviluppo futuro (disattivare una regola senza cancellarla).

7. `GET /slots/{id}` è pubblico e restituisce **qualsiasi** slot, incluso uno già occupato o bloccato — a differenza di `GET /slots/` che filtra solo `is_available=True`. Non è chiaro dai commenti se sia intenzionale o una svista: da verificare se serve prima di considerarlo un problema.

8. **Export CSV volutamente non paginato** (`GET /admin/export/csv`), a differenza di tutte le altre liste admin — deve restare un export completo.

9. **Password DB esposta in git history — impatto ridimensionato**: la password dell'utente MySQL `Desuzakiddo` è rimasta pubblicamente visibile su GitHub per circa un mese (dal primo commit `dd4a88b`). Storia riscritta e ripulita il 2026-08-08 (`git filter-repo`). **Verificato il 2026-08-19**: quella credenziale riguardava solo il MySQL locale di sviluppo — il database di produzione su Railway usa da sempre un utente `root` con password generata autonomamente da Railway, mai passata per la cronologia Git. Nessun dato di produzione è mai stato a rischio. Resta buona norma ruotare la password locale, ma non è più bloccante.

10. **Un solo branch su GitHub**: `main` e il branch residuo `railway/fix-deploy-e53c40` (entrambi fermi a giugno 2026) sono stati **eliminati il 2026-08-19** — `master` è ora l'unico branch e il branch predefinito del repository. Il problema di ambiguità descritto in precedenza non esiste più.

11. **SMTP diretto non funziona su Railway**: un tentativo di inviare email via `smtplib`/SMTP diretto (porta 587, incluso Gmail) fallisce in produzione con `OSError: [Errno 101] Network is unreachable` — Railway blocca le connessioni SMTP in uscita a livello di rete (comune su piattaforme PaaS, anti-spam). Confermato con test diretti il 2026-08-19. Qualunque invio email da questo progetto deve passare da un'API HTTPS (Gmail API con OAuth2, o un provider come SendGrid), mai da SMTP grezzo.

---

## 8. Modifiche recenti (rispetto alla struttura precedente)

Il commit `abf67ca` (2026-08-08) ha consolidato in un solo commit tutto il lavoro di una sessione di sviluppo precedente, mai committato fino ad ora. Rispetto allo stato precedentemente pubblicato su GitHub (commit `dd4a88b`/`26a42d4`):

- **Rimosso**: model e tabella `payments` (flusso pagamento PayPal manuale eliminato del tutto — nessuno stato "in attesa di pagamento"); file `procfile` (config duplicata, `nixpacks.toml` resta l'unica fonte); fallback hardcoded della password MySQL in `backend/database.py`/`alembic.ini`.
- **Aggiunto**: campo `service_type` su `Booking`; campi `vod_link`/`replay_code`/`reminder_sent`/`calendar_event_id` su `Booking`; stato `no_show`; tabella `client_notes` (mini-CRM); tabelle `availability_rules`/`availability_exceptions` + campo `blocked_admin`/`blocked_external` su `Slot` (disponibilità ricorrente e blocchi eccezionali); campi `discord_tag`/`discord_id` su `User`; router `discord_auth.py` (login OAuth2 opzionale); `backend/scheduler.py` (promemoria automatici via APScheduler); `backend/rate_limit.py` (rate limiting via slowapi); `backend/services/availability_service.py`, `timezone_service.py`, `discord_service.py`; endpoint `/admin/analytics`, `/admin/disponibilita/*`, `/admin/slots/sync-calendario`, `/users/me`, `/users/me/prenotazioni`.
- **Corretto**: gestione fusi orari (storage UTC esplicito, prima assente); race condition sulla doppia prenotazione (claim atomico, prima assente); endpoint `GET /users/`, `GET /bookings/`, `POST /slots/` ora protetti da JWT admin (prima pubblici); CORS ristretto a `FRONTEND_ORIGINS` esplicite (prima `"*"`); paginazione + fix N+1 su `/admin/prenotazioni`, `/admin/clienti`, `/admin/slots`; migrazione `calendar_event_id` (prima aveva `upgrade()`/`downgrade()` vuoti).
- **Sicurezza (questa sessione, 2026-08-08)**: storia Git riscritta per rimuovere la password MySQL esposta; `.env.example`, `README.md`, `ANALYSIS.md`, `ROADMAP.md` aggiunti al repository per la prima volta.

---

## 9. Cosa funziona e cosa no, ad oggi (aggiornato 2026-08-19)

**Verificato end-to-end in produzione, sul dominio pubblico Railway** (`https://vgc-coaching-production.up.railway.app`), con database svuotato di ogni dato di test prima della verifica finale:
- Creazione slot da pannello admin
- Prenotazione cliente via form pubblico (claim atomico, prezzo server-side, `service_type`)
- Email di conferma al cliente + notifica al coach (via Gmail API)
- Evento creato su Google Calendar
- Notifica Discord al coach
- Export CSV dal pannello admin
- Endpoint admin/protetti rifiutano correttamente richieste senza token JWT (`401`)
- HTTPS valido sul dominio Railway di default

**Non ancora verificato**:
- Il flusso di consenso OAuth2 completo di Discord (login studenti) è segnalato in `ROADMAP.md` (P3-1) come "non testabile" nella sessione di sviluppo originale perché richiede interazione umana reale sulla schermata di autorizzazione — non risulta una verifica manuale successiva documentata.
- Non esiste ancora nessun ambiente di test automatizzato (nessuna cartella `tests/`, nessun file di test nel repository) — ogni verifica è manuale.
- Dominio personalizzato non acquistato (si usa l'URL `*.up.railway.app`) — decisione consapevole dell'utente, vedi sezione 10.

---

## 10. Sessione 2026-08-19 — deploy in produzione, log modifiche

Sessione dedicata a portare il progetto da "codice pronto ma Railway sospeso" a servizio pubblico realmente funzionante. In ordine:

1. **Pulizia branch GitHub**: eliminati `main` e `railway/fix-deploy-e53c40` (entrambi fermi a giugno, causavano confusione — GitHub mostrava "aggiornato 2 mesi fa" perché il branch default era il vecchio `main`). `master` impostato come branch default, ora l'unico branch del repository.
2. **Riattivazione Railway**: l'utente ha riattivato il servizio (piano a pagamento). Tutte le variabili d'ambiente impostate da zero sulle Railway Variables (vedi sezione 5), inclusi `JWT_SECRET`/`ADMIN_PASSWORD` generati sicuri via `secrets` di Python. Deploy verificato: migrazioni eseguite, container attivo, endpoint pubblici e protetti verificati dal vivo.
3. **Verifica password DB esposta**: confermato che la password compromessa nella cronologia Git riguardava solo il MySQL locale — quello di produzione ha sempre avuto credenziali proprie (vedi punto 9 della sezione 7). Rischio residuo declassato da bloccante a igiene facoltativa.
4. **Migrazione email: SendGrid → Gmail SMTP → Gmail API**: la Fase 5 (dominio personalizzato) è stata scartata per decisione dell'utente (costo). Senza dominio, l'autenticazione SPF/DKIM/DMARC vera non è possibile, quindi si è scelto di inviare direttamente dall'account Gmail del coach. Primo tentativo con SMTP diretto (`smtplib`) funzionava in locale ma falliva su Railway (`Network is unreachable`, vedi punto 11 della sezione 7). Sostituito con l'**API Gmail via OAuth2** (HTTPS, mai bloccata): nessuna nuova dipendenza (riusa `google-auth`/`google-api-python-client`, già presenti per Google Calendar). Verificato che le email arrivano in posta in arrivo normale (non spam) sia su Gmail che su un dominio Outlook/Office365 (`studenti.uniba.it`).
5. **Fix `GET /slots/`**: mancava un filtro sulla data — slot mai prenotati ma con orario già passato restavano visibili/prenotabili all'infinito sul form pubblico. Aggiunto lo stesso confronto naive-UTC già usato altrove nel codice (`booking.py`, `admin.py`).
6. **Reset database di produzione**: svuotate (via `TRUNCATE`, diretto sul database) le tabelle `bookings`, `client_notes`, `slots`, `users`, `availability_rules`, `availability_exceptions` — erano piene di dati di sviluppo/test (slot con date di giugno-luglio, utenti e prenotazioni di prova). Database ripartito da zero, ID auto-incrementali resettati.
7. **Collaudo end-to-end finale**: su database pulito, verificato l'intero flusso reale (slot → prenotazione → email → Calendar → Discord → CSV) sul dominio pubblico Railway — vedi sezione 9.

### Backlog / problemi aperti

- **Token OAuth Gmail scade dopo 7 giorni di inattività** (app Google in stato "Testing", non verificata — scelta deliberata per evitare di dover comprare un dominio). Se le email smettono di funzionare dopo una pausa, rifare l'autorizzazione OAuth2 una tantum (non c'è uno script dedicato nel repository, va ricostruito il flusso "authorization code" manualmente se serve).
- **Password MySQL locale** (`Desuzakiddo`) non ancora ruotata — non urgente (non riguarda la produzione), ma resta buona norma.
- **Dominio personalizzato + HTTPS proprio** (Fase 5 originale) non fatto, per scelta dell'utente — il sito resta su `*.up.railway.app`. Da riconsiderare se serve un'immagine più professionale o per sbloccare SPF/DKIM/DMARC veri in futuro.
- **`GET /slots/{id}` resta pubblico e senza filtro data/disponibilità** (punto 7 della sezione 7) — non toccato in questa sessione, da verificare se è voluto.
- Nessun test automatizzato nel repository — ogni verifica fatta finora (questa sessione e le precedenti) è manuale.
