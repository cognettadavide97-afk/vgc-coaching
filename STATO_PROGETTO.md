# STATO_PROGETTO.md — VGC Coaching App

> Documento generato leggendo il codice sorgente effettivo del repository (branch `master`), **aggiornato al 2026-09-03** (sezioni 13 e 14), dopo la sessione di conformità GDPR, hardening di sicurezza e enterprise-readiness del 2026-08-25/26 (sezione 11) e il fix della CI del 26/08. Aggiornato ulteriormente dopo la sessione di review indipendente e hardening del 31/08-01/09 (sezione 12), e infine dopo la revisione documentale del 01–03/09 (sezioni 13 e 14). Ogni sessione è stata pushata su `origin/master` con la CI verificata verde sul push reale, non solo sulla suite locale: run GitHub Actions `33529945237` sul commit `61d4554` (01/09) e `33690855235` sul commit `1e17319` (03/09). *Questi due riferimenti sono eventi, e come tali non invecchiano; per sapere dove sia la punta del ramo si guarda `git log`, non questo paragrafo — inseguire l'hash di HEAD a ogni modifica aveva già prodotto tre disallineamenti.* Non presuppone la lettura di nessun'altra conversazione o documento precedente. `ANALYSIS.md` e `ROADMAP.md` (presenti nella root) descrivono una sessione di sviluppo ancora precedente (agosto 2026, prime settimane) e restano **storici di proposito** — non vengono aggiornati. In caso di conflitto **questo file e il codice sorgente hanno la precedenza**.

> **Come si aggiorna questo documento.** Le sezioni **1–9 descrivono il presente**: non portano date di sessione e vanno corrette ogni volta che il codice cambia. Le sezioni **10 in poi sono un diario**: si scrivono una volta, si chiudono, e non si riaprono se non per barrare una voce con la data. Ogni punto ancora aperto vive in **un posto solo**, §9.1 — i backlog dentro le sezioni-diario sono congelati e valgono come fotografia del momento in cui furono scritti, non come elenco da consultare. Vale la pena rispettarla: quasi tutti gli errori trovati nelle revisioni del 01–03/09 stavano esattamente sulla cucitura fra le due nature — un fatto di sessione rimasto congelato in una sezione di stato (§7.2 dava il cookie per non verificato mesi dopo la verifica), o un fatto di stato mai propagato all'indietro (il backlog di §11 elencava come aperte due voci chiuse altrove).

---

## 1. Struttura del progetto

Monolite Python/FastAPI che serve sia le API REST sia i file statici del frontend (HTML/CSS/JS vanilla, nessun framework, nessuna build step) da un unico processo. Persistenza su MySQL tramite SQLAlchemy, migrazioni con Alembic.

```
.
├── .env                    # segreti reali — MAI in git
├── .env.example             # template dei nomi di variabile, riverificato allineato al codice il 2026-09-02
├── .gitignore
├── .github/workflows/tests.yml  # CI: pytest su ogni push/PR, verde
├── ANALISI_2026-08-31.md      # referto della review indipendente del 31/08 — findings tutti chiusi (storico)
├── ANALYSIS.md               # audit di una sessione di sviluppo molto precedente (storico)
├── RAILWAY_RIALLINEAMENTO_2026-09-02.md  # runbook dell'intervento sulle variabili Railway (storico)
├── README.md                 # guida setup/deploy, riallineata al codice il 2026-09-03 (vedi §14)
├── ROADMAP.md                 # piano di lavoro P0→P3 di quella stessa sessione, tutto "fatto" (storico)
├── REVISIONE_2026-09-01.md    # referto completo della revisione documentale del 01/09 (storico)
├── STATO_PROGETTO.md          # questo file
├── alembic.ini                # config Alembic (sqlalchemy.url vuoto, popolato a runtime da env.py)
├── nixpacks.toml               # comando di avvio per il deploy Railway (unica fonte di verità)
├── pytest.ini                    # pythonpath=., testpaths=tests, coverage on di default
├── requirements.txt             # dipendenze Python di produzione
├── requirements-dev.txt          # dipendenze extra solo per i test (pytest, httpx, pytest-cov)
├── alembic/
│   ├── env.py                    # config runtime migrazioni; salta fileConfig() se il root logger ha già handler
│   ├── script.py.mako             # template per nuove migrazioni
│   └── versions/                   # 18 migrazioni, vedi sezione 2 per la catena in ordine
├── scripts/                    # utility one-off da lanciare a mano dal computer del coach, mai su Railway
│   ├── _env_utils.py              # helper condiviso per aggiornare .env locale
│   ├── hash_admin_password.py      # genera ADMIN_PASSWORD_HASH da una password digitata
│   ├── reauth_gmail.py              # rinnova GMAIL_REFRESH_TOKEN (OAuth2, apre il browser)
│   └── reauth_drive.py               # rinnova DRIVE_REFRESH_TOKEN (OAuth2, apre il browser)
├── tests/                      # suite pytest, SQLite in-memory, integrazioni esterne mockate (per il conteggio vedi §9)
│   ├── conftest.py                # fixture condivise: DB isolato, mock Gmail/Discord/Calendar sui router, helper auth
│   │                                (Drive è mockato localmente in test_backup_service.py, non qui)
│   ├── test_admin.py, test_booking.py, test_slots.py, test_richieste.py, test_discord_auth.py,
│   │   test_email_service.py, test_retention.py, test_backup_service.py, test_health.py, test_reviews.py,
│   │   test_availability.py, test_scheduler.py, test_pagination_service.py, test_avvio.py
├── backend/
│   ├── main.py                      # entrypoint: logging, crea l'app, lifespan (migrazioni + backup pre-migrazione + scheduler),
│   │                                  monta router e static, CORS ristretto, rate limiter, pagine HTML + /health
│   ├── database.py                   # engine SQLAlchemy (pool_pre_ping=True) + sessionmaker + get_db()
│   ├── rate_limit.py                  # istanza condivisa slowapi Limiter (evita import circolari)
│   ├── scheduler.py                    # 8 job periodici APScheduler (promemoria, recensioni, sync calendario, generazione slot, healthcheck Gmail, retention, pulizia slot, backup)
│   ├── models/
│   │   ├── __init__.py                   # raccoglie tutti i model per l'import (necessario ad Alembic)
│   │   ├── users.py                       # tabella users (con anonimizzato_at per la retention)
│   │   ├── slots.py                        # tabella slots
│   │   ├── booking.py                       # tabella bookings (con slot_id_secondario, package_id, review_token)
│   │   ├── package.py                        # tabella packages
│   │   ├── review.py                          # tabella reviews
│   │   ├── client_note.py                     # tabella client_notes
│   │   ├── availability_rule.py                # tabella availability_rules
│   │   └── availability_exception.py             # tabella availability_exceptions
│   ├── routers/
│   │   ├── slots.py                       # GET/POST slot (admin per POST)
│   │   ├── booking.py                      # prenotazioni, cancellazione self-service, recensioni pubbliche + invio recensione via token
│   │   ├── users.py                         # utenti, profilo/storico studente loggato, pacchetti attivi
│   │   ├── discord_auth.py                   # login opzionale via Discord OAuth2 (con CSRF state) + logout
│   │   ├── consulenza.py                      # richiesta call conoscitiva gratuita (no slot/booking)
│   │   ├── pacchetti_richieste.py              # richiesta attivazione pacchetto (contatto, non acquisto vero)
│   │   └── admin/                               # package (prima era un unico file da 1018 righe)
│   │       ├── __init__.py                        # login admin, get_admin, assembla i sotto-router
│   │       ├── dashboard.py                         # dashboard + analytics
│   │       ├── bookings.py                           # lista/stato/note prenotazioni + export CSV
│   │       ├── clients.py                             # lista clienti + cancellazione GDPR + note tecniche
│   │       ├── availability.py                         # slot, sync calendario, regole ricorrenti, blocchi
│   │       ├── packages.py                              # creazione/lista pacchetti clienti
│   │       └── reviews.py                                # moderazione recensioni (approva/nasconde)
│   ├── schemas/
│   │   ├── users.py, booking.py, slots.py, client_note.py, availability.py,
│   │   │   package.py, review.py, consulenza.py, pacchetto_richiesta.py   # validazione Pydantic in/out
│   └── services/
│       ├── auth_service.py                   # crea/verifica JWT (admin e studente, claim "type" separato)
│       ├── timezone_service.py                # utc_to_rome() + helper condivisi (formatta_data_ora_rome, ora_utc_naive, intervalli_si_sovrappongono), usati ovunque un orario va mostrato o confrontato
│       ├── availability_service.py             # genera slot da regola ricorrente, controllo overlap, applica blocchi, elimina slot obsoleti
│       ├── calendar_service.py                  # Google Calendar: crea/elimina/legge eventi
│       ├── email_service.py                      # invio email transazionali via Gmail API (OAuth2), HTML-escaping
│       ├── discord_service.py                     # notifiche via webhook Discord + alert di sistema
│       ├── retention_service.py                    # anonimizzazione GDPR clienti inattivi
│       ├── backup_service.py                        # dump SQL + upload su Google Drive
│       ├── google_oauth_service.py                   # credenziali OAuth condivise da Gmail e Drive (Calendar usa un service account, vedi §6)
│       ├── package_service.py                         # catalogo fisso pacchetti (CATALOGO_PACCHETTI)
│       ├── booking_service.py                          # libera_slot_prenotazione(), condivisa da cliente+admin
│       └── pagination_service.py                        # pagina_e_offset()/busta_paginazione(), condivise da tutte le liste admin paginate
└── frontend/
    ├── index.html               # form pubblico di prenotazione (wizard + login Discord opzionale)
    ├── about.html                 # pagina About con vetrina recensioni approvate
    ├── privacy.html                 # informativa privacy/GDPR (IT/EN)
    ├── recensione.html               # pagina pubblica per lasciare una recensione post-sessione (via token)
    ├── admin.html                      # pannello admin (login + dashboard, prenotazioni, clienti, slot, pacchetti, recensioni)
    ├── css/style.css, css/admin.css
    ├── js/app.js, admin.js, about.js, i18n.js, recensione.js
    ├── fonts/Anton-Regular.woff2, Archivo-Variable.woff2
    ├── images/coach-avatar.png, coach-photo.jpg, favicon.png
    └── favicon.ico
```

---

## 2. Schema del database

MySQL, **8 tabelle applicative** (più `alembic_version`, gestita da Alembic e non dal codice dell'app). Nessun ORM "autogenerate": ogni migrazione in `alembic/versions/` è scritta a mano.

### `users`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| nome | String(100) | NOT NULL |
| email | String(100) | UNIQUE, NOT NULL |
| telefono | String(20) | nullable |
| categoria | String(20) | nullable — `junior`/`senior`/`master`, sostituisce il vecchio `showdown_username` |
| discord_tag | String(100) | nullable — tag testuale inserito a mano nel form |
| discord_id | String(30) | nullable, UNIQUE — id Discord permanente, popolato solo via login OAuth2 |
| **anonimizzato_at** | DateTime | nullable — valorizzato dal job di retention GDPR quando anonimizza il cliente per inattività |
| created_at | DateTime | default now() |

### `slots`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| start_time | DateTime | NOT NULL, **indicizzato** — sempre UTC naive, vedi §7 |
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
| **slot_id_secondario** | Integer | FK → slots.id, nullable — valorizzato solo per prenotazioni da 2h (unisce due slot da 1h adiacenti) |
| duration_hours | Integer | NOT NULL, default 1 |
| price_cents | Integer | NOT NULL — 0 se pagata con un pacchetto |
| service_type | String(30) | NOT NULL — `vod_review` / `team_building` / `bo3_sparring` / `tournament_prep` |
| status | String(20) | default `confirmed`, **indicizzato** — `confirmed` / `cancelled` / `no_show` |
| note_cliente | Text | nullable |
| note_admin | Text | nullable — visibile solo al coach |
| vod_link | String(500) | nullable |
| replay_code | String(200) | nullable |
| calendar_event_id | String(200) | nullable — id evento Google Calendar collegato |
| reminder_sent | Boolean | NOT NULL, default False |
| **package_id** | Integer | FK → packages.id, nullable — valorizzato se pagata scalando un pacchetto |
| **review_token** | String(64) | nullable, UNIQUE — token monouso per il link di recensione post-sessione |
| **review_email_sent** | Boolean | NOT NULL, default False |
| created_at | DateTime | default now() |

Relazioni: `Booking.user` / `Booking.slot` / `Booking.slot_secondario` / `Booking.package` (many-to-one); backref `User.bookings`, `Slot.booking`, `Package.bookings`. `Booking.slot_secondario` è l'unica senza backref. Altrove: `Package.user` → backref `User.packages`, `ClientNote.user` → backref `User.note_tecniche`, `Review.booking` → backref `Booking.review` (`uselist=False`, una sola recensione per prenotazione — usato da `elimina_cliente` per cancellarla prima della prenotazione).

### `packages` (nuova)
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users.id, NOT NULL |
| tipo | String(20) | NOT NULL — `intro`/`team`/`tour`, chiave del catalogo fisso in `package_service.py` |
| sessioni_totali | Integer | NOT NULL |
| sessioni_usate | Integer | NOT NULL, default 0 |
| durata_sessione_ore | Integer | NOT NULL, default 2 |
| prezzo_cents | Integer | NOT NULL — prezzo scontato realmente pagato (fuori app) |
| created_at | DateTime | default now() |

### `reviews` (nuova)
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| booking_id | Integer | FK → bookings.id, NOT NULL, **UNIQUE** — una recensione per prenotazione |
| voto | Integer | NOT NULL — 1-5 |
| commento | Text | nullable |
| approvata | Boolean | NOT NULL, default False — pubblica solo dopo moderazione admin |
| created_at | DateTime | default now() |

### `availability_rules`
| Campo | Tipo | Vincoli |
|---|---|---|
| id | Integer | PK |
| giorno_settimana | Integer | NOT NULL — 0=lunedì...6=domenica |
| ora_inizio / ora_fine | Time | NOT NULL — ora italiana |
| durata_slot_ore | Integer | NOT NULL, default 1 |
| attiva | Boolean | NOT NULL, default True — **ora usata davvero**: `genera_slot_giornaliero` (job notturno) filtra solo le regole attive |
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

### Tabelle rimosse
`payments` — rimossa nel primo consolidamento del progetto (agosto 2026), mai realmente usata.

### Catena delle migrazioni (18 totali, ordine reale)
Riportata per intero: prima le prime 11 erano delegate a "la versione precedente di questo documento", che esiste solo nella storia git e non è consultabile da chi legge oggi.
```
1972ef07e768  crea tabelle iniziali (slots, users, bookings, payments)   [base]
  → a4568987d2e7  aggiungi calendar_event_id a bookings
    → d1af2a35c949  rimuovi tabella payments
      → 98489ff817ea  aggiungi service_type a bookings
        → 37a82dbead86  aggiungi discord_tag a users
          → f56a5f50b503  aggiungi blocked_external a slots
            → dcfea9cf2bb0  aggiungi vod_link, replay_code a bookings
              → 60a355bf4f97  aggiungi reminder_sent a bookings
                → cc755d0d6a6b  crea tabella client_notes
                  → 17c843945785  regole ricorrenti, blocchi eccezionali, blocked_admin
                    → 0bfc529cd9fd  aggiungi discord_id a users
                      → a1c92f7e4b18  categoria al posto di showdown_username su users
                        → b3d84a19e6f2  crea tabella packages
                          → c5f612a8d9e3  crea tabella reviews
                            → d4a72e0f8b31  aggiungi slot_id_secondario a bookings
                              → a1b2c3d4e5f6  aggiungi approvata a reviews
                                → 215aa000de4b  indici su slots.start_time e bookings.status
                                  → 2eac6f32b19b  aggiungi anonimizzato_at a users  [HEAD]
```
Per verificare quale revisione è applicata a un database: `SELECT * FROM alembic_version;` (in produzione, al 2026-09-02, risulta `2eac6f32b19b`).

---

## 3. Endpoint API

### Pagine/static (`backend/main.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/` | no | serve `frontend/index.html` |
| GET | `/about` | no | serve `frontend/about.html` |
| GET | `/privacy` | no | serve `frontend/privacy.html` |
| GET | `/admin-panel` | no | serve `frontend/admin.html` |
| GET | `/static/*` | no | file statici da `frontend/` (css/js/immagini) |
| **GET** | **`/health`** | no | esegue `SELECT 1` reale sul DB, per un monitor esterno (non solo "processo vivo") |
| GET | `/docs`, `/redoc`, `/openapi.json` | no | documentazione API generata automaticamente da FastAPI, **pubblica**: espone lo schema di tutti gli endpoint, admin compresi (non i dati). Scelta consapevole; disattivabile con `docs_url=None` in `backend/main.py` se un domani non la si vuole più |

### `/slots` (`backend/routers/slots.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/slots/` | no | slot con `is_available=True` e `start_time` non ancora passato |
| POST | `/slots/` | admin (JWT) | crea slot singolo; rifiuta se sovrapposto a uno esistente |

*`GET /slots/{id}` è stato rimosso il 2026-09-02 (§13): era pubblico, restituiva qualunque slot in qualunque stato e non lo chiamava nessuno.*

### `/bookings` (`backend/routers/booking.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| POST | `/bookings/` | no (rate limit 5/min/IP), package opzionale richiede login studente | crea prenotazione: valida durata/slot, gestisce sessioni da 2h (unione di 2 slot da 1h, solo inizio 15:00/17:00), **identità del prenotante mai presa dal body a scatola chiusa** — studente loggato → sempre dal token; guest → `email` obbligatoria (altrimenti 422) e deve corrispondere a quella dell'utente indicato da `user_id`, altrimenti 403 (vedi §7.7) —, redenzione pacchetto verificata contro l'utente **autenticato** (mai contro `user_id` nel body), claim atomico dello slot, prezzo server-side, evento Calendar, email+Discord |
| **PATCH** | **`/bookings/{id}/cancella`** | studente (JWT Discord) | cancellazione self-service di una propria prenotazione futura |
| **GET** | **`/bookings/recensioni/pubbliche`** | no | recensioni approvate, per la vetrina in `about.html` |
| **POST** | **`/bookings/{id}/recensione`** | no (token monouso nel body, rate limit 5/min) | lascia una recensione tramite il link ricevuto via email |

### `/users` (`backend/routers/users.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/users/` | admin | tutti gli utenti |
| GET | `/users/me` | studente (JWT Discord, cookie httpOnly) | profilo proprio |
| GET | `/users/me/prenotazioni` | studente | storico proprie prenotazioni |
| POST | `/users/` | no (rate limit 5/min/IP) | get-or-create per email; risponde solo `{"id": ...}` (non l'intero profilo) |
| **GET** | **`/users/pacchetti-attivi`** | studente (JWT, no più `?email=`) | pacchetti attivi con sessioni residue dell'utente autenticato |

### `/consulenze` e `/pacchetti-richieste` (nuovi, non toccano slot/booking)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| POST | `/consulenze/` | no (rate limit 5/min) | richiesta di call conoscitiva gratuita — solo contatto, il coach richiama a mano |
| POST | `/pacchetti-richieste/` | no (rate limit 5/min) | richiesta di attivazione pacchetto — solo contatto, l'admin lo crea davvero dopo il pagamento fuori app |

### `/admin/*` (`backend/routers/admin/`, package) — tutti richiedono JWT admin tranne `/admin/login`
| Metodo | Path | Cosa fa |
|---|---|---|
| POST | `/admin/login` | rate limit 5/min/IP; verifica contro `ADMIN_USERNAME`/**`ADMIN_PASSWORD_HASH`** (bcrypt, non più in chiaro) |
| GET | `/admin/dashboard` | numeri chiave + prossimi slot liberi. Nota: `media_voto_recensioni` è calcolata su **tutte** le recensioni ricevute, anche quelle non ancora approvate — è un dato interno per il coach, diverso da quello che il pubblico vede in `about.html` |
| GET | `/admin/analytics` | sessioni/incasso, servizi più richiesti, no-show rate, clienti nuovi/ricorrenti — tutte le metriche sulla stessa finestra degli ultimi 12 mesi (`MESI_FINESTRA_ANALYTICS`, vedi §12) |
| GET | `/admin/prenotazioni` | lista paginata |
| PATCH | `/admin/prenotazioni/{id}/stato` | cambia stato |
| PATCH | `/admin/prenotazioni/{id}/note` | imposta `note_admin` |
| GET | `/admin/export/csv` | export completo, non paginato di proposito |
| GET | `/admin/clienti` | lista clienti paginata con statistiche aggregate |
| **DELETE** | **`/admin/clienti/{user_id}`** | **cancellazione GDPR completa**: utente + prenotazioni + recensioni + note + pacchetti, libera lo slot se occupato |
| GET/POST | `/admin/clienti/{user_id}/note` | note tecniche cliente |
| GET | `/admin/slots` | lista slot paginata |
| POST | `/admin/slots/sync-calendario` | blocca slot sovrapposti a eventi Calendar esterni |
| DELETE | `/admin/slots/{id}` | elimina slot (rifiuta se ha prenotazioni collegate) |
| GET/POST | `/admin/disponibilita/regole` + DELETE `/{regola_id}` | regole ricorrenti |
| GET/POST | `/admin/disponibilita/blocchi` + DELETE `/{blocco_id}` | blocchi eccezionali |
| **GET/POST** | **`/admin/pacchetti`** | lista/crea pacchetti per un cliente (dal catalogo fisso) |
| **GET** | **`/admin/recensioni`** (filtro opzionale `?approvata=`) + **PATCH** `/{recensione_id}` | modera recensioni (approva/ritira l'approvazione) |

### `/auth/discord` (`backend/routers/discord_auth.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/auth/discord/login` | no | redirect a Discord con parametro `state` anti-CSRF (cookie httponly/samesite=lax) |
| GET | `/auth/discord/callback` | no | verifica `state` (`secrets.compare_digest`), scambia il code, trova/crea l'utente — **si collega a un utente esistente trovato per email solo se Discord la marca `verified`** (vedi §7.7), altrimenti rifiuta il login — **imposta cookie httpOnly** `student_token` (non più nell'URL) |
| **POST** | **`/auth/discord/logout`** | no | cancella il cookie `student_token` (JS non può farlo da solo su un cookie httpOnly) |

---

## 4. Logica di business

**Prezzi** (`TABELLA_PREZZI` in `backend/routers/booking.py`, unica fonte autoritativa): **20€/ora lineare** — 1 ora = €20 (2000 cent), 2 ore = €40 (4000 cent). *(Cambiato rispetto alla versione precedente di questo documento, che riportava 35/60/80€ e un'opzione da 3 ore ormai non più presente.)* Le sessioni da 2 ore possono iniziare **solo alle 15:00 o alle 17:00** (ora italiana) e "uniscono" due slot da 1h adiacenti generati dal calendario — vincolo di prodotto deliberato, non tecnico (vedi commento in `booking.py`). Per sessioni più lunghe esistono i **pacchetti** (catalogo fisso, vedi sotto).

**Pacchetti** (`CATALOGO_PACCHETTI` in `backend/services/package_service.py`): 3 opzioni fisse — *Competitive Intro* (2×2h, €70 invece di €80), *Team Building Session* (4×2h, €130 invece di €160), *Tournament Prep* (6×2h, €190 invece di €240). Il pagamento avviene sempre fuori app: il cliente manda una richiesta di contatto (`POST /pacchetti-richieste/`), il coach lo assegna davvero dal pannello admin dopo aver ricevuto il pagamento. Da lì il cliente (loggato via Discord) può "spendere" le sessioni residue prenotando slot a prezzo 0.

**Stati prenotazione**: `confirmed` (default, subito al submit) → `cancelled` (libera lo slot, elimina evento calendario — sia da admin sia self-service cliente) oppure `no_show`.

**Recensioni**: dopo ogni sessione conclusa, un job notturno manda un'email con un link contenente un token monouso (`review_token`); il cliente lascia voto+commento senza bisogno di login; **non è pubblica finché il coach non la approva** dal pannello admin; solo le approvate compaiono nella vetrina di `about.html`.

**Flusso cliente** (`frontend/index.html` + `js/app.js`): wizard di prenotazione, guest checkout sempre il percorso normale, login Discord opzionale per usare pacchetti/vedere lo storico/cancellare da soli.

**Flusso admin** (`frontend/admin.html` + `js/admin.js`): dashboard, prenotazioni, clienti (incl. cancellazione GDPR), slot/disponibilità, **pacchetti**, **recensioni** (moderazione).

**Limiti anti-abuso**: massimo 2 prenotazioni `confirmed` con slot futuro per lo stesso `user_id`; rate limiting 5 richieste/minuto per IP su tutti gli endpoint pubblici di scrittura (`/users/`, `/bookings/` POST/recensione, `/consulenze/`, `/pacchetti-richieste/`) **e ora anche su `/admin/login`**.

---

## 5. Variabili d'ambiente

**L'elenco completo sta in un posto solo: la tabella di `README.md`**, che riporta tutte e 32 le variabili lette dal codice con obbligatorietà, default e descrizione. `.env.example` ne è il calco eseguibile (riverificato allineato il 2026-09-02: tolta `SECRET_KEY`, che nessuna riga leggeva; aggiunta `LOG_LEVEL`, che invece lo era).

Qui non se ne tiene una seconda copia di proposito. Due tabelle della stessa cosa divergono — è una certezza, non un rischio — ed è lo stesso principio per cui `nixpacks.toml` è dichiarato unica fonte di verità per il comando di avvio (§1). Prima questa sezione elencava "le differenze rispetto alla versione precedente di questo documento": una colonna leggibile solo da chi avesse sotto mano un testo che esiste solo nella storia git, cioè lo stesso difetto che §2 e §7 hanno già eliminato riportando per intero ciò che delegavano.

Restano qui, perché sono fatti sullo **stato del deploy** e non documentazione delle variabili:

- La configurazione su Railway è **divisa fra i due servizi senza un criterio**, ed è quell'asimmetria ad aver prodotto la copia divergente di `GMAIL_REFRESH_TOKEN` trovata il 2026-09-02. Consolidamento ancora aperto: §9.1, voce 8. Dettaglio in §13.1 e in `RAILWAY_RIALLINEAMENTO_2026-09-02.md`.
- Le variabili `MYSQL*` del servizio database **non vanno toccate**: le genera e consuma Railway (`MYSQL_ROOT_PASSWORD` e `MYSQL_DATABASE` sono lette dal container all'avvio, rimuoverle romperebbe il database).
- `ADMIN_PASSWORD_HASH` ha sostituito `ADMIN_PASSWORD` in agosto, ma la vecchia variabile in chiaro è rimasta sul servizio MySQL fino al 2026-09-02, quando è stata rimossa insieme a `SECRET_KEY` e `PAYPAL_EMAIL` (§13.1).
- `DRIVE_REFRESH_TOKEN` usa l'account Google **reale** del coach, non il service account di Calendar: un service account non ha quota di storage propria su Drive (§6).

---

## 6. Servizi esterni

- **Gmail API (OAuth2)** — email transazionali. Il progetto Google Cloud OAuth resta in stato "Testing" (non verificato): `GMAIL_REFRESH_TOKEN` scade dopo **7 giorni, a prescindere dall'uso** — non per inattività, come si è creduto a lungo: il 2026-09-02 è scaduto pur essendo esercitato ogni giorno (vedi §13.5). Un job notturno (`controlla_credenziali_gmail`) verifica automaticamente e avvisa su Discord solo alla transizione ok→rotto; **rileva** la scadenza, non la previene. Rinnovo manuale: `python scripts/reauth_gmail.py`.
- **Google Calendar** — service account, scrittura (crea/elimina evento a ogni prenotazione/cancellazione) + lettura (sync automatico ogni ora via job, oltre al bottone admin manuale).
- **Google Drive (nuovo)** — backup automatico notturno del database (dump SQL scritto a mano via PyMySQL, non `mysqldump`) via OAuth2 con l'account reale del coach (**non** un service account — un service account non ha quota di storage propria su Drive, scoperto testando). Rinnovo: `python scripts/reauth_drive.py`.
- **Discord** — webhook in uscita (notifiche prenotazione/promemoria/alert di sistema) + OAuth2 in entrata (login studenti, ora con protezione CSRF via parametro `state`).
- **Railway** — hosting app + MySQL, build via Nixpacks. Piano Hobby: **nessun backup/PITR gestito dalla piattaforma** (da cui il backup homemade su Drive sopra). URL pubblico: `https://vgc-coaching-production.up.railway.app`.
- **GitHub Actions (nuovo)** — CI: `.github/workflows/tests.yml` esegue l'intera suite pytest su ogni push/PR (Python 3.11, nessun DB reale necessario — SQLite in-memory). Verde dal 2026-08-26.

---

## 7. Vincoli tecnici e comportamenti non ovvi

I quattro punti ereditati dalle versioni precedenti di questo documento, riportati per esteso invece che delegati a un testo non più consultabile:

- **Tutti i datetime nel database sono UTC "naive"** — salvati senza fuso, ma da leggere sempre come UTC. La conversione da/verso Europe/Rome avviene solo ai bordi: in ingresso nel validator di `SlotCreate`, in uscita in `SlotResponse` e nei service che formattano per il coach (`timezone_service.py`). Mai nel mezzo.
- **Il claim dello slot è atomico**, non "leggi e poi scrivi": un `UPDATE slots SET is_available=0 WHERE id=? AND is_available=1` con controllo di `rowcount`. Deliberatamente **nessun vincolo UNIQUE** a schema, perché incompatibile col flusso cancella/riprenota (uno slot cancellato torna prenotabile).
- **Le migrazioni girano a ogni avvio e non bloccano il boot**: `run_migrations()` è dentro un `try/except` che, se fallisce, lascia partire l'app registrando l'errore e mandando un alert Discord. Scelta deliberata: un deploy con migrazione fallita si nota subito, invece che al primo cliente che usa la funzione nuova.
- **SMTP diretto è bloccato dalla rete di Railway** (`OSError: Network is unreachable`): le email passano dall'API Gmail via HTTPS con OAuth2, non da una password SMTP.

Aggiunte rilevanti dopo il 19/08 — le voci di questo elenco sono citate altrove nel documento come §7.1, §7.2 e così via, pur non essendo sottosezioni con un proprio titolo:

1. **Prenotazioni da 2 ore ora uniscono due slot da 1h** (`slot_id_secondario`), non un unico slot da 2h come generato in origine — il calendario genera solo slot da 1h; vedi §4.
2. **Token JWT studente in cookie httpOnly**, non più in `localStorage`/header `Authorization` — `secure` derivato da `DISCORD_OAUTH_REDIRECT_URI` (inizia con `https://`?), non da `request.url.scheme` (Railway strip-a HTTPS prima che l'app veda la richiesta). Verificato end-to-end in produzione il 2026-09-02 con un vero login Discord: `student_token` risulta marcato `Secure` e `HttpOnly` in DevTools (vedi §9 e §13.1).
3. **Redenzione pacchetto**: la proprietà va sempre verificata contro l'utente **autenticato** dal token, mai contro un `user_id`/`package_id` dichiarato dal client — era il gap di sicurezza HIGH trovato e corretto nell'audit del 25/08 (permetteva furto di crediti pacchetto).
4. **Retention GDPR automatica**: un cliente inattivo da oltre `RETENTION_MONTHS` mesi (nessuna prenotazione/pacchetto recente) viene anonimizzato (non cancellato) da un job notturno — prenotazioni/pacchetti restano per analytics/storico, solo l'identità (nome/email/contatti Discord) viene rimossa.
5. **`AvailabilityRule.attiva` ora è davvero usato**: prima esisteva come colonna inerte, ora `genera_slot_giornaliero` (job notturno) filtra solo le regole attive.
6. **Backup pre-migrazione**: se all'avvio ci sono migrazioni Alembic in sospeso, l'app tenta un backup su Drive PRIMA di applicarle (fail-soft: un backup fallito o non configurato non blocca comunque la migrazione).
7. **Identità mai presa da un valore dichiarato dal client/provider esterno, senza verificarla**: sessione 31/08 (§12) — stessa classe di problema già chiusa una volta sul lato pacchetti (punto 3 sopra), riemersa altrove.
   - Creazione prenotazione (`POST /bookings/`): per lo studente loggato l'identità viene sempre dal token (`studente.id`), mai da `booking.user_id`. Per il guest checkout (nessun account, scelta di prodotto) non esiste un token da cui derivarla — `BookingCreate.email` deve corrispondere all'email dell'utente indicato da `user_id`, altrimenti 403.
   - Login Discord (`backend/routers/discord_auth.py`): un utente esistente viene collegato per email SOLO se Discord garantisce che è verificata (`discord_user["verified"]`) — altrimenti il login è rifiutato invece di agganciarsi a un account altrui.
8. **`/admin/analytics` a finestra fissa**: tutte e sei le metriche (non solo sessioni/incasso per mese, come prima) condividono la stessa finestra mobile di `MESI_FINESTRA_ANALYTICS` mesi (12, `backend/routers/admin/dashboard.py`), filtrata a livello query invece di scaricare l'intera storia delle prenotazioni in RAM.
9. **I job cron usano il fuso del processo, non Europe/Rome.** `BackgroundScheduler()` è costruito senza `timezone=`, quindi gli orari dei job notturni (03:00, 03:01, 03:02, 04:00) sono ore locali del processo. Su Railway il processo gira in UTC: il backup "delle 04:00" parte in realtà alle 06:00 italiane d'estate e alle 05:00 d'inverno. In locale sono davvero le 03:00/04:00 italiane. Nessun impatto pratico — restano ore a basso traffico — ma va saputo prima di leggere un log o di aspettarsi un file a un'ora precisa.
10. **Migrazioni e scheduler partono dal `lifespan`, non dall'import** (dal 2026-09-02, §13): il semplice `import backend.main` non ha più effetti collaterali. Prima li aveva, e la conseguenza era che lanciare `pytest` con un `.env` popolato applicava le migrazioni al database di sviluppo reale.
11. **Non citare i markdown per numero di riga.** I riferimenti tipo `README.md:217` si rompono nel giro di giorni: di due citati in `ANALISI_2026-08-31.md`, entrambi puntano oggi a tutt'altro contenuto. Citare invece il titolo di sezione (`§7.7`, "Area Sicurezza"), che sopravvive alle riscritture. Vale sia fra documenti sia nei commenti del codice.

---

## 8. Modifiche recenti (rispetto alla struttura del 19/08)

**Batch prodotto, commit `aa1e235` (2026-08-21)**: sessioni 1h/2h flessibili, cancellazione self-service, sistema recensioni con approvazione admin, pacchetti di sessioni, categoria cliente (junior/senior/master) al posto di showdown username, alert Discord automatici (token Gmail scaduto, migrazioni fallite), favicon, prima suite di test (19 test).

**Conformità GDPR (2026-08-25)**: rate limiting su `/admin/login`; password admin da plaintext a hash bcrypt (`ADMIN_PASSWORD_HASH`); informativa privacy pubblicata (`/privacy`); endpoint di cancellazione dati (`DELETE /admin/clienti/{id}`); retention automatica con anonimizzazione notturna.

**Audit di sicurezza (2026-08-25)**: 1 HIGH (furto credito pacchetto via IDOR, vedi §7.3) + 4 MEDIUM (info-disclosure su pacchetti attivi, profilo esposto da `POST /users/`, CSRF su Discord OAuth, HTML injection nelle email admin) — tutti corretti.

**Enterprise-hardening, 13 item (2026-08-25)**: rifiuto slot passati, `pool_pre_ping`, indici su colonne calde, fix N+1 nello scheduler, logging strutturato al posto di 38 `print()`, coverage test (64%→67%), test sui router prima scoperti, backup automatico su Drive, CI GitHub Actions, backup pre-migrazione, `/health` reale, cookie httpOnly, split di `admin.py` in package.

**Fix CI (2026-08-26)**: `pythonpath = .` in `pytest.ini`, `DATABASE_URL`/`JWT_SECRET` fittizie nel workflow — CI verde end-to-end.

---

## 9. Cosa funziona e cosa no, ad oggi

**Verificato**:
- Tutto quanto già verificato end-to-end in produzione al 19/08 (slot → prenotazione → email → Calendar → Discord → CSV, endpoint protetti → 401 senza token).
- **Suite verde.** Il numero di test e la coverage cambiano a ogni sessione: per averli aggiornati si esegue il comando della CI — `DATABASE_URL="sqlite:///:memory:" JWT_SECRET="..." pytest` — invece di fidarsi di un numero scritto qui. Al 2026-09-02: **83 test, coverage 77%** (era 82/80% prima che il codice di avvio uscisse dall'import, vedi §13).
- **CI verde** su ogni push/PR (GitHub Actions) — riconfermato sul push del 01/09 (18 commit, `1732fc2..61d4554`, run `33529945237`), non solo assunto dalla suite locale. Riconfermato di nuovo sul push del 03/09 (8 commit, `61d4554..1e17319`, run `33690855235`), che ha portato in remoto tutto il lavoro della revisione (vedi §13.4).
- Backup su Google Drive verificato end-to-end con un dump reale, **e confermato il 2026-09-02 che la cartella Drive contiene backup prodotti dalla produzione**, non solo dalle prove in locale.
- Login admin con la nuova password hashata, verificato live dopo il deploy.
- **Login Discord studente end-to-end in produzione, verificato il 2026-09-02** — con cookie `student_token` marcato `Secure` e `HttpOnly`, controllato da DevTools. Da annotare perché non era solo "non verificato": **non poteva funzionare**, mancavano `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` su entrambi i servizi Railway (vedi §13).
- **Schema di produzione allineato**: `alembic_version` risulta `2eac6f32b19b`, la head della catena in §2.
- **Variabili d'ambiente su Railway verificate** su entrambi i servizi il 2026-09-02, e riallineate (§13).

### 9.1 Backlog aperto — elenco unico

Prima esistevano cinque elenchi paralleli (qui, §11, §12, §13.5, §13.6) e una voce chiusa in una sessione restava "aperta" in quello di un'altra: è successo davvero, con il login Discord e il backup notturno. **Questo è l'unico elenco da consultare**; quelli dentro le sezioni-diario sono congelati. Nessuna voce è bloccante e nessuna richiede di scrivere codice applicativo.

**Con una data d'innesco**

1. **Schermata di consenso OAuth Google da "Testing" a "In production"** (Google Cloud Console). Aperta dal 25/08. Finché resta in "Testing", `GMAIL_REFRESH_TOKEN` e `DRIVE_REFRESH_TOKEN` scadono dopo **7 giorni a prescindere dall'uso** — non per inattività: il 2026-09-02 il token Gmail è scaduto pur essendo esercitato ogni giorno, ed è stato rinnovato a mano. **Verificato il 2026-09-03: lo stato è ancora "Testing"**, quindi il prossimo scadere è atteso **entro il 2026-09-09**. È l'unica voce di questo elenco con una scadenza vera. Origine §12, dettaglio §13.5.

**Rischi silenziosi — si scoprono a danno avvenuto**

2. **`DRIVE_REFRESH_TOKEN` non ha nessun healthcheck.** Quello schedulato controlla solo Gmail (`controlla_credenziali_gmail`): un token Drive morto si scopre dall'alert di backup fallito, cioè a copia di sicurezza già saltata, fino a 24 ore dopo. Al 2026-09-03 il file più recente nella cartella Drive è del **2 settembre** e non risulta nessun alert Discord — il token era valido a quell'esecuzione, il che non dice nulla sulla successiva. Origine §13.6.
3. **Uptime monitor esterno su `/health`, mai configurato.** Confermato osservativamente il 2026-09-02: nei log Railway non compare nessuna chiamata a quell'endpoint. L'endpoint funziona (interrogato a mano risponde), semplicemente nessuno lo interroga — quindi un sito giù si scopre da un cliente che si lamenta. Origine §11, riconfermato §13.5.
4. **Azioni GitHub su Node.js 20 deprecato.** `actions/checkout@v4` e `actions/setup-python@v5` vengono forzate su Node.js 24 con un'annotazione. Oggi la CI è verde; quando GitHub ritirerà il fallback si fermerà, senza preavviso e in un momento a caso. Si risolve alzando la versione delle due action in `.github/workflows/tests.yml`. Origine §13.5.

**Verifica ricorrente, non evento singolo**

5. **Che l'auto-deploy Railway abbia raccolto la punta di `origin/master`** — da confermare in dashboard **a ogni push**, non una volta sola. È l'unica cosa che separa "il codice è su GitHub" da "il codice è in produzione", e questo progetto quella distinzione l'ha già persa due volte. Il push del 2026-09-03 (`1e17319`) non è mai stato confermato in dashboard, e da allora sono arrivati `6348fa1` e `8c3dd56`. Origine §13.4.

**Da provare quando si presenta l'occasione**

6. **Che il link nell'email di richiesta recensione sia cliccabile.** Serve una sessione già conclusa; al 2026-09-02 non ce n'erano. La correzione vale solo per le email future: le richieste già inviate non verranno rimandate, perché il job filtra su `review_email_sent == False`. Origine §13.1, §13.6.
7. **Le due correzioni di sicurezza Alta severità del 31/08** (§7.7): coperte dalla suite automatica, con test che riproducono l'abuso e lo dimostrano bloccato, ma mai provate con un vero tentativo contro l'ambiente di produzione. Origine §12.

**Facoltative, o già decise**

8. **Consolidamento delle variabili Railway su un solo servizio.** Oggi sono divise fra i due senza un criterio, ed è proprio quell'asimmetria ad aver prodotto la copia divergente di `GMAIL_REFRESH_TOKEN` trovata il 02/09. Origine §13.1.
9. **Rotazione della password MySQL** esposta in git dal commit `15f536d` (giugno). **Rimandata deliberatamente**, non dimenticata: decisione presa il 2026-09-03 con l'informazione giusta, cioè che riguarda il database di **sviluppo locale**, mentre la produzione usa credenziali generate da Railway e mai finite in git. Da riconsiderare se quel database locale diventasse raggiungibile da fuori. Origine §12, §13.5.
10. **Dominio personalizzato** non acquistato — resta su `*.up.railway.app`, scelta consapevole. Da riconsiderare se servisse un'immagine più professionale o SPF/DKIM/DMARC veri. Origine §11.

---

## 10. Sessione 2026-08-19 — deploy in produzione

*(Invariata rispetto alla versione precedente di questo documento — riattivazione Railway, pulizia branch GitHub, migrazione email SendGrid→Gmail API, fix `GET /slots/`, reset DB produzione, collaudo end-to-end. Non ripetuta qui, vedi git history/commit `3260848` per il dettaglio.)*

---

## 11. Sessione 2026-08-25/26 — GDPR, sicurezza, enterprise-hardening, CI

Sessione dedicata a portare il progetto da "funzionante" a "pronto per traffico pubblico reale", su richiesta esplicita di una revisione "Principal Engineer" (architettura, sicurezza OWASP, performance, manutenibilità) con target single-tenant (non multi-tenant enterprise, deliberatamente fuori scopo — vedi §5-6 sopra per il riassunto dei risultati). In breve, in ordine cronologico:

1. Audit privacy/GDPR → 5 gap trovati e corretti (rate limit login, hash password, privacy policy, cancellazione dati, retention automatica).
2. Audit sicurezza separato → 1 HIGH + 4 MEDIUM trovati e corretti (vedi §8).
3. Punch list enterprise-readiness a 13 item, tutti completati (vedi §8).
4. Pass di pulizia pre-commit (`/simplify`): 9 problemi reali trovati e corretti (N+1 reintrodotto nella retention, duplicazione di codice OAuth/env-utils/query eager-load, standardizzazione escaping email).
5. Deploy in produzione: variabili Railway aggiornate (incluso lo scambio `ADMIN_PASSWORD`→`ADMIN_PASSWORD_HASH`, con una breve finestra di login admin rotto tra l'update delle variabili e il deploy del codice, risolta subito), verificato live.
6. Il giorno dopo (26/08): la CI, mai verificata end-to-end fino a quel momento, risultava rotta silenziosamente dal primo run — tre fix in sequenza (`pythonpath`, `DATABASE_URL` fittizia, `JWT_SECRET` fittizia) fino al verde.

### Backlog / follow-up al 2026-08-26 (chiuso)

> *Elenco congelato: fotografia di com'era alla chiusura di questa sessione. Le voci ancora aperte oggi stanno tutte in **§9.1**, che è l'unico da consultare.*

- ~~Login Discord OAuth reale in produzione, per confermare il flusso cookie httpOnly end-to-end.~~ **Fatto il 2026-09-02**: mancavano `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` su Railway — aggiunte, flusso provato end-to-end, cookie `Secure`+`HttpOnly` confermato (§13.1).
- Uptime monitor esterno (UptimeRobot/Better Uptime) su `/health`. **Ancora aperto al 2026-09-03** (§13.5).
- ~~Conferma che il backup notturno (04:00) produca davvero un file in produzione, non solo in locale.~~ **Fatto il 2026-09-02**: la cartella Drive contiene backup prodotti dalla produzione (§9).
- Dominio personalizzato — non fatto per scelta, da riconsiderare se serve un'immagine più professionale o SPF/DKIM/DMARC veri.

---

## 12. Sessione 2026-08-31/09-01 — review indipendente e chiusura findings

Su richiesta esplicita di una code review indipendente ("senior full-stack
engineer, impronta back-end"), prodotta come `ANALISI_2026-08-31.md`
(root del progetto — vedi quel file per l'analisi completa, area per
area, con voti e riferimenti `file:riga`). Di seguito solo la sintesi di
cosa è stato corretto in questa sessione, in ordine cronologico:

0. Messa in sicurezza del lavoro pregresso: 22 file modificati + 2 nuovi
   (`backend/services/pagination_service.py`, `tests/test_availability.py`)
   risultavano non committati da una sessione precedente — committati in
   blocco prima di qualunque fix. Ambiente locale allineato a
   produzione/CI: venv ricreato su Python 3.11 (era 3.14). Il giorno dopo
   (01/09) i 18 commit risultanti sono stati pushati su `origin/master`
   (`1732fc2..61d4554`) e la CI verificata verde sul push reale, non solo
   sulla suite locale — il lavoro non esiste più solo su questa macchina.
1. **Sicurezza, Alta severità (2 bug chiusi)**:
   - `backend/routers/discord_auth.py`: il login Discord collegava un
     account esistente trovato per email SENZA controllare il flag
     `verified` restituito da Discord — un attaccante poteva aggiungere
     l'email non verificata di un cliente al proprio account Discord e
     ottenere un cookie di sessione legato alla sua identità (storico
     prenotazioni, pacchetti residui). Fix: il fallback per email avviene
     solo se `verified` è vero; altrimenti il login viene rifiutato.
   - IDOR su `booking.user_id` (`backend/routers/booking.py`,
     `backend/schemas/booking.py`): chiunque poteva creare prenotazioni
     "confirmed" a nome di un altro cliente esistente (in produzione una
     PK sequenziale, banale da indovinare). Fix: studente loggato →
     identità sempre dal token; guest checkout → `BookingCreate` verifica
     che l'email dichiarata corrisponda davvero a `user_id`.
2. **Privacy/performance/accessibilità (quick-win)**:
   - `note_admin` (documentato come "visibile solo al coach") non compare
     più nella risposta di `PATCH /bookings/{id}/cancella` (nuovo schema
     `BookingResponseStudente`).
   - `/admin/analytics` filtra ora a livello DB invece di scaricare in RAM
     tutta la storia delle prenotazioni — finestra estesa a 12 mesi
     (`MESI_FINESTRA_ANALYTICS`) su richiesta esplicita, dopo un primo
     fix a 6 mesi.
   - Le card slot del form pubblico sono ora `<button>` veri, raggiungibili
     da tastiera (prima `<div onclick>`, unico punto del flusso di
     prenotazione non accessibile).
3. **Debito di test colmato**: `controlla_e_invia_promemoria` e
   `controlla_e_invia_richieste_recensione` (`backend/scheduler.py`, prima
   completamente scoperti nonostante girino senza supervisione umana),
   calcoli di `/admin/analytics` verificati con dati noti,
   `pagination_service.py` portato al 100% di coverage. Suite: 54 → **82
   test**, coverage 67% → **80%**.
4. **Igiene**: rimossa `SECRET_KEY` **dalla tabella del README** (var
   d'ambiente mai letta; è poi rimasta in `.env.example` e su Railway fino
   al 2026-09-02, vedi §13), corretto un commento obsoleto in `admin.js`
   sul token studente, rimosso `frontend/Architettura.txt` (già segnalato
   come obsoleto), `nuovo_stato`/`note` di `PATCH /admin/prenotazioni/{id}/*`
   passati da query param a body JSON (finivano nei log di accesso),
   eliminato un N+1 residuo in `elimina_cliente`.

### Checklist identità — da applicare a ogni endpoint nuovo che legge, scrive o collega un'identità utente
1. L'endpoint legge/scrive un dato collegato a un `user_id`? Quell'`user_id`
   deve venire da `get_studente`/`get_admin` (JWT verificato), MAI da un
   campo del body/query dichiarato dal client.
2. Se il client sceglie QUALE risorsa toccare (es. l'admin che gestisce un
   cliente), l'identità dell'ATTORE resta comunque quella del token — il
   BERSAGLIO va sempre validato con un `.filter()` esplicito di
   appartenenza, mai un UPDATE/DELETE su un id nudo.
3. Un'email da un provider OAuth (Discord, Google...) usata per
   collegare/creare un utente? Controlla il flag `verified` del provider
   prima di fidartene.
4. Esiste un test che prova l'azione COME UN ALTRO UTENTE (id/email
   diverso da chi detiene il token) e verifica un 403/404? Se manca,
   l'area non è coperta indipendentemente dalla percentuale di coverage
   totale.

### Backlog / follow-up al 2026-09-01 (chiuso)

> *Elenco congelato: fotografia di com'era alla chiusura di questa sessione. Le voci ancora aperte oggi stanno tutte in **§9.1**, che è l'unico da consultare.*

- Screen di consenso OAuth Google: portarlo da "Testing" a "In production"
  (Google Cloud Console) — elimina la scadenza dei refresh token Gmail/Drive
  invece di limitarsi all'alert automatico. **Ancora aperto al 2026-09-03**, e
  nel frattempo la scadenza si è materializzata davvero (§13).
- Confermare/eseguire la rotazione della password MySQL esposta in chiaro
  nella storia git (commit `15f536d`, mai confermata fatta —
  `ROADMAP.md` la segnava "todo"). **Rimandata deliberatamente al 2026-09-03**,
  valutata non necessaria per ora: riguarda il database di **sviluppo locale**,
  mentre la produzione su Railway usa credenziali separate, generate dalla
  piattaforma e mai finite in git. Vedi §13.5.
- ~~Verificare che le variabili d'ambiente reali su Railway riflettano
  `.env.example` aggiornato.~~ **Fatto il 2026-09-02, vedi §13.**

---

## 13. Sessione 2026-09-01/03 — revisione documentale in tre parti

Revisione strutturata in tre sessioni con un obiettivo dichiarato: **rendere i documenti
markdown un ritratto fedele del codice**, perché chi apre il progetto fra tre mesi possa
fidarsene senza rileggere tutto. Referto completo in **`REVISIONE_2026-09-01.md`** (root):
fotografia del codice a freddo, 29 rilievi documentali approvati voce per voce, ritrovamenti
di codice e di configurazione. Runbook operativo dell'intervento su Railway in
**`RAILWAY_RIALLINEAMENTO_2026-09-02.md`**.

Le tre sessioni, in ordine: **analisi** (nessuna modifica, solo il referto) → **codice**
(correzioni + test) → **documenti** (allineamento). I documenti sono rimasti volutamente
disallineati fra la prima e la terza, per non riscrivere due volte le correzioni che il lavoro
sul codice avrebbe reso obsolete.

### 13.1 Configurazione Railway — riallineata

L'analisi delle variabili d'ambiente ha trovato **3 problemi con effetto reale in produzione**,
tutti corretti il 2026-09-02:

1. **Il login Discord non poteva funzionare.** `DISCORD_CLIENT_ID` e `DISCORD_CLIENT_SECRET`
   **non esistevano su nessuno dei due servizi** Railway: `discord_login()` costruiva l'URL di
   autorizzazione con `client_id=None`. Non era "non ancora verificato", era rotto. Aggiunte, e
   il flusso è stato provato end-to-end con esito positivo.
2. **Le email di richiesta recensione contenevano un link non cliccabile.** `PUBLIC_BASE_URL`
   non era impostata, quindi il codice ricadeva sulla prima origine di `FRONTEND_ORIGINS` —
   che era un hostname **senza schema**. Impostata; aggiunto `https://` anche a
   `FRONTEND_ORIGINS`, che senza schema non poteva combaciare con nessun header `Origin`.
3. **I cookie di sessione uscivano senza il flag `Secure`.** `DISCORD_OAUTH_REDIRECT_URI` era
   `http://`, e da quella variabile l'app deduce di essere in produzione. Portata a `https://`
   (e allineata sul Discord Developer Portal); verificato da DevTools che `student_token` ha
   ora `Secure` e `HttpOnly`.

Pulizia, sullo stesso intervento: rimosse `SECRET_KEY` e `PAYPAL_EMAIL` (mai lette da nessuna
riga di codice), la **password admin in chiaro** `ADMIN_PASSWORD` rimasta sul servizio MySQL
dopo il passaggio a bcrypt di agosto, e una **copia divergente e non referenziata** di
`GMAIL_REFRESH_TOKEN` — pericolosa non perché occupasse spazio, ma perché al prossimo
`reauth_gmail.py` sarebbe stata il posto "naturale" dove incollare il token nuovo, quello
sbagliato. Corretto infine un refuso, `REMINDER_CHECK_INTERNAL_MINUTES`, che rendeva la
variabile invisibile al codice.

**Non toccate di proposito**: tutte le `MYSQL*` del servizio database, che Railway genera e
consuma da sé (`MYSQL_ROOT_PASSWORD` e `MYSQL_DATABASE` sono lette dal container all'avvio:
rimuoverle romperebbe il database). Resta **aperto** un consolidamento facoltativo: la
configurazione è divisa fra i due servizi senza un criterio, ed è proprio quell'asimmetria ad
aver prodotto il token divergente.

### 13.2 Codice — 5 commit

- **`1d2c850`** — `run_migrations()` e `avvia_scheduler()` spostati in un handler **`lifespan`**
  di FastAPI. Erano a livello di modulo, quindi il solo `import backend.main` — che
  `tests/conftest.py` fa — applicava le migrazioni al database di **sviluppo reale**, tentava un
  backup su Drive e poteva mandare un **alert Discord autentico**, oltre a lasciare vivo un
  thread APScheduler per tutta la suite. Nuovo `tests/test_avvio.py`, che verifica l'assenza di
  effetti collaterali facendo un import pulito in un sottoprocesso. Verificato con uvicorn reale
  che il lifespan esegua comunque migrazioni e gli 8 job all'avvio.
- **`886b10b`** — sette commenti che descrivevano comportamenti inesistenti: `attiva` data per
  inutilizzata mentre lo scheduler ci filtra; un rimando a `GET /pacchetti/attivi`, endpoint mai
  esistito; il refresh Gmail dato per rifatto a ogni invio; il docstring che prometteva di
  "disattivare" uno slot mentre solleva 400; sei rimandi a "Blocco B1/B2/C3/D4" di
  `ANALISI_2026-08-31.md`, nomenclatura che quel documento non ha mai avuto; il fuso dei job
  cron; la scadenza dei token. Nessuna riga eseguibile toccata.
- **`d3a0f32`** — nel guest checkout, `email` mancante ora risponde **422** invece di un 403
  "user_id and email do not match", che descriveva un problema diverso da quello reale. Resta
  `Optional` nello schema di proposito: lo studente loggato non la manda, la sua identità viene
  dal token.
- **`a8bc99d`** — rimosso `GET /bookings/`: nessun consumatore (verificato su frontend e test),
  restituiva tutte le prenotazioni di sempre senza paginazione. Rimosso di conseguenza un import
  diventato morto.
- **`23544db`** — rimosso `GET /slots/{slot_id}`: pubblico, senza consumatori, restituiva
  qualunque slot in qualunque stato. **La suite scende da 84 a 83 test** perché è caduto anche
  il test che lo copriva: è il test di una funzionalità eliminata di proposito, non un test
  aggiustato per farlo passare.

**Lasciato stare deliberatamente**: `/docs` pubblici (gli endpoint restano protetti, la scelta
è ora dichiarata in §3), la media voto calcolata anche sulle recensioni non approvate (dato
interno, ora dichiarato), `categoria` non anonimizzata dalla retention (non è un
identificativo), il parametro `escludi_id` mai usato (il commento accanto lo dichiara tenuto
apposta per un caso futuro), la duplicazione minima negli script.

### 13.3 Documenti — allineati

29 correzioni approvate voce per voce, più due nate dal lavoro sul codice. In sintesi:
`README.md` (inventari di model/schemi/service/router incompleti, `timezone_service` descritto
come "un'unica funzione", lo scheduler descritto come se facesse solo i promemoria, un rimando
a `backend/routers/admin.py` che non esiste più da agosto, `GET /slots/` senza il filtro sugli
orari passati, "due pagine web" invece di cinque, "tre notifiche in parallelo" che sono
sequenziali, Python "3.11+" invece di 3.11 esatta, l'healthcheck attribuito anche al token
Drive); `.env.example` (via `SECRET_KEY`, dentro `LOG_LEVEL`); questo documento (conteggio
tabelle, catena migrazioni riportata per intero invece di rimandare a una versione precedente
non consultabile, §7 espansa per lo stesso motivo, `/docs` dichiarati, fuso dei job cron);
`frontend/privacy.html` e `i18n.js` (la **fascia di esperienza** junior/senior/master era
raccolta ma non dichiarata fra i dati trattati — corretta in entrambe le lingue e data di
aggiornamento portata al 2 settembre 2026).

`ANALYSIS.md` e `ROADMAP.md` hanno ricevuto **un cartello di storicità in testa** con la data a
cui si riferiscono: restano storici di proposito e non sono stati allineati al presente.
`ANALISI_2026-08-31.md` ne ha ricevuto uno che dichiara i findings chiusi — un lettore che lo
apriva senza contesto concludeva che l'app avesse due vulnerabilità Alta severità aperte.

Le 29 correzioni riguardavano i rilievi di `REVISIONE_2026-09-01.md`, non una rilettura integrale:
una passata successiva sul solo README (§14) ha trovato altri disallineamenti che quell'elenco
non copriva. Da qui in avanti conviene leggere "allineato" come "allineato per i rilievi di quella
revisione", mai come una garanzia generale.

### 13.4 Push e CI — EFFETTUATI il 2026-09-03

**Push eseguito il 2026-09-03**: `61d4554..1e17319` su `origin/master`, **8 commit** — quello
documentale rimasto indietro dalla sessione del 01/09 (`5c495cb`), i 5 della sessione sul
codice, e i 2 del riallineamento documentale.

**CI verde sul push reale**, non solo sulla suite locale: run GitHub Actions
[`33690855235`](https://github.com/cognettadavide97-afk/vgc-coaching/actions/runs/33690855235),
`conclusion: success` sul commit `1e17319`. È la prima volta che questi commit passano dalla
CI: gira solo su push, e fino a quel momento erano rimasti tutti in locale.

Superata anche la preoccupazione che ci si era posti prima di pushare: `tests/test_avvio.py`
avvia un **sottoprocesso** ed è il primo test del progetto a farlo — poteva comportarsi
diversamente su un runner Linux rispetto al Windows locale. Non è successo.

**Prima del push**, l'ordine dei fatti era questo, e vale la pena ricordarlo perché è la
distinzione che questo progetto ha già faticato a tenere: l'intervento su Railway descritto in
§13.1 era **già in produzione** dal 2026-09-02 (sono modifiche alle variabili d'ambiente fatte
dalla dashboard, che hanno provocato un redeploy dell'immagine esistente), mentre il codice in
esecuzione era ancora quello di `61d4554`. Le correzioni di §13.2 sono arrivate in produzione
solo con questo push, e solo nella misura in cui l'auto-deploy di Railway lo ha raccolto.

> ⚠️ **Da confermare in dashboard Railway**: che il deploy automatico agganciato a
> `origin/master` sia effettivamente partito su `1e17319` e sia andato a buon fine. Il push e
> la CI sono verificati; il deploy no — è fuori dal repository e non osservabile da qui.

**Collaudo locale prima del push**, eseguito il 2026-09-03 con il `.env` reale: app avviata con
uvicorn contro il MySQL di sviluppo, avvio pulito (`Migrazioni eseguite con successo`, nessuna
migrazione in sospeso quindi nessun backup tentato, scheduler partito con tutti e 8 i job,
nessun errore nei log). Verificati: le 5 pagine HTML (4 pubbliche + `/admin-panel`), `/health`, `/slots/`,
`/bookings/recensioni/pubbliche`, `/docs` → 200; `/users/me`, `/users/`, `/admin/dashboard`
senza token → 401; `GET /bookings/` → **405** e `GET /slots/{id}` → **404**, cioè le due
rimozioni di §13.2 senza danni collaterali su `POST /bookings/`, che valida ancora
correttamente. **Non verificato dal vivo** il nuovo 422 sull'email mancante: il database di
sviluppo non aveva slot futuri disponibili e `create_booking` valida lo slot per primo, quindi
non si arriva al controllo. Resta coperto dal test automatico.

### 13.5 Backlog / follow-up al 2026-09-03 (chiuso)

> *Elenco congelato: fotografia di com'era alla chiusura di questa sessione. Le voci ancora aperte oggi stanno tutte in **§9.1**, che è l'unico da consultare.*

- **Schermata di consenso OAuth Google da "Testing" a "In production".** Ora è più urgente di
  prima: il 2026-09-02 il `GMAIL_REFRESH_TOKEN` **è scaduto davvero**, pur essendo esercitato
  ogni giorno — la scadenza è a 7 giorni a prescindere dall'uso, non per inattività come si era
  creduto. È stato rinnovato a mano. Finché si resta in "Testing", la cosa si ripeterà.
  **Verificato il 2026-09-03: lo stato è ancora "Testing".** Il prossimo scadere è quindi atteso
  entro il 2026-09-09.
- **Rotazione della password MySQL** esposta in git dal commit `15f536d` (giugno) — non fatta,
  e **rimandata deliberatamente**: il coach l'ha valutata non necessaria al momento (confermato
  il 2026-09-03), perché riguarda il database di **sviluppo locale** e la produzione su Railway
  usa credenziali separate generate dalla piattaforma. Non è una dimenticanza: è una decisione
  presa con l'informazione giusta, che prima mancava. Da riconsiderare se quel database locale
  dovesse mai diventare raggiungibile da fuori.
- ~~Push dei 6 commit e verifica che la CI resti verde.~~ **Fatto il 2026-09-03**, CI verde
  (§13.4). Resta da confermare in dashboard che l'auto-deploy di Railway sia partito.
- **Azioni GitHub su Node.js 20 deprecato.** La CI del 2026-09-03 ha prodotto questa
  annotazione: `actions/checkout@v4` e `actions/setup-python@v5` puntano a Node.js 20 e
  vengono forzate su Node.js 24. Oggi funziona e il run è verde; quando GitHub ritirerà il
  fallback, la CI si fermerà. Si risolve alzando la versione delle due action in
  `.github/workflows/tests.yml` — non urgente, ma è il tipo di cosa che rompe senza
  preavviso in un momento a caso.
- **Consolidamento delle variabili Railway** su un solo servizio (§13.1).
- **Uptime monitor esterno** su `/health`, mai configurato.

### 13.6 Non verificato al 2026-09-03 (chiuso)

> *Elenco congelato: fotografia di com'era alla chiusura di questa sessione. Le voci ancora aperte oggi stanno tutte in **§9.1**, che è l'unico da consultare.*

- Che il link nell'email di richiesta recensione sia ora cliccabile: al 2026-09-02 non
  esistevano sessioni concluse su cui provarlo. **Nota**: la correzione vale per le email
  future; le richieste già inviate non verranno rimandate, perché il job filtra su
  `review_email_sent == False`.
- Che il `DRIVE_REFRESH_TOKEN` regga fino al prossimo backup. Vale la stessa scadenza del
  token Gmail e **non esiste un healthcheck che lo controlli**: un token Drive morto si scopre
  solo dall'alert di backup fallito, quindi a copia di sicurezza già saltata. **Al 2026-09-03**
  il file più recente nella cartella Drive è datato **2 settembre** e non risulta nessun alert
  Discord — il che conferma che il token era valido a quell'esecuzione, ma **non** dice nulla
  sull'esecuzione successiva.

---

## 14. Sessione 2026-09-03 — riallineamento README e correzioni a questo file

Passata di verifica sul `README.md` contro il codice, indipendente dai 29 rilievi di §13.3.
Nessuna riga di codice toccata: solo i due markdown.

**`README.md` — un errore grafico e dodici disallineamenti di contenuto.** Il diagramma ASCII
dell'architettura aveva i riquadri sfalsati (bordi superiori da 59 caratteri contro inferiori da
61, righe di contenuto fino a 63, i tre riquadri in basso con bordi più stretti del testo che
contenevano): ridisegnato con larghezze coerenti. Sul contenuto: la **sequenza di avvio**
elencava migrazioni e scheduler in mezzo a CORS/router/static, cioè mescolava ciò che accade
all'import con ciò che accade nel `lifespan` — riscritta in due fasi distinte; **`js/i18n.js`
non era citato da nessuna parte** (l'intero sistema di traduzione IT/EN); `index.html` era
descritto come il solo wizard, senza il form di consulenza gratuita né la vetrina pacchetti;
mancavano del tutto le cartelle `scripts/`, `tests/` e `.github/` dal giro dei file, e
`pytest.ini`/`requirements-dev.txt` dalla tabella di root; gli inventari di schemi, router e
service erano incompleti negli stessi punti in cui lo erano qui (vedi sotto); il percorso di
prenotazione saltava l'unione dei due slot da 1h e il limite di 2 prenotazioni attive; il box
Gmail si **contraddiceva da solo**, spiegando che il token scade a 7 giorni a prescindere
dall'uso e poi ricadendo su "smette di scadere per inattività"; la colonna "Obbligatoria" della
tabella variabili usava due convenzioni opposte (`Sì (per le email)` ma `No (per il login
Discord)`) per dire la stessa identica cosa.

**Questo file — sette errori fattuali e una contraddizione.** Nell'albero di §1:
`google_oauth_service.py` era dato come condiviso anche con Calendar, che invece usa un service
account (§6 lo diceva già correttamente); mancava `elimina_slot_obsoleti()` da
`availability_service.py`, cioè la funzione dietro un job elencato due righe più sopra; `conftest.py`
era dato per mockare anche Drive; `requirements-dev.txt` ometteva `httpx`; `main.py` "montava" lo
scheduler, che invece parte dal lifespan; l'albero `frontend/` ometteva `fonts/`, `images/` e
`favicon.ico`; `routers/booking.py` ometteva l'invio recensione. Corretti anche i path con `{id}`
in §3 e i backref mancanti in §2.

**La contraddizione**: §7.2 dichiarava il cookie httpOnly "non ancora verificato… solo via mock +
curl", mentre §9 e §13.1 lo davano verificato end-to-end il 2026-09-02. §7 è una sezione di stato
corrente, non un verbale: la frase era semplicemente rimasta indietro ed è stata sostituita con
l'esito reale. Stessa sorte per due voci del backlog di §11 (login Discord, backup notturno reale),
chiuse altrove nel documento ma ancora elencate come aperte: ora barrate con la data, come già si
faceva in §12.

**Seconda passata, stesso giorno — riordino strutturale.** La prima passata aveva corretto errori
puntuali; il check-up successivo ha mostrato che quasi tutti nascevano dallo stesso punto, e cioè
che il documento mescola **due nature**: §1–9 descrivono lo stato presente, §10 in poi sono un
diario di sessioni. Ogni errore stava sulla cucitura — un fatto di sessione congelato in una
sezione di stato (§7.2), o un fatto di stato mai propagato all'indietro (il backlog di §11). Da qui:

- **Regola di manutenzione dichiarata in testa al documento**, così la prossima sessione ha un
  controllo meccanico invece di un giudizio: le sezioni di stato non portano date di sessione, le
  sezioni-diario non si riaprono.
- **Backlog unificato in §9.1.** Prima le voci aperte erano sparse in cinque elenchi (§9, §11, §12,
  §13.5, §13.6): chiudere una voce richiedeva di ricordarsi di barrarla anche negli elenchi delle
  sessioni precedenti, un incrocio manuale che era già fallito. Ora l'elenco è uno; gli altri
  quattro restano al loro posto ma **congelati**, con una riga che lo dichiara, perché come
  fotografia storica hanno ancora valore.
- **Questa sezione, che nasceva come sottosezione di §13, promossa a §14.** Correggeva
  un'affermazione di §13.3: annidata lì dentro, il lettore la
  trovava solo arrivando in fondo alla sezione che conteneva l'errore. §13 è stata rititolata
  `01/03` perché conteneva già §13.4 e §13.5, datate 03/09.
- **§5 riscritta.** Elencava "le differenze rispetto alla versione precedente di questo documento",
  cioè un testo consultabile solo nella storia git — lo stesso difetto che §2 e §7 avevano già
  eliminato. Ora rimanda alla tabella del README come fonte unica (verificata: copre esattamente
  le 32 variabili lette dal codice) e tiene solo i fatti sullo stato del deploy. Due tabelle della
  stessa cosa divergono, ed è il principio per cui `nixpacks.toml` è già dichiarato fonte unica
  per il comando di avvio.
- **Minori**: tolta la data dall'intestazione di §9 (le singole voci ne hanno già una propria, e una
  data di sezione dichiara freschezza per righe che non si sono mosse); censiti nell'albero i tre
  referti in root che il testo cita ma l'indice ometteva; tolto da §1 il conteggio "83 test", che
  contraddiceva la politica dichiarata da §9; tolta da §8 la frase che rimandava "alla cronologia
  del progetto" senza indicare né un commit né un file.
- **L'intestazione contraddiceva se stessa**: dichiarava che "il riferimento è una data e non un
  hash di commit, inseguire l'hash aveva già prodotto due disallineamenti" e poi inseguiva l'hash
  di HEAD, con un valore già falso poche ore dopo. Restano i due run CI, che sono eventi legati a
  un commit preciso e quindi non invecchiano.

**Cosa è stato ricontrollato e risulta corretto**, perché valga anche come referto positivo: lo
schema di §2 combacia con i model colonna per colonna; la catena delle 18 migrazioni, ricostruita
dai `down_revision`, è esattamente quella stampata e la HEAD è `2eac6f32b19b`; tutti e 24 gli
endpoint admin hanno `Depends(get_admin)` tranne `/admin/login`; prezzi, catalogo pacchetti,
ore di inizio ammesse, limite prenotazioni attive e lista degli endpoint con rate limit sono
esatti; `.env.example` coincide con le 32 variabili davvero lette dal codice; i cinque commit
citati in §13.2 esistono con quegli hash, e i conteggi (8 commit `61d4554..1e17319`, 18 commit
`1732fc2..61d4554`) tornano. Ricontrollati a macchina alla fine della seconda passata: i 13 hash
citati nel documento esistono tutti in `git log`; i numeri affermati (18 migrazioni, 8 job
scheduler, 14 file di test, 8 tabelle applicative, 32 variabili d'ambiente) combaciano con il
codice; tutti i rimandi `§x` puntano a sezioni esistenti; nessun `.md` in root manca dall'albero
di §1 e nessuno di quelli citati nell'albero manca dal disco.
