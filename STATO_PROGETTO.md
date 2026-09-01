# STATO_PROGETTO.md — VGC Coaching App

> Documento generato leggendo il codice sorgente effettivo del repository (branch `master`), **aggiornato al commit `1732fc2`, 2026-08-31**, dopo la sessione di conformità GDPR, hardening di sicurezza e enterprise-readiness del 2026-08-25/26 (sezione 11) e il fix della CI del 26/08. Aggiornato ulteriormente dopo la sessione di review indipendente e hardening del 31/08 (sezione 12), fino al commit `2114b73`. Non presuppone la lettura di nessun'altra conversazione o documento precedente. `ANALYSIS.md` e `ROADMAP.md` (presenti nella root) descrivono una sessione di sviluppo ancora precedente (agosto 2026, prime settimane) e restano **storici di proposito** — non vengono aggiornati. In caso di conflitto **questo file e il codice sorgente hanno la precedenza**.

---

## 1. Struttura del progetto

Monolite Python/FastAPI che serve sia le API REST sia i file statici del frontend (HTML/CSS/JS vanilla, nessun framework, nessuna build step) da un unico processo. Persistenza su MySQL tramite SQLAlchemy, migrazioni con Alembic.

```
.
├── .env                    # segreti reali — MAI in git
├── .env.example             # template dei nomi di variabile, allineato al codice attuale
├── .gitignore
├── .github/workflows/tests.yml  # CI: pytest su ogni push/PR, verde
├── ANALYSIS.md               # audit di una sessione di sviluppo molto precedente (storico)
├── README.md                 # guida setup/deploy, allineata al codice attuale
├── ROADMAP.md                 # piano di lavoro P0→P3 di quella stessa sessione, tutto "fatto" (storico)
├── STATO_PROGETTO.md          # questo file
├── alembic.ini                # config Alembic (sqlalchemy.url vuoto, popolato a runtime da env.py)
├── nixpacks.toml               # comando di avvio per il deploy Railway (unica fonte di verità)
├── pytest.ini                    # pythonpath=., testpaths=tests, coverage on di default
├── requirements.txt             # dipendenze Python di produzione
├── requirements-dev.txt          # dipendenze extra solo per i test (pytest, pytest-cov)
├── alembic/
│   ├── env.py                    # config runtime migrazioni; salta fileConfig() se il root logger ha già handler
│   ├── script.py.mako             # template per nuove migrazioni
│   └── versions/                   # 18 migrazioni, vedi sezione 2 per la catena in ordine
├── scripts/                    # utility one-off da lanciare a mano dal computer del coach, mai su Railway
│   ├── _env_utils.py              # helper condiviso per aggiornare .env locale
│   ├── hash_admin_password.py      # genera ADMIN_PASSWORD_HASH da una password digitata
│   ├── reauth_gmail.py              # rinnova GMAIL_REFRESH_TOKEN (OAuth2, apre il browser)
│   └── reauth_drive.py               # rinnova DRIVE_REFRESH_TOKEN (OAuth2, apre il browser)
├── tests/                      # 82 test, SQLite in-memory, tutte le integrazioni esterne mockate
│   ├── conftest.py                # fixture condivise: DB isolato, mock Gmail/Discord/Calendar/Drive, helper auth
│   ├── test_admin.py, test_booking.py, test_slots.py, test_richieste.py, test_discord_auth.py,
│   │   test_email_service.py, test_retention.py, test_backup_service.py, test_health.py, test_reviews.py,
│   │   test_availability.py, test_scheduler.py, test_pagination_service.py
├── backend/
│   ├── main.py                      # entrypoint: logging, migrazioni (+ backup pre-migrazione), crea l'app,
│   │                                  monta router/static/scheduler, CORS ristretto, rate limiter
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
│   │   ├── booking.py                      # prenotazioni, cancellazione self-service, recensioni pubbliche
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
│       ├── availability_service.py             # genera slot da regola ricorrente, controllo overlap, applica blocchi
│       ├── calendar_service.py                  # Google Calendar: crea/elimina/legge eventi
│       ├── email_service.py                      # invio email transazionali via Gmail API (OAuth2), HTML-escaping
│       ├── discord_service.py                     # notifiche via webhook Discord + alert di sistema
│       ├── retention_service.py                    # anonimizzazione GDPR clienti inattivi
│       ├── backup_service.py                        # dump SQL + upload su Google Drive
│       ├── google_oauth_service.py                   # credenziali OAuth condivise (Gmail + Calendar + Drive)
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
    └── js/app.js, admin.js, about.js, i18n.js, recensione.js
```

---

## 2. Schema del database

MySQL, **9 tabelle attive**. Nessun ORM "autogenerate": ogni migrazione in `alembic/versions/` è scritta a mano.

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

Relazioni: `Booking.user` / `Booking.slot` / `Booking.slot_secondario` / `Booking.package` (many-to-one); backref `User.bookings`, `Slot.booking`, `Package.bookings`.

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
Le prime 12 sono descritte in dettaglio nella versione precedente di questo documento (crea tabelle iniziali → discord_id). Aggiunte dopo il 19/08:
```
0bfc529cd9fd  aggiungi discord_id a users
  → a1c92f7e4b18  categoria al posto di showdown_username su users
    → b3d84a19e6f2  crea tabella packages
      → c5f612a8d9e3  crea tabella reviews
        → d4a72e0f8b31  aggiungi slot_id_secondario a bookings
          → a1b2c3d4e5f6  aggiungi approvata a reviews
            → 215aa000de4b  indici su slots.start_time e bookings.status
              → 2eac6f32b19b  aggiungi anonimizzato_at a users   [HEAD]
```

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

### `/slots` (`backend/routers/slots.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/slots/` | no | slot con `is_available=True` e `start_time` non ancora passato |
| GET | `/slots/{id}` | no | un singolo slot, qualsiasi stato |
| POST | `/slots/` | admin (JWT) | crea slot singolo; rifiuta se sovrapposto a uno esistente |

### `/bookings` (`backend/routers/booking.py`)
| Metodo | Path | Auth | Cosa fa |
|---|---|---|---|
| GET | `/bookings/` | admin | tutte le prenotazioni |
| POST | `/bookings/` | no (rate limit 5/min/IP), package opzionale richiede login studente | crea prenotazione: valida durata/slot, gestisce sessioni da 2h (unione di 2 slot da 1h, solo inizio 15:00/17:00), **identità del prenotante mai presa dal body a scatola chiusa** — studente loggato → sempre dal token; guest → `user_id` deve corrispondere a `email` nello stesso body, altrimenti 403 (vedi §7.7) —, redenzione pacchetto verificata contro l'utente **autenticato** (mai contro `user_id` nel body), claim atomico dello slot, prezzo server-side, evento Calendar, email+Discord |
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
| GET | `/admin/dashboard` | numeri chiave + prossimi slot liberi |
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
| GET/POST/DELETE | `/admin/disponibilita/regole` | regole ricorrenti |
| GET/POST/DELETE | `/admin/disponibilita/blocchi` | blocchi eccezionali |
| **GET/POST** | **`/admin/pacchetti`** | lista/crea pacchetti per un cliente (dal catalogo fisso) |
| **GET/PATCH** | **`/admin/recensioni`** | modera recensioni (approva/nasconde) |

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

## 5. Variabili d'ambiente richieste

Vedi `.env.example` (verificato allineato al codice il 2026-08-31) per l'elenco completo con commenti — qui solo le differenze rilevanti rispetto alla versione precedente di questo documento:

| Nome | Cambiato | Note |
|---|---|---|
| **`ADMIN_PASSWORD_HASH`** | sostituisce `ADMIN_PASSWORD` | hash bcrypt, mai la password in chiaro — genera con `scripts/hash_admin_password.py` |
| **`DRIVE_REFRESH_TOKEN`** | nuova | OAuth account reale del coach per il backup su Google Drive (non un service account — vedi sezione 6) |
| **`GOOGLE_DRIVE_BACKUP_FOLDER_ID`** | nuova | cartella Drive di destinazione dei backup |
| **`BACKUP_RETENTION_DAYS`** | nuova (default 30) | dopo quanti giorni un backup viene eliminato da Drive |
| **`RETENTION_MONTHS`** | nuova (default 24) | dopo quanti mesi di inattività un cliente viene anonimizzato |
| **`LOG_LEVEL`** | nuova (default INFO) | livello del logging strutturato (sostituisce i vecchi `print()`) |
| **`PUBLIC_BASE_URL`** | nuova | dominio usato per costruire il link assoluto di recensione nelle email |
| **`REVIEW_CHECK_INTERVAL_MINUTES`**, **`CALENDAR_SYNC_INTERVAL_MINUTES`**, **`GMAIL_HEALTHCHECK_INTERVAL_HOURS`** | nuove | intervalli dei job schedulati aggiunti dopo il 19/08 |

Tutte le altre variabili (`DATABASE_URL`, `GMAIL_*`, `EMAIL_*`, `DISCORD_*`, `JWT_*`, `GOOGLE_SERVICE_ACCOUNT_*`, `REMINDER_*`, `FRONTEND_ORIGINS`) sono invariate rispetto a prima.

---

## 6. Servizi esterni

- **Gmail API (OAuth2)** — email transazionali. Il progetto Google Cloud OAuth resta in stato "Testing" (non verificato): `GMAIL_REFRESH_TOKEN` scade dopo 7 giorni di inattività dell'app. Un job notturno (`controlla_credenziali_gmail`) verifica automaticamente e avvisa su Discord solo alla transizione ok→rotto. Rinnovo manuale: `python scripts/reauth_gmail.py`.
- **Google Calendar** — service account, scrittura (crea/elimina evento a ogni prenotazione/cancellazione) + lettura (sync automatico ogni ora via job, oltre al bottone admin manuale).
- **Google Drive (nuovo)** — backup automatico notturno del database (dump SQL scritto a mano via PyMySQL, non `mysqldump`) via OAuth2 con l'account reale del coach (**non** un service account — un service account non ha quota di storage propria su Drive, scoperto testando). Rinnovo: `python scripts/reauth_drive.py`.
- **Discord** — webhook in uscita (notifiche prenotazione/promemoria/alert di sistema) + OAuth2 in entrata (login studenti, ora con protezione CSRF via parametro `state`).
- **Railway** — hosting app + MySQL, build via Nixpacks. Piano Hobby: **nessun backup/PITR gestito dalla piattaforma** (da cui il backup homemade su Drive sopra). URL pubblico: `https://vgc-coaching-production.up.railway.app`.
- **GitHub Actions (nuovo)** — CI: `.github/workflows/tests.yml` esegue l'intera suite pytest su ogni push/PR (Python 3.11, nessun DB reale necessario — SQLite in-memory). Verde dal 2026-08-26.

---

## 7. Vincoli tecnici e comportamenti non ovvi

Tutti i punti della versione precedente di questo documento restano validi (fusi orari UTC naive, claim atomico via UPDATE condizionale, migrazioni automatiche non bloccanti, SMTP diretto bloccato su Railway, ecc.). Aggiunte rilevanti dopo il 19/08:

1. **Prenotazioni da 2 ore ora uniscono due slot da 1h** (`slot_id_secondario`), non un unico slot da 2h come generato in origine — il calendario genera solo slot da 1h; vedi §4.
2. **Token JWT studente in cookie httpOnly**, non più in `localStorage`/header `Authorization` — `secure` derivato da `DISCORD_OAUTH_REDIRECT_URI` (inizia con `https://`?), non da `request.url.scheme` (Railway strip-a HTTPS prima che l'app veda la richiesta). Non ancora verificato con un vero login Discord end-to-end in produzione, solo via mock + curl.
3. **Redenzione pacchetto**: la proprietà va sempre verificata contro l'utente **autenticato** dal token, mai contro un `user_id`/`package_id` dichiarato dal client — era il gap di sicurezza HIGH trovato e corretto nell'audit del 25/08 (permetteva furto di crediti pacchetto).
4. **Retention GDPR automatica**: un cliente inattivo da oltre `RETENTION_MONTHS` mesi (nessuna prenotazione/pacchetto recente) viene anonimizzato (non cancellato) da un job notturno — prenotazioni/pacchetti restano per analytics/storico, solo l'identità (nome/email/contatti Discord) viene rimossa.
5. **`AvailabilityRule.attiva` ora è davvero usato**: prima esisteva come colonna inerte, ora `genera_slot_giornaliero` (job notturno) filtra solo le regole attive.
6. **Backup pre-migrazione**: se all'avvio ci sono migrazioni Alembic in sospeso, l'app tenta un backup su Drive PRIMA di applicarle (fail-soft: un backup fallito o non configurato non blocca comunque la migrazione).
7. **Identità mai presa da un valore dichiarato dal client/provider esterno, senza verificarla**: sessione 31/08 (§12) — stessa classe di problema già chiusa una volta sul lato pacchetti (punto 3 sopra), riemersa altrove.
   - Creazione prenotazione (`POST /bookings/`): per lo studente loggato l'identità viene sempre dal token (`studente.id`), mai da `booking.user_id`. Per il guest checkout (nessun account, scelta di prodotto) non esiste un token da cui derivarla — `BookingCreate.email` deve corrispondere all'email dell'utente indicato da `user_id`, altrimenti 403.
   - Login Discord (`backend/routers/discord_auth.py`): un utente esistente viene collegato per email SOLO se Discord garantisce che è verificata (`discord_user["verified"]`) — altrimenti il login è rifiutato invece di agganciarsi a un account altrui.
8. **`/admin/analytics` a finestra fissa**: tutte e sei le metriche (non solo sessioni/incasso per mese, come prima) condividono la stessa finestra mobile di `MESI_FINESTRA_ANALYTICS` mesi (12, `backend/routers/admin/dashboard.py`), filtrata a livello query invece di scaricare l'intera storia delle prenotazioni in RAM.

---

## 8. Modifiche recenti (rispetto alla struttura del 19/08)

**Batch prodotto, commit `aa1e235` (2026-08-21)**: sessioni 1h/2h flessibili, cancellazione self-service, sistema recensioni con approvazione admin, pacchetti di sessioni, categoria cliente (junior/senior/master) al posto di showdown username, alert Discord automatici (token Gmail scaduto, migrazioni fallite), favicon, prima suite di test (19 test).

**Conformità GDPR (2026-08-25)**: rate limiting su `/admin/login`; password admin da plaintext a hash bcrypt (`ADMIN_PASSWORD_HASH`); informativa privacy pubblicata (`/privacy`); endpoint di cancellazione dati (`DELETE /admin/clienti/{id}`); retention automatica con anonimizzazione notturna.

**Audit di sicurezza (2026-08-25)**: 1 HIGH (furto credito pacchetto via IDOR, vedi §7.3) + 4 MEDIUM (info-disclosure su pacchetti attivi, profilo esposto da `POST /users/`, CSRF su Discord OAuth, HTML injection nelle email admin) — tutti corretti.

**Enterprise-hardening, 13 item (2026-08-25)**: rifiuto slot passati, `pool_pre_ping`, indici su colonne calde, fix N+1 nello scheduler, logging strutturato al posto di 38 `print()`, coverage test (64%→67%), test sui router prima scoperti, backup automatico su Drive, CI GitHub Actions, backup pre-migrazione, `/health` reale, cookie httpOnly, split di `admin.py` in package. Vedi dettagli completi nella cronologia del progetto (non ripetuti qui per brevità).

**Fix CI (2026-08-26)**: `pythonpath = .` in `pytest.ini`, `DATABASE_URL`/`JWT_SECRET` fittizie nel workflow — CI verde end-to-end.

---

## 9. Cosa funziona e cosa no, ad oggi (aggiornato 2026-08-31)

**Verificato**:
- Tutto quanto già verificato end-to-end in produzione al 19/08 (slot → prenotazione → email → Calendar → Discord → CSV, endpoint protetti → 401 senza token).
- **82 test automatizzati**, suite verde, eseguita di nuovo il 2026-08-31 (coverage 78%).
- **CI verde** su ogni push/PR (GitHub Actions).
- Backup su Google Drive verificato end-to-end con un dump reale.
- Login admin con la nuova password hashata, verificato live dopo il deploy.

**Non ancora verificato**:
- Le due correzioni di sicurezza Alta severità della sessione 31/08 (§7.7): verificate dalla suite automatica (test che riproducono l'abuso e lo dimostrano bloccato), non ancora con un vero tentativo contro l'ambiente di produzione.
- Login Discord studente end-to-end in produzione con il nuovo cookie httpOnly (solo mock + curl finora).
- Che il cron di backup notturno (04:00) abbia davvero prodotto un file da produzione (solo verificato in locale).
- Un uptime monitor esterno puntato su `/health` non risulta ancora configurato.
- Dominio personalizzato non acquistato — resta su `*.up.railway.app`, scelta consapevole.

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

### Backlog / follow-up manuali ancora aperti (nessuno bloccante, nessun codice da scrivere)
- Login Discord OAuth reale in produzione, per confermare il flusso cookie httpOnly end-to-end.
- Uptime monitor esterno (UptimeRobot/Better Uptime) su `/health`.
- Conferma che il backup notturno (04:00) produca davvero un file in produzione, non solo in locale.
- Dominio personalizzato — non fatto per scelta, da riconsiderare se serve un'immagine più professionale o SPF/DKIM/DMARC veri.

---

## 12. Sessione 2026-08-31 — review indipendente e chiusura findings

Su richiesta esplicita di una code review indipendente ("senior full-stack
engineer, impronta back-end"), prodotta come `ANALISI_2026-08-31.md`
(root del progetto — vedi quel file per l'analisi completa, area per
area, con voti e riferimenti `file:riga`). Di seguito solo la sintesi di
cosa è stato corretto in questa sessione, in ordine cronologico:

0. Messa in sicurezza del lavoro pregresso: 22 file modificati + 2 nuovi
   (`backend/services/pagination_service.py`, `tests/test_availability.py`)
   risultavano non committati da una sessione precedente — committati in
   blocco prima di qualunque fix. Ambiente locale allineato a
   produzione/CI: venv ricreato su Python 3.11 (era 3.14).
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
   test**, coverage 67% → **78%**.
4. **Igiene**: rimossa `SECRET_KEY` (var d'ambiente mai letta, documentata
   per errore in README), corretto un commento obsoleto in `admin.js`
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

### Backlog / follow-up manuali ancora aperti (nessuno bloccante, nessun codice da scrivere)
- Screen di consenso OAuth Google: portarlo da "Testing" a "In production"
  (Google Cloud Console) — elimina la scadenza a 7 giorni di inattività dei
  refresh token Gmail/Drive invece di limitarsi all'alert automatico.
- Confermare/eseguire la rotazione della password MySQL esposta in chiaro
  nella storia git (commit `15f536d`, mai confermata fatta —
  `ROADMAP.md` la segnava "todo").
- Verificare che le variabili d'ambiente reali su Railway riflettano
  `.env.example` aggiornato.
