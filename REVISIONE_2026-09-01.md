# REVISIONE DOCUMENTALE — 2026-09-01

## Come leggere questo file (per una sessione che non sa nulla della precedente)

**Cos'è.** Il referto di una revisione in **tre sessioni** il cui scopo è rendere i
documenti markdown del progetto un ritratto fedele del codice e coerenti tra loro.

**Regola non derogabile — gerarchia della verità:**
1. il **codice sorgente** e i file di configurazione (sempre l'ultima parola);
2. **`STATO_PROGETTO.md`** per le intenzioni e le scelte deliberate;
3. gli altri documenti.

Quando codice e documento divergono si aggiorna **il documento**. Non si modifica mai il
codice per farlo combaciare con un documento.

**Vincoli di progetto (invarianti, valgono in tutte e tre le sessioni):** monolite FastAPI,
frontend vanilla senza build step, nessun servizio a pagamento ricorrente, single-tenant,
pagamento fuori app, guest checkout come percorso normale.

**Struttura di questo file:**
- **Fase 1 — Fotografia del codice**: ricostruzione fatta leggendo SOLO il codice,
  senza aver aperto nessun markdown. È la base di confronto per tutto il resto.
- **Fase 1b — Ritrovamenti nel codice**: cose strane o incoerenti trovate nel codice,
  segnalate e **non corrette** (materiale per la sessione 2). Numerate `R1`–`R16`.
- **Fase 2 — Confronto documento per documento**: un verdetto sintetico per ciascuno dei
  5 markdown + `.env.example` + il workflow CI.
- **Fase 3 — Incroci tra documenti**: punti in cui due documenti *attuali* si smentiscono.
- **Fase 4 — Tabella unica dei rilievi**, ordinata per gravità. Voci numerate `D1`–`D27`,
  più le domande che solo l'umano può chiudere (`U1`–`U9`).
- **Fase 4b — Configurazione Railway**: esito di `U1`, con i ritrovamenti `P1`–`P9`
  (difetti dell'ambiente di produzione, distinti sia dai documenti `D*` sia dal codice `R*`)
  e il rilievo `G1` sullo stato di git. **`P1`–`P8` sono stati corretti il 2026-09-02**;
  il runbook seguito è `RAILWAY_RIALLINEAMENTO_2026-09-02.md`.
- *(da scrivere)* **Fase 5 — Correzioni approvate, da applicare** (registrate, NON applicate:
  la sessione 2 modificherà il codice e ne renderà obsoleta una parte).

**Stato di avanzamento al momento della scrittura:**
- [x] Fase 1 — fotografia del codice a freddo → **COMPLETATA**
- [x] Fase 2 — lettura dei markdown uno per volta → **COMPLETATA**
- [x] Fase 3 — incrocio tra documenti → **COMPLETATA**
- [x] Fase 4 — referto consolidato → **COMPLETATA**
- [x] Fase 5 — congelamento delle correzioni approvate → **COMPLETATA il 2026-09-02**:
      tutte e 29 le voci approvate voce per voce e registrate con testo attuale e testo nuovo
- [x] Fase 6 — sessione 2, debugging e pulizia del codice → **COMPLETATA il 2026-09-02**,
      5 commit (`1d2c850`, `886b10b`, `d3a0f32`, `a8bc99d`, `23544db`)
- [x] Fase 7 — sessione 3, riallineamento dei documenti → **COMPLETATA il 2026-09-02**

**La revisione in tre sessioni è conclusa.** Tutto il lavoro è stato **pushato il 2026-09-03**
(`61d4554..1e17319`, 8 commit) con **CI verde** (run `33690855235`): `G1` è chiuso, vedi
`STATO_PROGETTO.md` §13.4.

Cosa resta, e dove: la conferma che l'**auto-deploy di Railway** sia partito su `1e17319`
(fuori dal repository, solo l'umano può vederlo); il consolidamento delle variabili Railway
(`P9`); le domande ancora aperte `U2` (schermata OAuth ancora in "Testing", rimandata) e `U9`
(link nell'email di recensione, mai verificato); la rotazione della password MySQL (`U3`,
**rimandata deliberatamente**, non dimenticata); la decisione su `ANALISI_2026-08-31.md` in
coda alla Fase 5; e i ritrovamenti classificati **NON TOCCARE** nella Fase 6, che restano
debito noto e non sono spariti.

**Stato del repository al momento della fotografia:** branch `master`, working tree pulito,
ultimo commit `5c495cb` — *"docs: registra push+CI reali e correggi la cronologia 31/08 vs
01/09"* (2026-09-01). 121 file tracciati, nessun file untracked.

**In questa sessione non è stato modificato niente**, né codice né documenti: l'unico file
scritto è questo.

---

# FASE 1 — FOTOGRAFIA DEL CODICE

> Ricostruita leggendo esclusivamente il codice sorgente e i file di configurazione, prima
> di aprire qualunque markdown. I numeri qui sotto sono misurati, non riportati.

## 1.1 Albero reale dei file

Esclusi `venv/`, `.git/`, cache. Corrisponde ai 121 file tracciati da git.

```
|-- .github/
|   \-- workflows/
|       \-- tests.yml
|-- alembic/
|   |-- versions/
|   |   |-- 0bfc529cd9fd_aggiungi_discord_id_a_users.py
|   |   |-- 17c843945785_regole_ricorrenti_e_blocchi_eccezionali.py
|   |   |-- 1972ef07e768_crea_tabelle_iniziali.py
|   |   |-- 215aa000de4b_indici_su_slots_start_time_e_bookings_.py
|   |   |-- 2eac6f32b19b_aggiungi_anonimizzato_at_a_users.py
|   |   |-- 37a82dbead86_aggiungi_discord_tag_a_users.py
|   |   |-- 60a355bf4f97_aggiungi_reminder_sent_a_bookings.py
|   |   |-- 98489ff817ea_aggiungi_service_type_a_bookings.py
|   |   |-- a1b2c3d4e5f6_aggiungi_approvata_a_reviews.py
|   |   |-- a1c92f7e4b18_categoria_al_posto_di_showdown_users.py
|   |   |-- a4568987d2e7_aggiungi_calendar_event_id_a_bookings.py
|   |   |-- b3d84a19e6f2_crea_tabella_packages.py
|   |   |-- c5f612a8d9e3_crea_tabella_reviews.py
|   |   |-- cc755d0d6a6b_crea_tabella_client_notes.py
|   |   |-- d1af2a35c949_rimuovi_tabella_payments.py
|   |   |-- d4a72e0f8b31_aggiungi_slot_secondario_a_bookings.py
|   |   |-- dcfea9cf2bb0_aggiungi_vod_link_replay_code_a_bookings.py
|   |   \-- f56a5f50b503_aggiungi_blocked_external_a_slots.py
|   |-- env.py
|   |-- README
|   \-- script.py.mako
|-- backend/
|   |-- models/
|   |   |-- __init__.py
|   |   |-- availability_exception.py
|   |   |-- availability_rule.py
|   |   |-- booking.py
|   |   |-- client_note.py
|   |   |-- package.py
|   |   |-- review.py
|   |   |-- slots.py
|   |   \-- users.py
|   |-- routers/
|   |   |-- admin/
|   |   |   |-- __init__.py
|   |   |   |-- availability.py
|   |   |   |-- bookings.py
|   |   |   |-- clients.py
|   |   |   |-- dashboard.py
|   |   |   |-- packages.py
|   |   |   \-- reviews.py
|   |   |-- __init__.py
|   |   |-- booking.py
|   |   |-- consulenza.py
|   |   |-- discord_auth.py
|   |   |-- pacchetti_richieste.py
|   |   |-- slots.py
|   |   \-- users.py
|   |-- schemas/
|   |   |-- __init__.py
|   |   |-- availability.py
|   |   |-- booking.py
|   |   |-- client_note.py
|   |   |-- consulenza.py
|   |   |-- pacchetto_richiesta.py
|   |   |-- package.py
|   |   |-- review.py
|   |   |-- slots.py
|   |   \-- users.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- auth_service.py
|   |   |-- availability_service.py
|   |   |-- backup_service.py
|   |   |-- booking_service.py
|   |   |-- calendar_service.py
|   |   |-- discord_service.py
|   |   |-- email_service.py
|   |   |-- google_oauth_service.py
|   |   |-- package_service.py
|   |   |-- pagination_service.py
|   |   |-- retention_service.py
|   |   \-- timezone_service.py
|   |-- __init__.py
|   |-- database.py
|   |-- main.py
|   |-- rate_limit.py
|   \-- scheduler.py
|-- frontend/
|   |-- css/ (admin.css, style.css)
|   |-- fonts/ (Anton-Regular.woff2, Archivo-Variable.woff2)
|   |-- images/ (coach-avatar.png, coach-photo.jpg, favicon.png)
|   |-- js/ (about.js, admin.js, app.js, i18n.js, recensione.js)
|   |-- about.html
|   |-- admin.html
|   |-- favicon.ico
|   |-- index.html
|   |-- privacy.html
|   \-- recensione.html
|-- scripts/
|   |-- _env_utils.py
|   |-- hash_admin_password.py
|   |-- reauth_drive.py
|   \-- reauth_gmail.py
|-- tests/
|   |-- conftest.py
|   |-- test_admin.py
|   |-- test_availability.py
|   |-- test_backup_service.py
|   |-- test_booking.py
|   |-- test_discord_auth.py
|   |-- test_email_service.py
|   |-- test_health.py
|   |-- test_pagination_service.py
|   |-- test_retention.py
|   |-- test_reviews.py
|   |-- test_richieste.py
|   |-- test_scheduler.py
|   \-- test_slots.py
|-- .env.example
|-- .gitignore
|-- alembic.ini
|-- ANALISI_2026-08-31.md
|-- ANALYSIS.md
|-- nixpacks.toml
|-- pytest.ini
|-- README.md
|-- requirements-dev.txt
|-- requirements.txt
|-- ROADMAP.md
\-- STATO_PROGETTO.md
```

**Markdown presenti nella root (5):** `ANALISI_2026-08-31.md`, `ANALYSIS.md`, `README.md`,
`ROADMAP.md`, `STATO_PROGETTO.md`. Non esistono markdown in sottocartelle.

## 1.2 Endpoint reali

**Totale: 47 endpoint** dichiarati nel codice (5 a livello di `app` in `main.py`, 18 nei
router non-admin, 24 nel package `admin/`) + il mount statico `/static` + le tre rotte
generate automaticamente da FastAPI (`/docs`, `/redoc`, `/openapi.json`).

### Pagine HTML e infrastruttura (`backend/main.py`)

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| GET | `/health` | nessuna | Esegue `SELECT 1` sul DB e risponde `{"status":"ok"}`. Pensato per monitoraggio esterno. |
| GET | `/` | nessuna | Serve `frontend/index.html`. |
| GET | `/about` | nessuna | Serve `frontend/about.html`. |
| GET | `/privacy` | nessuna | Serve `frontend/privacy.html`. |
| GET | `/admin-panel` | **nessuna** | Serve `frontend/admin.html`. La pagina è pubblica; la protezione è sulle API che chiama. |
| — | `/static/*` | nessuna | `StaticFiles(directory="frontend")` — espone TUTTA la cartella `frontend/`. |
| GET | `/docs`, `/redoc`, `/openapi.json` | **nessuna** | Generate da FastAPI, non disattivate nel codice: l'intera superficie API è navigabile pubblicamente. |

### Slot (`backend/routers/slots.py`, prefix `/slots`)

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| GET | `/slots/` | nessuna | Slot con `is_available == True` **e** `start_time >= adesso` (UTC naive). Nessuna paginazione. |
| GET | `/slots/{slot_id}` | **nessuna** | Restituisce QUALSIASI slot per id, anche non disponibile o passato. |
| POST | `/slots/` | admin | Crea uno slot. Rifiuta se `slot_si_sovrappone`. `start_time` in input è interpretato come ora di Roma e convertito in UTC dal validator di `SlotCreate`. |

### Prenotazioni (`backend/routers/booking.py`, prefix `/bookings`)

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| GET | `/bookings/` | admin | `db.query(Booking).all()` — tutte le prenotazioni, **senza paginazione**. |
| POST | `/bookings/` | nessuna (cookie studente opzionale) — **rate 5/min** | Il cuore dell'app. Vedi sequenza sotto. |
| PATCH | `/bookings/{booking_id}/cancella` | studente (cookie) | Cancellazione self-service. Verifica proprietà, stato `confirmed`, slot futuro; poi `status="cancelled"` + `libera_slot_prenotazione`. |
| GET | `/bookings/recensioni/pubbliche` | nessuna | Solo `Review.approvata == True`, più recenti prima. Espone voto, commento, **solo il nome di battesimo** (`nome.split(" ")[0]`), data. |
| POST | `/bookings/{booking_id}/recensione` | token monouso — **rate 5/min** | Auth = `secrets.compare_digest(token, booking.review_token)`. Rifiuta se esiste già una recensione. Nasce con `approvata=False`. |

**Sequenza reale di `POST /bookings/`:**
1. slot esiste, altrimenti 404;
2. slot non passato (`start_time > adesso`), altrimenti 400;
3. coerenza durata: se `duration_hours != slot.duration_hours`, l'unico caso ammesso è
   2h richieste su slot da 1h → l'ora di inizio (in ora di Roma) deve essere in
   `ORE_INIZIO_VALIDE_2H = {15, 17}` e lo slot dell'ora successiva deve esistere ed essere
   libero; altrimenti 400;
4. identità: se c'è un cookie studente valido, l'utente è quello (il `user_id`/`email` nel
   body vengono ignorati); altrimenti guest checkout — si cerca `User.id == booking.user_id`
   e si richiede che `user.email == booking.email`, altrimenti 403;
5. pacchetto (opzionale): richiede **login studente** (401 altrimenti); il pacchetto deve
   appartenere a `studente.id`, avere sessioni residue e durata combaciante;
6. limite anti-abuso: massimo `MAX_PRENOTAZIONI_ATTIVE = 2` prenotazioni `confirmed` con
   slot futuro per utente;
7. claim atomico dello slot con `UPDATE ... WHERE is_available = True`, controllo
   `rowcount == 0` → 400; stesso claim ripetuto per lo slot secondario, con rollback di
   entrambi se il secondo fallisce;
8. prezzo: `0` se pacchetto, altrimenti `TABELLA_PREZZI[duration_hours]`;
9. crea l'evento Google Calendar (fallimento tollerato → `calendar_event_id = None`);
10. salva il `Booking` con `status="confirmed"` e `review_token = secrets.token_urlsafe(32)`;
    incrementa `package.sessioni_usate` se pacchetto;
11. **dopo** il commit invia: email conferma cliente, email notifica admin, notifica Discord.

### Utenti (`backend/routers/users.py`, prefix `/users`)

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| GET | `/users/` | admin | Tutti gli utenti. |
| GET | `/users/me` | studente (cookie) | Profilo dello studente loggato. |
| GET | `/users/me/prenotazioni` | studente (cookie) | Storico prenotazioni, più recenti prima. Nessun `response_model`; restituisce anche `start_time_iso` (ISO con offset UTC esplicito). Non espone `note_admin`. |
| POST | `/users/` | nessuna — **rate 5/min** | "Get or create" per email. `response_model=UserIdResponse`: restituisce **solo l'id**, mai il profilo. |
| GET | `/users/pacchetti-attivi` | studente (cookie) | Pacchetti con `sessioni_usate < sessioni_totali` dello studente loggato. |

Il cookie studente si chiama **`student_token`**, è `httponly`, `samesite="lax"`,
`secure` solo se `DISCORD_OAUTH_REDIRECT_URI` inizia con `https://`, `max_age = JWT_EXPIRE_MINUTES * 60`.

### Login Discord (`backend/routers/discord_auth.py`, prefix `/auth/discord`)

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| GET | `/auth/discord/login` | nessuna | Redirect a Discord con `scope="identify email"`, `prompt=consent` e uno `state` casuale salvato anche nel cookie `discord_oauth_state` (max_age 600s). |
| GET | `/auth/discord/callback` | nessuna | Verifica lo `state` con `compare_digest`; scambia il code per un access token; legge l'identità. Trova l'utente per `discord_id`, altrimenti per email — **ma il collegamento per email avviene solo se `discord_user["verified"]` è vero**, altrimenti il login viene rifiutato. Imposta il cookie `student_token` e reindirizza a `/`. |
| POST | `/auth/discord/logout` | nessuna | Cancella il cookie `student_token`. |

### Consulenza e richieste pacchetto

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| POST | `/consulenze/` | nessuna — **rate 5/min** | Call conoscitiva gratuita da 20 min. **Non** crea né Slot né Booking: `get_or_create_user` + email al cliente + email al coach + Discord. |
| POST | `/pacchetti-richieste/` | nessuna — **rate 5/min** | **Non** crea un `Package`: `get_or_create_user` + email al cliente + email al coach + Discord. Il pacchetto vero lo assegna l'admin. |

### Pannello admin (`backend/routers/admin/`, prefix `/admin`)

Autenticazione: `get_admin` → `OAuth2PasswordBearer(tokenUrl="/admin/login")`, quindi header
`Authorization: Bearer <JWT>` con claim `type == "admin"`. **Non** cookie.

| Metodo | Path | Auth | Cosa fa davvero |
|---|---|---|---|
| POST | `/admin/login` | nessuna — **rate 5/min** | Form `username`/`password`; confronto bcrypt contro `ADMIN_PASSWORD_HASH`. Restituisce `{access_token, token_type}`. |
| GET | `/admin/dashboard` | admin | Totale prenotazioni, prenotazioni di oggi (giorno solare di Roma), totale incassato (solo `confirmed`), media voto recensioni (**su tutte, anche non approvate**), 5 prossimi slot liberi. |
| GET | `/admin/analytics` | admin | Finestra mobile di `MESI_FINESTRA_ANALYTICS = 12` mesi. Sessioni/incasso per mese, servizi più richiesti, tasso di no-show (solo su sessioni concluse), clienti nuovi vs ricorrenti. |
| GET | `/admin/prenotazioni` | admin | Paginata (`pagina`, `per_pagina`), filtro opzionale `stato`. Include voto della recensione se presente. |
| PATCH | `/admin/prenotazioni/{id}/stato` | admin | `nuovo_stato` nel **body JSON** (`BookingStatoUpdate`, `Literal["confirmed","cancelled","no_show"]`). Se `cancelled` → `libera_slot_prenotazione`. |
| PATCH | `/admin/prenotazioni/{id}/note` | admin | `note` nel **body JSON** (`BookingNoteUpdate`). |
| GET | `/admin/export/csv` | admin | CSV di **tutte** le prenotazioni, 13 colonne, encoding `utf-8-sig`. |
| GET | `/admin/clienti` | admin | Paginata. Statistiche per cliente con `GROUP BY` limitato agli id della pagina. |
| DELETE | `/admin/clienti/{user_id}` | admin | Diritto all'oblio: libera gli slot delle prenotazioni `confirmed`, cancella recensioni, prenotazioni, note e pacchetti, poi l'utente. |
| GET | `/admin/clienti/{user_id}/note` | admin | Note tecniche, ordine cronologico crescente. |
| POST | `/admin/clienti/{user_id}/note` | admin | Aggiunge una nota (rifiuta stringhe di soli spazi). |
| GET | `/admin/slots` | admin | Paginata, ordinata per `start_time` crescente. Distingue `bloccato_da_calendario` / `bloccato_da_admin`. |
| POST | `/admin/slots/sync-calendario` | admin | Bottone manuale; stessa logica del job periodico. |
| DELETE | `/admin/slots/{slot_id}` | admin | Rifiuta se esistono prenotazioni collegate (anche come `slot_id_secondario`, anche cancellate). **Non** "disattiva" lo slot: solleva 400. |
| GET | `/admin/disponibilita/regole` | admin | Tutte le regole ricorrenti. |
| POST | `/admin/disponibilita/regole` | admin | Crea la regola e genera subito gli slot fino a fine mese. `durata_slot_ore` deve valere 1 (validator Pydantic). **Non imposta `attiva`**: usa il default `True` del model. |
| DELETE | `/admin/disponibilita/regole/{id}` | admin | Elimina la regola; non tocca gli slot già generati. |
| GET | `/admin/disponibilita/blocchi` | admin | Blocchi eccezionali, più recenti prima. |
| POST | `/admin/disponibilita/blocchi` | admin | Crea il blocco e marca `is_available=False, blocked_admin=True` sugli slot **liberi** nel periodo. |
| DELETE | `/admin/disponibilita/blocchi/{id}` | admin | Elimina il blocco; **non riapre** gli slot bloccati. |
| GET | `/admin/pacchetti` | admin | Tutti i pacchetti assegnati, più recenti prima. |
| POST | `/admin/pacchetti` | admin | Assegna un pacchetto del catalogo fisso. Il client sceglie solo `user_id` e `tipo`. |
| GET | `/admin/recensioni` | admin | Tutte, filtro opzionale `approvata=true/false`. Include nome ed email del cliente. |
| PATCH | `/admin/recensioni/{id}` | admin | Approva o ritira l'approvazione. |

**Endpoint con rate limit (6, tutti `5/minute` per IP):** `POST /users/`, `POST /bookings/`,
`POST /bookings/{id}/recensione`, `POST /admin/login`, `POST /consulenze/`,
`POST /pacchetti-richieste/`.

## 1.3 Modelli e schema DB reale

**8 tabelle applicative** + `alembic_version`. La tabella `payments`, creata dalla migrazione
iniziale, è stata **rimossa** da `d1af2a35c949`: non esiste più.

| Tabella | Model | Colonne |
|---|---|---|
| `users` | `User` | `id` (PK, idx), `nome` (100, NOT NULL), `email` (100, **unique**, NOT NULL), `telefono` (20), `categoria` (20), `discord_tag` (100), `discord_id` (30, **unique**), `created_at`, `anonimizzato_at` |
| `slots` | `Slot` | `id` (PK, idx), `start_time` (DateTime, NOT NULL, **idx**), `duration_hours` (default 1), `is_available` (default True), `blocked_external` (NOT NULL, default False), `blocked_admin` (NOT NULL, default False), `created_at` |
| `bookings` | `Booking` | `id` (PK, idx), `user_id` (FK users), `slot_id` (FK slots), `slot_id_secondario` (FK slots, nullable), `duration_hours`, `price_cents`, `service_type` (30), `status` (20, default `confirmed`, **idx**), `note_cliente` (Text), `note_admin` (Text), `vod_link` (500), `replay_code` (200), `calendar_event_id` (200), `reminder_sent` (NOT NULL, default False), `package_id` (FK packages, nullable), `review_token` (64, **unique**), `review_email_sent` (NOT NULL, default False), `created_at` |
| `client_notes` | `ClientNote` | `id`, `user_id` (FK users), `nota` (Text, NOT NULL), `created_at` |
| `availability_rules` | `AvailabilityRule` | `id`, `giorno_settimana` (Integer 0-6), `ora_inizio` (Time), `ora_fine` (Time), `durata_slot_ore` (default 1), `attiva` (NOT NULL, default True), `created_at` |
| `availability_exceptions` | `AvailabilityException` | `id`, `data_inizio` (Date, inclusiva), `data_fine` (Date, inclusiva), `motivo` (200), `created_at` |
| `packages` | `Package` | `id`, `user_id` (FK users), `tipo` (20), `sessioni_totali`, `sessioni_usate` (default 0), `durata_sessione_ore` (default 2), `prezzo_cents`, `created_at` |
| `reviews` | `Review` | `id`, `booking_id` (FK bookings, **unique**), `voto` (Integer 1-5), `commento` (Text), `approvata` (NOT NULL, default False), `created_at` |

**Convenzione datetime:** ogni `DateTime` nel database è **UTC naive**. La conversione
da/verso Europe/Rome avviene solo ai bordi (`backend/services/timezone_service.py`,
`SlotCreate`/`SlotResponse`).

**Relazioni:** `Booking.user` (backref `bookings`), `Booking.slot` (`foreign_keys=[slot_id]`,
backref `booking`), `Booking.slot_secondario` (`foreign_keys=[slot_id_secondario]`),
`Booking.package` (backref `packages`), `ClientNote.user` (backref `note_tecniche`),
`Review.booking` (backref `review`, `uselist=False`).

**Indici espliciti oltre alle PK:** `ix_slots_start_time`, `ix_bookings_status` (entrambi da
`215aa000de4b`); `email` e `discord_id` su users, `review_token` su bookings, `booking_id`
su reviews sono unique.

## 1.4 Catena delle migrazioni Alembic

**18 migrazioni**, catena lineare senza rami né merge. Head: **`2eac6f32b19b`**.

```
1972ef07e768  crea tabelle iniziali (slots, users, bookings, payments)   [base]
  -> a4568987d2e7  aggiungi calendar_event_id a bookings
  -> d1af2a35c949  rimuovi tabella payments
  -> 98489ff817ea  aggiungi service_type a bookings
  -> 37a82dbead86  aggiungi discord_tag a users
  -> f56a5f50b503  aggiungi blocked_external a slots
  -> dcfea9cf2bb0  aggiungi vod_link, replay_code a bookings
  -> 60a355bf4f97  aggiungi reminder_sent a bookings
  -> cc755d0d6a6b  crea tabella client_notes
  -> 17c843945785  regole ricorrenti, blocchi eccezionali, blocked_admin
  -> 0bfc529cd9fd  aggiungi discord_id a users (+ unique)
  -> a1c92f7e4b18  categoria al posto di showdown_username su users
  -> b3d84a19e6f2  crea tabella packages + package_id su bookings
  -> c5f612a8d9e3  crea tabella reviews + review_token/review_email_sent su bookings
  -> d4a72e0f8b31  aggiungi slot_id_secondario a bookings
  -> a1b2c3d4e5f6  aggiungi approvata a reviews
  -> 215aa000de4b  indici su slots.start_time e bookings.status
  -> 2eac6f32b19b  aggiungi anonimizzato_at a users                       [HEAD]
```

Le migrazioni sono applicate **automaticamente all'avvio dell'app** (`run_migrations()` in
`backend/main.py`, chiamata a livello di modulo, prima ancora che `app` esista). Se ci sono
migrazioni in sospeso (confronto tra revisione nel DB e head), viene prima tentato un backup
su Drive; un backup fallito non blocca la migrazione. Se la migrazione fallisce, l'app parte
comunque e manda un alert Discord.

## 1.5 Job dello scheduler

**8 job**, tutti registrati in `avvia_scheduler()` (`backend/scheduler.py`) su un
`BackgroundScheduler` di APScheduler, avviato da `backend/main.py`.

| id | Funzione | Trigger | Intervallo/orario | Variabile d'ambiente (default) |
|---|---|---|---|---|
| `controlla_promemoria` | `controlla_e_invia_promemoria` | interval | ogni 5 min | `REMINDER_CHECK_INTERVAL_MINUTES` (`5`) |
| `controlla_recensioni` | `controlla_e_invia_richieste_recensione` | interval | ogni 60 min | `REVIEW_CHECK_INTERVAL_MINUTES` (`60`) |
| `sincronizza_calendario` | `controlla_e_sincronizza_calendario` | interval | ogni 60 min | `CALENDAR_SYNC_INTERVAL_MINUTES` (`60`) |
| `genera_slot_giornaliero` | `genera_slot_giornaliero` | cron | ogni giorno **03:00** | **hardcoded** (`hour=3, minute=0`) |
| `controlla_credenziali_gmail` | `controlla_credenziali_gmail` | interval | ogni 24 ore | `GMAIL_HEALTHCHECK_INTERVAL_HOURS` (`24`) |
| `controlla_retention_clienti` | `controlla_e_anonimizza_clienti_inattivi` | cron | ogni giorno **03:01** | **hardcoded** |
| `pulisci_slot_obsoleti` | `pulisci_slot_obsoleti` | cron | ogni giorno **03:02** | **hardcoded** |
| `backup_database` | `controlla_e_esegui_backup_database` | cron | ogni giorno **04:00** | **hardcoded** |

Note di comportamento reale:
- **Promemoria**: `REMINDER_HOURS_BEFORE` (default `24`) decide la finestra; filtra
  `status=="confirmed"`, `reminder_sent==False`, `ora < start_time <= ora + soglia`. Manda
  email al cliente **e** messaggio Discord al coach, poi `reminder_sent = True` con commit
  dentro il ciclo.
- **Recensioni**: pre-filtro largo `start_time <= ora - 2h`, poi controllo esatto in Python
  su `start_time + duration_hours`. Link costruito come
  `{PUBLIC_BASE_URL}/static/recensione.html?booking_id=...&token=...`.
- **Generazione slot**: filtra `AvailabilityRule.attiva == True`. `genera_slot_da_regola`
  genera solo fino alla **fine del mese corrente**, è idempotente, e restituisce `0` se
  `durata_slot_ore != 1`.
- **Healthcheck Gmail**: mantiene lo stato in una globale `_ultimo_controllo_gmail_ok`;
  manda l'alert Discord solo sulle **transizioni** ok→rotto e rotto→ok.
- **Retention**: avvisa su Discord solo se ha anonimizzato almeno un cliente, riportando
  solo il conteggio.
- **Backup**: avvisa su Discord solo in caso di fallimento.
- I job cron usano il fuso orario locale del processo (APScheduler senza `timezone=`
  esplicito): su Railway è UTC, in locale è l'ora italiana.

## 1.6 Variabili d'ambiente realmente lette dal codice

**32 variabili distinte** lette con `os.getenv`. Nessun uso di `os.environ` diretto.
*(Correzione del 2026-09-02: la prima stesura di questa sezione diceva "26". Il conteggio era
sbagliato — la tabella qui sotto ne elenca 32 ed è sempre stata quella giusta. Il numero
corretto è **32**.)*

| Variabile | Letta in | Default | Obbligatoria? |
|---|---|---|---|
| `DATABASE_URL` | `backend/database.py:23`, `backend/main.py:132`, `alembic/env.py:115` | nessuno | **Sì** — `database.py` e `alembic/env.py` sollevano `RuntimeError` se manca; `main.py` invece salta le migrazioni con un warning |
| `LOG_LEVEL` | `backend/main.py:30` | `"INFO"` | no |
| `FRONTEND_ORIGINS` | `backend/main.py:188`, `backend/scheduler.py:40` (fallback) | `"http://127.0.0.1:8000,http://localhost:8000"` | no |
| `JWT_SECRET` | `backend/services/auth_service.py:31` | nessuno (`None`) | **di fatto sì** — senza, `jwt.encode` fallisce |
| `JWT_ALGORITHM` | `auth_service.py:32` | `"HS256"` | no |
| `JWT_EXPIRE_MINUTES` | `auth_service.py:33` | `480` | no |
| `ADMIN_USERNAME` | `auth_service.py:35` | nessuno | sì per il login admin |
| `ADMIN_PASSWORD_HASH` | `auth_service.py:40` | nessuno | sì per il login admin (hash bcrypt) |
| `DISCORD_CLIENT_ID` | `routers/discord_auth.py:29` | nessuno | sì per il login Discord |
| `DISCORD_CLIENT_SECRET` | `discord_auth.py:30` | nessuno | sì per il login Discord |
| `DISCORD_OAUTH_REDIRECT_URI` | `discord_auth.py:31` | nessuno | sì per il login Discord — **decide anche il flag `secure` dei cookie** |
| `DISCORD_WEBHOOK_URL` | `services/discord_service.py:15` | nessuno | no (se manca, ogni notifica logga un warning e viene saltata) |
| `GMAIL_CLIENT_ID` | `email_service.py:36`, `backup_service.py:63`, `scripts/reauth_*.py` | nessuno | sì per email e backup |
| `GMAIL_CLIENT_SECRET` | `email_service.py:37`, `backup_service.py:64`, `scripts/reauth_*.py` | nessuno | sì per email e backup |
| `GMAIL_REFRESH_TOKEN` | `email_service.py:38` | nessuno | sì per le email |
| `EMAIL_MITTENTE` | `email_service.py:39` | nessuno | sì per le email |
| `EMAIL_ADMIN` | `email_service.py:40` | nessuno | sì per le notifiche al coach |
| `COACH_DISCORD_TAG` | `email_service.py:41` | nessuno | no (finisce nel corpo delle email) |
| `COACH_TELEGRAM_CONTACT` | `email_service.py:42` | nessuno | no (idem) |
| `GOOGLE_CALENDAR_ID` | `calendar_service.py:27` | nessuno | sì per il calendario |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | `calendar_service.py:28` | nessuno | sì per il calendario |
| `GOOGLE_PRIVATE_KEY` | `calendar_service.py:34` | `""` (con `\n` letterali convertiti) | sì per il calendario |
| `DRIVE_REFRESH_TOKEN` | `backup_service.py:65` | nessuno | sì per il backup (senza, il backup viene saltato con un warning) |
| `GOOGLE_DRIVE_BACKUP_FOLDER_ID` | `backup_service.py:66` | nessuno | sì per il backup (idem) |
| `BACKUP_RETENTION_DAYS` | `backup_service.py:68` | `30` | no |
| `RETENTION_MONTHS` | `retention_service.py:26` | `24` | no |
| `REMINDER_HOURS_BEFORE` | `scheduler.py:29` | `24` | no |
| `REMINDER_CHECK_INTERVAL_MINUTES` | `scheduler.py:30` | `5` | no |
| `REVIEW_CHECK_INTERVAL_MINUTES` | `scheduler.py:32` | `60` | no |
| `PUBLIC_BASE_URL` | `scheduler.py:38` | prima origine di `FRONTEND_ORIGINS`, altrimenti `http://127.0.0.1:8000` | no |
| `CALENDAR_SYNC_INTERVAL_MINUTES` | `scheduler.py:43` | `60` | no |
| `GMAIL_HEALTHCHECK_INTERVAL_HOURS` | `scheduler.py:45` | `24` | no |

Le 32 righe sono le variabili **distinte**; alcune (`DATABASE_URL`, `FRONTEND_ORIGINS`,
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`) sono lette da più file. Gli script in `scripts/`
non ne aggiungono nessuna: leggono solo `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`, già contate.

**Variabile presente in `.env.example` ma MAI letta dal codice:** `SECRET_KEY`.
**Variabile letta dal codice ma assente da `.env.example`:** `LOG_LEVEL`.

## 1.7 Servizi esterni realmente chiamati

| Servizio | Dove | Autenticazione | Cosa fa |
|---|---|---|---|
| **Gmail API** (`gmail.v1`) | `services/email_service.py` | OAuth2 utente, `GMAIL_REFRESH_TOKEN`, scope `gmail.send` | Invia 8 tipi di email: conferma prenotazione, promemoria, notifica admin prenotazione, conferma richiesta consulenza, notifica admin consulenza, conferma richiesta pacchetto, notifica admin pacchetto, richiesta recensione. Più `users.getProfile` come healthcheck (non manda nulla). |
| **Google Calendar API** (`calendar.v3`) | `services/calendar_service.py` | **service account** (`GOOGLE_SERVICE_ACCOUNT_EMAIL` + `GOOGLE_PRIVATE_KEY`), scope `calendar` | Crea evento, elimina evento, legge eventi in un intervallo per bloccare gli slot sovrapposti. |
| **Google Drive API** (`drive.v3`) | `services/backup_service.py` | OAuth2 utente, `DRIVE_REFRESH_TOKEN`, scope `drive.file` — **deliberatamente NON il service account** | Carica il dump SQL, elenca ed elimina i backup più vecchi di `BACKUP_RETENTION_DAYS`. |
| **Discord webhook** | `services/discord_service.py` | URL segreto (`DISCORD_WEBHOOK_URL`), timeout 5s | 5 tipi di messaggio: nuova prenotazione, promemoria sessione, richiesta consulenza, richiesta pacchetto, alert di sistema. |
| **Discord OAuth2** | `routers/discord_auth.py` | client id/secret, timeout 10s | `oauth2/authorize`, `oauth2/token`, `users/@me`. |
| **MySQL** | `backend/database.py` | `DATABASE_URL` | `create_engine(..., pool_pre_ping=True)`. |

Ogni chiamata a Gmail/Calendar/Drive/Discord è avvolta in `try/except`: un fallimento
esterno non fa mai fallire una prenotazione. Le credenziali OAuth sono in cache in memoria
per `refresh_token` (`services/google_oauth_service.py`), riusate finché `.valid`.

**Nessun servizio a pagamento ricorrente**: nessun Stripe, nessun SendGrid, nessuna coda
esterna, nessun Redis (il rate limiter di slowapi è in memoria).

## 1.8 Test e coverage reali

Suite eseguita realmente in questa sessione con `venv/Scripts/python.exe -m pytest`
(Python 3.11.9), con `DATABASE_URL="sqlite:///:memory:"` e `JWT_SECRET="test-secret"`:

```
82 passed, 23 warnings in 5.14s
TOTAL   1714 stmts   351 miss   80% cover
```

**82 test**, distribuiti su 13 file:

| File | Test |
|---|---|
| `tests/test_booking.py` | 19 |
| `tests/test_admin.py` | 10 |
| `tests/test_availability.py` | 8 |
| `tests/test_pagination_service.py` | 7 |
| `tests/test_reviews.py` | 6 |
| `tests/test_discord_auth.py` | 5 |
| `tests/test_richieste.py` | 5 |
| `tests/test_scheduler.py` | 5 |
| `tests/test_slots.py` | 5 |
| `tests/test_email_service.py` | 4 |
| `tests/test_retention.py` | 4 |
| `tests/test_backup_service.py` | 3 |
| `tests/test_health.py` | 1 |

**Coverage reale: 80%** (`--cov=backend`, attivo di default via `addopts` in `pytest.ini`).
I file meno coperti:

| File | Coverage |
|---|---|
| `services/calendar_service.py` | 24% |
| `services/google_oauth_service.py` | 36% |
| `services/email_service.py` | 50% |
| `services/backup_service.py` | 58% |
| `routers/admin/availability.py` | 55% |
| `services/discord_service.py` | 62% |
| `scheduler.py` | 69% |
| `database.py` | 71% |
| `routers/admin/clients.py` | 74% |
| `routers/admin/bookings.py` | 75% |

A 100%: tutti i model, tutti gli schemi tranne `availability.py` (98%), `rate_limit.py`,
`routers/slots.py`, `routers/consulenza.py`, `routers/pacchetti_richieste.py`,
`package_service.py`, `pagination_service.py`, `retention_service.py`, `timezone_service.py`.

**Ambiente dei test:** SQLite in-memory con `StaticPool`, `app.dependency_overrides[get_db]`,
`limiter.enabled = False`, e monkeypatch delle integrazioni esterne su `booking`,
`consulenza` e `pacchetti_richieste`. Fixture `db_pulito` (autouse) ricrea/elimina le tabelle
con `Base.metadata.create_all`/`drop_all` prima e dopo ogni test.

**CI** (`.github/workflows/tests.yml`): su ogni `push` e ogni `pull_request`,
`ubuntu-latest`, Python **3.11** (stessa versione dichiarata in `nixpacks.toml`),
`pip install -r requirements-dev.txt`, `pytest` con `DATABASE_URL="sqlite:///:memory:"` e
`JWT_SECRET="test-secret-non-usato-in-produzione"`. Nessun job di deploy: il deploy è
l'auto-deploy di Railway, fuori da GitHub Actions.

## 1.9 Costanti di business

**Prezzi sessione singola** — `TABELLA_PREZZI` in `backend/routers/booking.py:39`:

| Durata | Prezzo |
|---|---|
| 1 ora | 2000 cent = **€20** |
| 2 ore | 4000 cent = **€40** |

Lineare a €20/h. Il frontend (`frontend/index.html:191-195`) mostra esattamente "1 hour — €20"
e "2 hours — €40", con **2 ore come default selezionato**.

**Catalogo pacchetti** — `CATALOGO_PACCHETTI` in `backend/services/package_service.py`:

| Chiave | Nome | Sessioni | Durata | Prezzo scontato | Prezzo pieno |
|---|---|---|---|---|---|
| `intro` | Competitive Intro | 2 | 2 ore | 7000 cent = **€70** | 8000 cent = €80 |
| `team` | Team Building Session | 4 | 2 ore | 13000 cent = **€130** | 16000 cent = €160 |
| `tour` | Tournament Prep | 6 | 2 ore | 19000 cent = **€190** | 24000 cent = €240 |

Il frontend (`index.html:361, 373, 385`) riporta gli stessi valori: `€80 → €70`,
`€160 → €130`, `€240 → €190`. **Coerente.**

**Tipi di servizio (4)** — `ServiceType` in `backend/schemas/booking.py`, etichette in
`discord_service.SERVICE_LABELS`: `vod_review` (VOD Review), `team_building`
(Team Building), `bo3_sparring` (Bo3 Sparring), `tournament_prep` (Tournament Prep).

**Categorie cliente (3)** — `Categoria` in `backend/schemas/users.py`:
`junior`, `senior`, `master`.

**Stati prenotazione (3)**: `confirmed` (default), `cancelled`, `no_show`.

**Altre costanti:**

| Costante | Valore | Dove |
|---|---|---|
| `MAX_PRENOTAZIONI_ATTIVE` | `2` | `routers/booking.py:29` |
| `ORE_INIZIO_VALIDE_2H` | `{15, 17}` (ora di Roma) | `routers/booking.py:48` |
| `ORE_INIZIO_VALIDE_2H` (frontend) | `[15, 17]` | `frontend/js/app.js:435` — **allineato** |
| Rate limit | `5/minute` per IP, su 6 endpoint | `rate_limit.py` + decoratori |
| `MESI_FINESTRA_ANALYTICS` | `12` mesi mobili | `routers/admin/dashboard.py:85` |
| Paginazione admin | default `20`, massimo `100`, minimo `1`, pagina minima `1` | `services/pagination_service.py` |
| `RETENTION_MONTHS` | `24` mesi (soglia calcolata come `30 * mesi` giorni) | `services/retention_service.py:26` |
| `BACKUP_RETENTION_DAYS` | `30` giorni | `services/backup_service.py:68` |
| `RIGHE_PER_INSERT` (dump) | `500` | `services/backup_service.py:73` |
| Margine ricerca sovrapposizioni | `6` ore | `services/availability_service.py:39` |
| Finestra generazione slot | fino alla **fine del mese corrente** | `services/availability_service.py` |
| Durata slot generabile | **solo 1 ora** (doppia barriera: validator + `return 0`) | `schemas/availability.py` + `availability_service.py:92` |
| Voto recensione | intero `1`–`5` | `schemas/review.py` |
| `JWT_EXPIRE_MINUTES` | `480` (8 ore), stesso valore per admin e studente | `auth_service.py:33` |
| `max_age` cookie state OAuth | `600` secondi | `discord_auth.py:103` |
| Reminder email calendario Google | email 60 min prima, popup 30 min prima | `calendar_service.py:120-121` |
| Timeout HTTP | Discord `5s`, Discord OAuth `10s` | `discord_service.py`, `discord_auth.py` |

**Orario di ricevimento implicito**: il commento in `routers/booking.py:41-47` documenta
"15:00-19:00, 4 slot da 1h (15, 16, 17, 18)" come ragione dietro `ORE_INIZIO_VALIDE_2H`. Non è
una costante nel codice: gli orari reali dipendono dalle `AvailabilityRule` create a runtime.

---

# FASE 1b — RITROVAMENTI NEL CODICE (segnalati, NON corretti)

> Materiale per la sessione 2. Nessuno di questi è stato toccato.

### R1 — Eseguire `pytest` in locale tocca il database reale e manda un vero messaggio Discord
**Gravità: alta.** `run_migrations()` è chiamata a livello di modulo in `backend/main.py:165`,
quindi si esegue al semplice `import backend.main` — cioè quando `tests/conftest.py` importa
l'app, **prima di qualunque fixture**. Con un `.env` popolato (presente in locale, contiene
`DATABASE_URL` MySQL reale, `DISCORD_WEBHOOK_URL` reale e `DRIVE_REFRESH_TOKEN` reale),
lanciare `pytest` senza override:
- applica le migrazioni al **database di sviluppo vero**;
- tenta un **backup reale su Google Drive** se ci sono migrazioni in sospeso;
- se qualcosa fallisce, **manda un alert Discord vero** al canale del coach
  (`invia_alert_sistema` non è tra le funzioni sostituite da `conftest.py`).

Verificato sperimentalmente forzando `DATABASE_URL="sqlite:///:memory:"`: in quella
configurazione `run_migrations()` fallisce sempre (il dump usa `SHOW TABLES`, sintassi MySQL,
e le migrazioni usano DDL MySQL) e finisce nel ramo `except` che chiama `invia_alert_sistema`.
In CI è innocuo (`DISCORD_WEBHOOK_URL` non è impostata), ma **il ramo di errore delle
migrazioni viene esercitato ad ogni singolo run della suite**, in locale e in CI.

### R2 — `/docs`, `/redoc` e `/openapi.json` sono pubblici
`FastAPI(title=..., version="1.0")` senza `docs_url=None`: l'intero schema dell'API,
endpoint admin compresi, è navigabile da chiunque conosca l'URL. Non è una vulnerabilità di
per sé (gli endpoint restano protetti), ma è una scelta mai dichiarata esplicitamente.

### R3 — Commento obsoleto su `AvailabilityRule.attiva`
`backend/models/availability_rule.py` dice: *"oggi nel codice non viene ancora usata per
filtrare nulla, resta pronta per un eventuale sviluppo futuro"*. **Falso**:
`genera_slot_giornaliero` in `backend/scheduler.py:244` filtra proprio
`AvailabilityRule.attiva == True`. Il docstring di quel job lo dice esplicitamente
("prima volta che questo campo viene davvero usato per filtrare, vedi il commento nel
model") — cioè i due commenti si contraddicono a vicenda. Nota collegata: nessun endpoint
permette di **cambiare** `attiva`: una regola nasce sempre attiva e non può essere sospesa.

### R4 — Riferimento a un endpoint inesistente in un commento
`backend/routers/admin/packages.py:23` rimanda a *"GET `/pacchetti/attivi` in
backend/routers/users.py"*. Il path reale è **`GET /users/pacchetti-attivi`**.

### R5 — Commento obsoleto sul refresh del token Gmail
`backend/services/email_service.py:105-113` afferma che `Credentials.refresh()` *"va rifatta
ad ogni invio invece di essere salvata"*. Non è più vero da quando esiste
`services/google_oauth_service.py`, che tiene le credenziali in cache per `refresh_token` e
le rinnova solo quando `.valid` è falso — cosa che il commento in quel file spiega
correttamente.

### R6 — `SECRET_KEY` ancora in `.env.example`, `LOG_LEVEL` assente
`SECRET_KEY` non è letta da nessuna riga del codice (verificato: nessun `os.getenv("SECRET_KEY")`),
ma è in `.env.example:5` con la nota *"non più usata direttamente, ma tenuta per compatibilità"*.
Il commit `efbe886` l'ha rimossa dalla tabella del README ma non dal `.env.example`.
Viceversa `LOG_LEVEL`, letta in `backend/main.py:30`, non compare in `.env.example`.

### R7 — Il docstring di `DELETE /admin/slots/{id}` promette qualcosa che non fa
`backend/routers/admin/availability.py:86-89` dice: *"Se ha prenotazioni collegate (anche
cancellate) non può essere eliminato fisicamente per preservare lo storico — **viene invece
disattivato**"*. Il codice **non disattiva niente**: solleva un `HTTPException` 400 e lo slot
resta esattamente com'era.

### R8 — `media_voto_recensioni` in dashboard include le recensioni non approvate
`routers/admin/dashboard.py:66`: `db.query(func.avg(Review.voto)).scalar()`, senza filtro su
`approvata`. Comportamento probabilmente voluto (è un numero interno per il coach), ma non
dichiarato da nessuna parte: la vetrina pubblica usa invece solo le approvate.

### R9 — La retention non anonimizza `categoria`
`services/retention_service.py` azzera `nome`, `email`, `telefono`, `discord_tag`,
`discord_id`, ma lascia `categoria` (junior/senior/master). Non è un identificativo diretto,
quindi probabilmente è deliberato — ma la privacy policy va confrontata con questo dettaglio
in Fase 2.

### R10 — `slot_si_sovrappone(escludi_id=...)` è un parametro mai usato
`services/availability_service.py:18`. Il commento lo dichiara esplicitamente ("nel codice
attuale questo parametro non viene mai passato"), quindi è un ritrovamento neutro, non un
errore.

### R11 — `GET /bookings/` e `GET /admin/export/csv` non sono paginati
Mentre le tre liste admin (prenotazioni, clienti, slot) sono paginate, `GET /bookings/`
scarica tutte le prenotazioni di sempre e l'export CSV pure. Per l'export è ovviamente
voluto; per `GET /bookings/` non è chiaro se abbia ancora un consumatore (il frontend admin
usa `/admin/prenotazioni`, non `/bookings/`).

### R12 — `GET /slots/{slot_id}` è pubblico e non filtra nulla
A differenza di `GET /slots/`, restituisce qualunque slot per id, anche già prenotato,
bloccato o passato. Espone poco (id, orario, durata, disponibilità), ma è un'asimmetria
non documentata rispetto alla lista.

### R13 — I job cron dipendono dal fuso orario del processo
`BackgroundScheduler()` è costruito senza `timezone=`: le "03:00" e le "04:00" dei quattro
job cron sono ore **locali del processo**. Su Railway (UTC) significa 04:00/05:00 ora
italiana in estate, 04:00/05:00 in inverno; in locale sono davvero le 03:00 italiane. Il
commento parla di *"ogni notte alle 03:00, un momento a basso traffico"* senza chiarire in
quale fuso.

### R14 — `guest checkout`: `email` è formalmente opzionale nello schema ma di fatto obbligatoria
`BookingCreate.email` è `Optional[str] = None`. Per un guest, `user.email != booking.email`
con `booking.email is None` è sempre vero → 403. Quindi l'email è obbligatoria per il guest
checkout ma lo schema non lo dice, e chi legge `/docs` vede un campo opzionale.

### R15 — `.env` locale contiene `EMAIL_APP_PASSWORD`, residuo dell'era SMTP
Non è letta da nessuna riga del codice (l'invio è passato all'API Gmail con
`GMAIL_REFRESH_TOKEN`). Non è in `.env.example`. È solo rumore nel `.env` locale, ma
conferma che il `.env` reale e `.env.example` sono andati alla deriva l'uno dall'altro.

### R16 — Duplicazione minima negli script `scripts/`
`hash_admin_password.py`, `reauth_gmail.py` e `reauth_drive.py` importano tutti
`aggiorna_env_locale` da `_env_utils`, ma ciascuno ridefinisce poi una propria funzione
locale con lo stesso nome che la incapsula. Funziona, ma il nome collide con quello importato
(salvato come `aggiorna_env_locale_helper`) e rende meno ovvio quale delle due si stia
chiamando.

---

---

# FASE 2 — CONFRONTO DOCUMENTO PER DOCUMENTO

> Letti uno alla volta, ciascuno confrontato con la fotografia prima di aprire il successivo.
> Ordine: `STATO_PROGETTO.md` → `README.md` → `ANALISI_2026-08-31.md` → `ANALYSIS.md` →
> `ROADMAP.md` → `.env.example` → `.github/workflows/tests.yml`. Non esistono altri markdown:
> i 5 in root sono tutti, più `alembic/README` (una riga di testo standard di Alembic,
> "Generic single-database configuration", nessun contenuto di progetto).

## 2.1 `STATO_PROGETTO.md` — il documento più affidabile del progetto

**Verdetto complessivo: sostanzialmente fedele.** È l'unico documento che descrive il codice
di oggi, e nella maggior parte dei punti controllati lo descrive **bene**. In particolare è
corretto — e più preciso del codice stesso — su tre punti dove il codice si auto-contraddice:

- §2 riga 180 e §7.5: `AvailabilityRule.attiva` "ora usata davvero" da `genera_slot_giornaliero`.
  **Il documento ha ragione, il commento nel model ha torto** (vedi `R3`).
- §3: `DELETE /admin/slots/{id}` "elimina slot (rifiuta se ha prenotazioni collegate)".
  **Il documento ha ragione, il docstring del codice ha torto** (vedi `R7`).
- §7.2: il flag `secure` dei cookie derivato da `DISCORD_OAUTH_REDIRECT_URI`. Esatto.

Altri punti verificati corretti: 8 job scheduler con l'elenco giusto; 18 migrazioni; head
`2eac6f32b19b`; 82 test; prezzi 20€/h e catalogo pacchetti; `MAX_PRENOTAZIONI_ATTIVE=2`;
`ORE_INIZIO_VALIDE_2H`; rate limit su 6 endpoint con l'elenco esatto; `MESI_FINESTRA_ANALYTICS`
= 12 e "tutte e sei le metriche" (le chiavi restituite da `/admin/analytics` sono davvero 6);
tutte le colonne di tutte le 8 tabelle; venv su Python 3.11 (verificato: 3.11.9).

**Difetti trovati:** `D4` (commit e data di riferimento nell'intestazione), `D5`
(`.env.example` dichiarato allineato), `D6` (coverage 78% vs 80%), `D14` ("9 tabelle attive"
seguito da un elenco di 8), `D19` ("le prime 12 migrazioni" — sono 11 — rimandate a una
"versione precedente di questo documento" non consultabile), `D20` (§7 delega alla stessa
versione precedente inesistente), `D21` (§12.4 "rimossa `SECRET_KEY`" senza dire "solo dal
README"), `D23` (`/docs` pubblici non menzionati), `D24` (fuso dei job cron), `D25`
(`media_voto_recensioni` include le recensioni non approvate).

## 2.2 `README.md` — la guida di setup, ferma a prima di agosto in più punti

**Verdetto complessivo: è il documento più disallineato tra quelli che descrivono il presente.**
Ha una sezione impeccabile — la tabella delle variabili d'ambiente, che è **più corretta di
`.env.example`** (ha già perso `SECRET_KEY`, ha tutte le altre 25) — e una parte "struttura
del progetto" che descrive uno stato del codice superato in almeno otto punti.

Cosa è corretto: tutto il setup locale, i comandi, le sezioni Gmail/Calendar/Drive/Discord
(dettagliate e accurate, incluso il perché del non-service-account per Drive), il deploy, la
sezione Sicurezza, la sezione GDPR, l'architettura monolite.

**Difetti trovati:** `D1` (l'affermazione su `pytest`, il rilievo più costoso di tutta la
revisione), `D8` (`timezone_service` "un'unica funzione"), `D9` (lo scheduler descritto come
"dei promemoria"), `D10` (`backend/routers/admin.py`, file inesistente), `D11` (`GET /slots/`
senza il filtro sugli orari passati), `D12` (healthcheck attribuito anche al token Drive),
`D16` (inventari di model/schemi/service/router incompleti), `D17` ("due pagine web", sono 5),
`D18` ("tre notifiche in parallelo", sono sequenziali), `D22` ("Python 3.11+"), `D26`
(`DISCORD_OAUTH_REDIRECT_URI` marcata facoltativa senza dire che decide il flag `secure`).

## 2.3 `ANALISI_2026-08-31.md` — storico *di fatto*, ma non dichiarato tale

Questo documento **non era nell'elenco dei "storici di proposito"** delle istruzioni, ma
leggendolo risulta esserlo a tutti gli effetti: è il verbale di una code review eseguita in
una data precisa. Il suo contenuto **non va allineato al codice** — riscriverlo distruggerebbe
il verbale di cosa quella review trovò davvero, esattamente come per `ANALYSIS.md`/`ROADMAP.md`.

Ho verificato che **praticamente ogni criticità che elenca è già chiusa**: IDOR su
`booking.user_id` (`e567d11`), account linking Discord senza `verified` (`d30a3de`),
`note_admin` in cancellazione (`97b56ec`), analytics non filtrata (`4e711e8`+`e32c032`),
slot-card non accessibili (`bee9345`), note admin in query string (`0ee7182`), N+1 in
`elimina_cliente` (`2114b73`), `frontend/Architettura.txt` (`fd0b78e`), venv su 3.14,
modifiche non committate, `SECRET_KEY` nel README (`efbe886`).

**Il difetto non è il contenuto: è che il file non dice da nessuna parte che quei findings
sono stati chiusi.** Ha la data in testa (riga 2), il che è già meglio degli altri due storici,
ma un lettore che lo apre oggi senza aver prima letto `STATO_PROGETTO.md` §12 conclude che
l'applicazione ha **in questo momento due vulnerabilità Alta severità sfruttabili senza
credenziali**. → `D3`.

Nota utile per la Fase 5: ANALISI segnalava `SECRET_KEY` citando **solo** `README.md:217` e
non `.env.example` — ed è esattamente per questo che il fix `efbe886` è stato parziale. Il
disallineamento residuo `D5`/`D21` ha qui la sua causa.

## 2.4 `ANALYSIS.md` — storico di proposito, ma indistinguibile dall'attuale

Contenuto **da non allineare**, per costruzione. L'unica domanda pertinente è: un lettore può
scambiarlo per attuale?

**Sì, facilmente.** L'intestazione (righe 1-3) dice solo *"Documento generato da una sessione
di analisi... Autosufficiente: non presuppone di aver letto la conversazione originale"*.
**Non dice che è storico e non porta una data in testa**: l'unica data in tutto il file è fra
parentesi in un titolo di sezione a metà documento (`## 5. Decisioni prese con l'utente
(2026-08-06)`). Tutto il resto è scritto al presente indicativo.

Un lettore che apre solo questo file conclude che oggi: `GET /users/` è pubblico e perde i
dati personali di tutti i clienti; `GET /bookings/` e `POST /slots/` sono pubblici; il CORS è
`allow_origins=["*"]`; `database.py` contiene credenziali MySQL in chiaro; la password admin
è confrontata con `==`; le email passano da SendGrid; il Calendar è solo in scrittura; non
esiste nessuno scheduler; nessuna lista è paginata; i prezzi sono 35/60/80€; esistono
`payment.py`, `procfile` e uno stato `pending`; la migrazione `a4568987d2e7` è vuota.
**Nessuna di queste cose è vera oggi** — verificate tutte contro la fotografia. → `D2`.

## 2.5 `ROADMAP.md` — storico di proposito, e senza nessuna data

Stesso trattamento: contenuto **da non allineare**. Ma qui la dichiarazione manca in modo
ancora più netto di `ANALYSIS.md`.

**Non c'è nessuna data in tutto il file**, né in testa né dentro. E l'intestazione (riga 3)
lo presenta esplicitamente come un piano *vivo*: *"Stato aggiornabile a `in corso` / `fatto`
man mano che si procede"*. Un lettore lo prende per la roadmap corrente del progetto.

Nel merito è quasi tutto marcato "fatto" — e l'unico `todo` rimasto (P0-1, rotazione della
password MySQL) **è davvero ancora aperto**, coerente con `STATO_PROGETTO.md` §12: è l'unico
segnale vivo del file, ed è accurato. Le descrizioni interne sono invece superate (generazione
slot "8 settimane in avanti" contro l'attuale "fine del mese corrente"; analytics "ultimi 6
mesi" contro 12; servizio `mentality_prep` contro l'attuale `tournament_prep`; `admin.py`
come file unico) — **non vanno toccate**, sono il verbale di cosa fu deciso allora. → `D2`.

## 2.6 `.env.example` — documentazione a tutti gli effetti, e disallineata

Due difetti concreti, entrambi verificati contro il codice:
- riga 5: `SECRET_KEY`, con la nota *"non più usata direttamente, ma tenuta per compatibilità"*.
  **Nessuna riga del progetto la legge** (`grep 'getenv("SECRET_KEY")'` → zero risultati). Non
  c'è nessuna "compatibilità" da mantenere: non è letta né da `backend/`, né da `alembic/`, né
  da `scripts/`.
- `LOG_LEVEL` **manca**, pur essendo letta in `backend/main.py:30` ed essendo documentata sia
  nel README (no: assente anche lì, vedi `D7`) sia in `STATO_PROGETTO.md` §5.

Tutte le altre 25 variabili lette dal codice sono presenti e commentate correttamente, con
spiegazioni sostanziose (il perché di OAuth invece del service account per Drive, la scadenza
del refresh token, ecc.). → `D5`, `D7`.

## 2.7 `.github/workflows/tests.yml` — commenti descrittivi

**Verdetto: fedele.** I commenti sono accurati su tutto quello che affermano: Python 3.11
allineata a `nixpacks.toml` (vero), `requirements-dev.txt` (vero), `DATABASE_URL`/`JWT_SECRET`
fittizie con la spiegazione del perché (vera).

Un solo silenzio, ed è lo stesso di `D1`: il commento dice *"backend/database.py richiede
DATABASE_URL solo per costruire l'Engine all'import (create_engine non apre una connessione
reale finché nessuno la usa) — i test però sovrascrivono get_db con un SQLite in-memory
separato, quindi basta un valore fittizio, mai usato per davvero"*. **"Mai usato per davvero"
non è esatto**: `run_migrations()` in `backend/main.py:165` usa quella `DATABASE_URL` sul
serio, all'import, e ci tenta sopra un `alembic upgrade head` (che fallisce, perché il DDL è
MySQL su un SQLite). In CI l'effetto è innocuo; il punto è che la stessa frase, applicata a
un `.env` locale popolato, diventa falsa e pericolosa. → confluisce in `D1`.

---

# FASE 3 — INCROCI TRA DOCUMENTI

> Solo punti in cui due documenti **attuali** dicono cose diverse sulla stessa realtà di oggi.
> Le divergenze tra `ANALYSIS.md`/`ROADMAP.md`/`ANALISI_2026-08-31.md` e il presente **non**
> sono contate qui: sono legittime, quei documenti parlano di un'altra epoca.

| Tema | Documento A | Documento B | Chi ha ragione |
|---|---|---|---|
| `timezone_service.py` | `README.md:100` — "un'unica funzione (`utc_to_rome`)" | `STATO_PROGETTO.md:76` — "`utc_to_rome()` + helper condivisi (`formatta_data_ora_rome`, `ora_utc_naive`, `intervalli_si_sovrappongono`)" | **STATO**: il file ha 4 funzioni pubbliche |
| Cosa fa lo scheduler | `README.md:68,139,155` — "il lavoratore che ogni tot minuti controlla i promemoria" | `STATO_PROGETTO.md:45` — "8 job periodici APScheduler (promemoria, recensioni, sync calendario, generazione slot, healthcheck Gmail, retention, pulizia slot, backup)" | **STATO**: 8 job |
| `GET /slots/` | `README.md:150` — "tutti gli slot con `is_available=True`" | `STATO_PROGETTO.md:234` — "`is_available=True` **e** `start_time` non ancora passato" | **STATO**: il filtro sul passato c'è dal commit `3260848` (19/08) |
| Dov'è il codice admin | `README.md:160` — "`backend/routers/admin.py` verifica le credenziali" | `README.md:110` (stesso file!) — "È un package, non un singolo file"; `STATO_PROGETTO.md:63` | **STATO e README:110**: è il package `backend/routers/admin/` dal commit `f48fd22` |
| `SECRET_KEY` | `.env.example:5` — presente, "tenuta per compatibilità" | `README.md` — assente dalla tabella; `STATO_PROGETTO.md:461` — "rimossa" | **README/STATO**: il codice non la legge. `.env.example` è l'unico rimasto indietro |
| `LOG_LEVEL` | `STATO_PROGETTO.md:321` — elencata tra le variabili | `README.md` tabella e `.env.example` — **assente in entrambi** | **STATO**: è letta in `backend/main.py:30` |
| `.env.example` è allineato? | `STATO_PROGETTO.md:14,312` — "allineato al codice attuale", "verificato allineato il 2026-08-31" | il file stesso, che contiene `SECRET_KEY` e non contiene `LOG_LEVEL` | **Il file**: la verifica dichiarata non regge |
| Coverage della suite | `STATO_PROGETTO.md:375,460` — "78%" | misurazione reale ripetuta due volte: `1714` stmt, `351` miss → **80%** | **La misurazione** |
| Numero di tabelle | `STATO_PROGETTO.md:101` — "9 tabelle attive" | lo stesso §2, che poi ne elenca **8** | Incoerenza interna: 8 applicative + `alembic_version` |

**Rimandi interni rotti (verificati uno per uno):**

- **7 riferimenti da codice e test a `ANALISI_2026-08-31.md, Blocco B1/B2/C3/D4`** —
  `backend/routers/admin/dashboard.py:122`, `tests/test_admin.py:112,161,226,280`,
  `tests/test_booking.py:433`. **La stringa "Blocco" non compare in nessun markdown del
  progetto**: `ANALISI_2026-08-31.md` è organizzato per *Area* (Architettura, Back-end, Dati,
  Sicurezza, Performance, Front-end, Test, Build, Osservabilità, Leggibilità), mai per
  blocchi lettera+numero. Quella nomenclatura è esistita solo nei messaggi di commit della
  sessione 31/08. Chi segue il rimando non trova nulla. *(Fa eccezione
  `tests/test_booking.py:210`, che cita "Area Sicurezza/Backend" — quello risolve
  correttamente.)*
- **`STATO_PROGETTO.md` rimanda due volte a "la versione precedente di questo documento"**
  (righe 205 e 342) per contenuti sostanziosi: 11 delle 18 migrazioni e l'intera base della
  sezione §7 sui comportamenti non ovvi. Quella versione esiste solo nella storia git: chi
  legge oggi non può ricostruirla.
- **Rimandi per numero di riga di `ANALISI_2026-08-31.md` ormai sfalsati**: `STATO_PROGETTO.md:91`
  (allora `Architettura.txt`, oggi `recensione.html`) e `README.md:217` (allora `SECRET_KEY`,
  oggi `FRONTEND_ORIGINS`) sono **rotti**; altri otto sono sfalsati di 1-6 righe. Trattandosi
  di un documento storico non vanno corretti, ma confermano che citare i markdown per numero
  di riga si rompe nel giro di giorni.

**Su cosa i documenti attuali invece concordano correttamente** (verificato, nessuna azione):
prezzi e catalogo pacchetti; 82 test; 18 migrazioni e head; 8 job; le 6 rotte con rate limit;
pagamento sempre fuori app; guest checkout come percorso normale; cookie httpOnly per lo
studente e header `Authorization` per l'admin; rotazione della password MySQL ancora aperta
(`ROADMAP.md` P0-1 "todo" ↔ `STATO_PROGETTO.md` §12 backlog ↔ `README.md:323`).

---

# FASE 4 — REFERTO CONSOLIDATO

> Ordinato per **quanto costa a chi si fida del documento per lavorare**, non per quanto è
> sbagliato. Le prime sei voci sono quelle su cui qualcuno costruisce sopra una decisione.

## Gravità ALTA

| # | Documento e riga | Cosa afferma | Cosa risulta | Prova | Verdetto | Correzione proposta |
|---|---|---|---|---|---|---|
| **D1** | `README.md:252` (tabella Comandi) | `pytest` "usa un database SQLite in memoria, **non tocca mai il MySQL di sviluppo o produzione**" | `run_migrations()` è chiamata a livello di modulo, quindi si esegue al semplice import di `backend.main` — cioè quando `conftest.py` importa l'app, **prima di qualunque fixture**. Con un `.env` popolato (presente su questa macchina) `pytest` legge la `DATABASE_URL` **reale** e ci applica sopra `alembic upgrade head`; se ci sono migrazioni in sospeso tenta anche un **backup vero su Google Drive**; se qualcosa fallisce chiama `invia_alert_sistema`, che **non è tra le funzioni sostituite da `conftest.py`** e manda un messaggio Discord vero | `backend/main.py:165` (chiamata a livello modulo) + `tests/conftest.py:28` (`from backend.main import app`) + `backend/database.py:16` (`load_dotenv()`). Verificato eseguendo con `DATABASE_URL` forzata a SQLite: `run_migrations()` finisce sempre nel ramo `except` (il dump usa `SHOW TABLES`, il DDL è MySQL) e chiama l'alert. **Non ho eseguito la prova contro il MySQL reale**, per non modificare nulla in questa sessione: la catena è dimostrata staticamente | **DISALLINEATO** | Sostituire la riga con: "`pytest` — esegue la suite. I *test* girano su SQLite in memoria, ma l'import di `backend.main` esegue `run_migrations()` sulla `DATABASE_URL` dell'ambiente: **lancialo sempre con `DATABASE_URL` e `JWT_SECRET` fittizie**, come fa la CI, altrimenti tocca il DB di sviluppo reale e può mandare un alert Discord vero." Allineare anche il commento in `.github/workflows/tests.yml` ("mai usato per davvero"). *Il fix vero è nel codice (`R1`) ed è materiale per la sessione 2* |
| **D2** | `ANALYSIS.md:1-3` e `ROADMAP.md:1-3` (intestazioni) | Nessuna dichiarazione di storicità. `ANALYSIS.md` porta una data solo dentro un titolo di sezione a metà file (`§5 ... (2026-08-06)`); **`ROADMAP.md` non ha nessuna data**, e il suo header lo presenta come piano vivo ("Stato aggiornabile ... man mano che si procede") | Sono superati quasi integralmente. Un lettore che apre solo `ANALYSIS.md` conclude che oggi `GET /users/`, `GET /bookings/` e `POST /slots/` sono pubblici, il CORS è `*`, le credenziali MySQL sono in chiaro nel codice, la password admin è confrontata con `==`, non esiste scheduler, le email passano da SendGrid, i prezzi sono 35/60/80€ | Confrontati con la Fase 1: tutti quegli endpoint hanno `Depends(get_admin)`; CORS ristretto a `FRONTEND_ORIGINS` (`main.py:197-202`); `database.py:25` solleva `RuntimeError`; `auth_service.py:53` usa `bcrypt.checkpw`; 8 job in `scheduler.py`; Gmail API; `TABELLA_PREZZI = {1:2000, 2:4000}` | **INCOMPLETO** (manca la dichiarazione; il contenuto è legittimamente congelato e **non va allineato**) | Aggiungere in testa a **entrambi**, come primo blocco citato, una riga tipo: "> ⚠️ **DOCUMENTO STORICO — non descrive lo stato attuale.** Fotografa il progetto al `<data>`. Tutto ciò che segue è stato in gran parte superato: per lo stato di oggi vedi `STATO_PROGETTO.md`. Conservato come memoria delle decisioni prese allora, **non va aggiornato**." Per `ROADMAP.md` la data va **stabilita** (dal git log: gli step P0-P3 coprono il periodo 2026-08-06 → 2026-08-21) |
| **D3** | `ANALISI_2026-08-31.md:1-2` (intestazione) | Ha la data (2026-08-31) e il metodo, ma **non dice che i findings sono stati chiusi** | Tutte le criticità elencate risultano corrette tra il 31/08 e l'01/09. Chi lo apre oggi senza aver letto `STATO_PROGETTO.md` §12 conclude che l'app ha **adesso** due vulnerabilità Alta severità sfruttabili senza credenziali (account takeover Discord, IDOR su `booking.user_id`) | Commit `d30a3de`, `e567d11`, `97b56ec`, `4e711e8`, `e32c032`, `bee9345`, `0ee7182`, `2114b73`, `fd0b78e`, `efbe886` — più i test che riproducono i due abusi e li dimostrano bloccati (`tests/test_booking.py:210`, `:433`) | **INCOMPLETO** (come `D2`: il contenuto è un verbale e **non va allineato**) | Aggiungere sotto la riga della data: "> ✅ **Findings chiusi.** Tutte le criticità di questo referto sono state corrette nella sessione 31/08–01/09 (vedi `STATO_PROGETTO.md` §12 per l'elenco commit per commit). Questo file resta il verbale di **cosa la review trovò quel giorno**, non lo stato attuale: non va aggiornato." |
| **D4** | `STATO_PROGETTO.md:3` (intestazione) | "aggiornato al commit `1732fc2`, **2026-08-31**" e "Aggiornato ulteriormente ... **fino al commit `61d4554`**" | `1732fc2` è del **2026-08-26**, non del 31/08. E il documento è stato modificato **dopo** `61d4554`, dal commit `5c495cb` (HEAD), che tocca esattamente e solo `STATO_PROGETTO.md`: il file dichiara di fermarsi un commit prima della propria ultima modifica | `git log -1 1732fc2` → `2026-08-26`; `git show --stat 5c495cb` → `STATO_PROGETTO.md | 15 +++---` | **DISALLINEATO** | Riscrivere il riferimento come: "aggiornato al commit **`5c495cb`** (2026-09-01)", separando la data del documento dalla data dei commit citati. Meglio ancora: smettere di inseguire l'hash a ogni modifica e scrivere "aggiornato al **2026-09-01**", lasciando a `git log` il compito degli hash |
| **D5** | `STATO_PROGETTO.md:14` e `:312` | "`.env.example` — template dei nomi di variabile, **allineato al codice attuale**" / "(verificato allineato al codice il 2026-08-31)" | `.env.example` contiene `SECRET_KEY`, **mai letta da nessuna riga del progetto**, e **non contiene `LOG_LEVEL`**, che invece è letta | `grep -rn 'getenv("SECRET_KEY")' .` → zero risultati; `backend/main.py:30` → `os.getenv("LOG_LEVEL", "INFO")`; `.env.example:5` | **DISALLINEATO** | In `.env.example`: rimuovere il blocco `SECRET_KEY` (righe 4-5) e aggiungere `LOG_LEVEL=INFO` con la nota "livello minimo dei log (INFO/DEBUG/WARNING); DEBUG solo in fase di indagine". In `STATO_PROGETTO.md`: aggiornare la data della verifica solo *dopo* aver fatto la correzione |
| **D6** | `STATO_PROGETTO.md:375` e `:460` | "coverage 78%" (§9) e "coverage 67% → **78%**" (§12.3) | **80%** — `1714` statement, `351` non coperti. Misurato due volte con lo stesso comando della CI. Nessun commit dopo `2114b73` tocca il codice (gli ultimi due sono solo doc), quindi il numero era già 80% quando è stato scritto 78% | `venv/Scripts/python.exe -m pytest` con `DATABASE_URL="sqlite:///:memory:"` e `JWT_SECRET="test-secret"` → `TOTAL 1714 351 80%`, `82 passed` | **DISALLINEATO** | Sostituire "78%" con "80%" in entrambi i punti (§12.3 diventa "coverage 67% → **80%**") |

## Gravità MEDIA

| # | Documento e riga | Cosa afferma | Cosa risulta | Prova | Verdetto | Correzione proposta |
|---|---|---|---|---|---|---|
| **D7** | `README.md` tabella variabili (righe 214-240) e `.env.example` | `LOG_LEVEL` non compare in nessuno dei due | È letta e usata per configurare il logging di tutto il progetto | `backend/main.py:30,42` | **INCOMPLETO** | Aggiungere alla tabella README: "\| `LOG_LEVEL` \| No \| Livello minimo dei messaggi di log (default `INFO`). Portalo a `DEBUG` solo per un'indagine. \|" e la riga corrispondente in `.env.example` (vedi `D5`) |
| **D8** | `README.md:100` | "`timezone_service.py` — **un'unica funzione** (`utc_to_rome`) che converte un orario UTC nell'ora italiana" | Il file espone **4 funzioni pubbliche**: `utc_to_rome`, `formatta_data_ora_rome`, `ora_utc_naive`, `intervalli_si_sovrappongono` — le ultime tre estratte nella sessione del 31/08 proprio perché ripetute in una dozzina di punti | `backend/services/timezone_service.py`; `STATO_PROGETTO.md:76` le elenca correttamente | **CONTRADDIZIONE TRA DOCUMENTI** | "`timezone_service.py` — le conversioni e i confronti di orario condivisi da tutto il progetto: `utc_to_rome()` (UTC → ora italiana, per la visualizzazione), `formatta_data_ora_rome()`, `ora_utc_naive()` ("adesso" nella stessa forma salvata nel DB) e `intervalli_si_sovrappongono()`." |
| **D9** | `README.md:68`, `:139`, `:155` | Lo scheduler è "il lavoratore in background che ogni tot minuti controlla se ci sono prenotazioni imminenti a cui inviare un promemoria"; l'avvio "avvia lo scheduler **dei promemoria**" | Sono **8 job**: promemoria, richieste recensione, sync calendario, generazione slot notturna, healthcheck Gmail, retention GDPR, pulizia slot obsoleti, backup del database. Chi legge solo il README crede che toccare lo scheduler riguardi solo le email di promemoria | `backend/scheduler.py:347-429`; `STATO_PROGETTO.md:45` li elenca correttamente | **CONTRADDIZIONE TRA DOCUMENTI** + **INCOMPLETO** | Riga 68: "`scheduler.py` — gli **8 lavori automatici in background** che girano senza che nessuno li chieda: promemoria pre-sessione, richieste di recensione, sync col Google Calendar, generazione notturna degli slot dalle regole ricorrenti, controllo del token Gmail, anonimizzazione GDPR dei clienti inattivi, pulizia degli slot passati, backup del database su Drive." Righe 139 e 155: togliere "dei promemoria" |
| **D10** | `README.md:160` | "**`backend/routers/admin.py`** verifica le credenziali (`auth_service.py`) e restituisce un token JWT" | Quel file **non esiste**: è il package `backend/routers/admin/`, e il login vive in `admin/__init__.py`. Lo stesso README lo dice correttamente a riga 110 | `git ls-files backend/routers/`; commit `f48fd22`; `README.md:110` | **DISALLINEATO** (e contraddizione interna al README) | "**`backend/routers/admin/__init__.py`** verifica le credenziali (`auth_service.py`) e restituisce un token JWT" |
| **D11** | `README.md:150` | `GET /slots/` restituisce "tutti gli slot con `is_available=True`" | Filtra **anche** `start_time >= adesso`: uno slot libero ma già passato non viene mai proposto. È il fix del commit `3260848` (19/08), mai recepito dal README | `backend/routers/slots.py:29-33`; `STATO_PROGETTO.md:234` lo dice correttamente | **CONTRADDIZIONE TRA DOCUMENTI** | "...tutti gli slot ancora liberi (`is_available=True`) **e non ancora passati**, e li restituisce come JSON..." |
| **D12** | `README.md:288` | "Lo stesso **controllo di salute** pensato per Gmail ... si applica anche a questo token [Drive]" | Nessun healthcheck controlla `DRIVE_REFRESH_TOKEN`: `controlla_credenziali_gmail` chiama `verifica_credenziali_gmail`, che usa solo `GMAIL_REFRESH_TOKEN`. Un token Drive scaduto si scopre quando **fallisce il backup delle 04:00** (che manda comunque un alert Discord) — una rete diversa e più lenta. *Lettura benevola: la frase può voler dire "lo stesso **problema** di scadenza vale anche per questo token", che è vero. Resta ambigua proprio dove usa il termine tecnico introdotto due paragrafi sopra* | `backend/services/email_service.py:147-154`; `backend/scheduler.py:270-298` | **DISALLINEATO** (ambiguo nella lettura benevola → va comunque reso esplicito) | "La stessa **scadenza** a 7 giorni di inattività vale anche per questo token. Attenzione però: l'healthcheck schedulato controlla **solo** `GMAIL_REFRESH_TOKEN` — un `DRIVE_REFRESH_TOKEN` scaduto si scopre dall'alert Discord del backup notturno fallito, non prima. Portare la schermata di consenso a 'In production' risolve per entrambi insieme." |
| **D13** | `backend/routers/admin/dashboard.py:122`, `tests/test_admin.py:112,161,226,280`, `tests/test_booking.py:433` | Rimandano a "`ANALISI_2026-08-31.md`, **Blocco B1 / B2 / C3 / D4**" | La stringa "Blocco" **non compare in nessun markdown del progetto**. `ANALISI_2026-08-31.md` è strutturato per *Area*, mai per blocchi lettera+numero: quella nomenclatura è esistita solo nei messaggi di commit del 31/08. Chi segue il rimando non trova nulla | `grep -n "Blocco" *.md` → zero risultati; struttura di `ANALISI_2026-08-31.md` (§ "Fase 3 — Analisi area per area") | **RIMANDO ROTTO** (documento↔codice) | Due strade, da scegliere: **(a)** riscrivere i 6 rimandi citando l'Area invece del Blocco (es. "ANALISI_2026-08-31.md, Area Dati" per B2), come già fa correttamente `tests/test_booking.py:210`; **(b)** aggiungere a `ANALISI_2026-08-31.md` una tabella di corrispondenza Blocco→Area. **(a)** è preferibile: non tocca un documento storico. *Modifica al codice → sessione 2* |
| **D14** | `STATO_PROGETTO.md:101` | "MySQL, **9 tabelle attive**" | Il §2 stesso ne elenca **8** (`users`, `slots`, `bookings`, `packages`, `reviews`, `availability_rules`, `availability_exceptions`, `client_notes`). Il numero torna solo contando `alembic_version`, che però non è mai nominata né descritta, e non è una tabella "attiva" dell'applicazione | Il §2 del documento stesso; `backend/models/__init__.py` (8 model) | **DISALLINEATO** (o, se il conteggio includeva `alembic_version`, **INCOMPLETO** perché non lo dice) | "MySQL, **8 tabelle applicative** (più `alembic_version`, gestita da Alembic, non dal codice dell'app)" |
| **D15** | `STATO_PROGETTO.md:383` ("cron di backup notturno (04:00)"), `README.md:278` ("una volta al giorno") | Gli orari dei job notturni sono dati come 03:00 / 03:01 / 03:02 / 04:00 senza specificare il fuso | `BackgroundScheduler()` è costruito **senza** `timezone=`: quegli orari sono nel fuso **del processo**. Su Railway il processo gira in UTC, quindi il backup "delle 04:00" parte in realtà alle **06:00 italiane** d'estate e alle 05:00 d'inverno. In locale sono davvero le 03:00/04:00 italiane | `backend/scheduler.py:360` (`BackgroundScheduler()` senza argomenti), `:384-427` | **INCOMPLETO** | In `STATO_PROGETTO.md` §7, aggiungere un punto: "**I job cron usano il fuso del processo**, non Europe/Rome: `BackgroundScheduler()` è costruito senza `timezone=`. Su Railway (UTC) le 03:00/04:00 dichiarate corrispondono alle 05:00/06:00 italiane. Nessun impatto pratico (sono comunque ore a basso traffico), ma va saputo prima di leggere un log." *Se si preferisce cambiare il comportamento invece della documentazione → sessione 2* |

| **D27** *(nato il 2026-09-02)* | `STATO_PROGETTO.md:382` (§9, "Non ancora verificato"), `:407` (§11 backlog), `:491-492` (§12 backlog) | Elenca come **non verificati** quattro punti: il login Discord end-to-end in produzione col cookie httpOnly ("solo mock + curl finora"), la conferma del flusso OAuth reale, la verifica che le variabili d'ambiente su Railway riflettano `.env.example`, e che il cron di backup notturno abbia davvero prodotto un file da produzione ("solo verificato in locale") | Tutti e quattro chiusi il **2026-09-02**: il login Discord è stato provato end-to-end e **funziona** (dopo l'aggiunta di `DISCORD_CLIENT_ID`/`SECRET`, che semplicemente non esistevano); il flag `Secure` sul cookie è stato verificato da DevTools; le variabili Railway sono state esaminate su entrambi i servizi, trovandone 9 assenti e 5 morte, poi corrette; e la cartella Drive contiene **esclusivamente backup prodotti dalla produzione** (`U7`). Verificato inoltre che lo schema di produzione è alla head `2eac6f32b19b` (`U6`) | `RAILWAY_RIALLINEAMENTO_2026-09-02.md`, STEP 6 punti 4 e 5; sezione "Fase 4b" di questo referto; risposte a `U6` e `U7` | **DISALLINEATO** (dal 2026-09-02: prima era corretto) | Spostare i quattro punti da "Non ancora verificato" a "Verificato", datandoli 2026-09-02 e rimandando a `RAILWAY_RIALLINEAMENTO_2026-09-02.md`. **Resta invece vero e va lasciato dov'è** l'unico punto ancora aperto della lista: l'uptime monitor su `/health` non configurato (confermato: nessuna chiamata nei log). Annotare anche che il login Discord *non poteva* funzionare prima, così non sembra che sia sempre stato a posto e solo non provato |

| **D28** *(nato il 2026-09-02)* | `ROADMAP.md:15-20` (P0-1), `README.md:323`, `STATO_PROGETTO.md:488-490` | Tutti e tre parlano della "password MySQL esposta in chiaro nella storia git" da ruotare, **senza mai dire di quale database si tratti** | La credenziale finita in git (commit `15f536d`, 2026-06-11) è quella del database di **sviluppo locale**. La produzione su Railway usa credenziali root separate, generate dalla piattaforma (`MYSQL_ROOT_PASSWORD` sul servizio MySQL) e mai passate da git | Elenco variabili del servizio MySQL su Railway (Fase 4b); `DATABASE_URL` di produzione punta a `mysql.railway.internal` con credenziali proprie | **INCOMPLETO** — non dicono il falso, ma il silenzio induce a sovrastimare il rischio | Aggiungere in tutti e tre i punti la precisazione: "riguarda il database di **sviluppo locale**; la produzione su Railway usa credenziali separate generate dalla piattaforma, mai finite in git". Senza questa riga, chi legge oggi non sa se sta guardando un'esposizione di produzione ancora aperta da tre mesi — ed è esattamente il motivo per cui il punto è stato rimandato tante volte senza che nessuno sapesse quanto fosse urgente. **La rotazione resta comunque da fare** (`U3`) |

| **D29** *(nato il 2026-09-02)* | `README.md:267`, `STATO_PROGETTO.md:331`, `backend/services/email_service.py:141-143`, `.env.example:16-19` | Tutti e quattro affermano che, con la schermata di consenso OAuth in stato "Testing", il refresh token Google **"scade dopo 7 giorni di inattività dell'app"** | **La spiegazione è smentita dai fatti, ma non è stato possibile stabilire quella giusta.** Due osservazioni reali, entrambe del 2026-09-02: (a) il `GMAIL_REFRESH_TOKEN` è **scaduto** pur essendo esercitato **ogni giorno** (healthcheck `users.getProfile` ogni 24h, più due email per ogni prenotazione) → la regola **non è** "7 giorni di inattività"; (b) il `DRIVE_REFRESH_TOKEN`, emesso all'incirca il 25/08 e quindi vecchio di ~8 giorni, **è ancora valido** → la regola **non è** nemmeno "7 giorni assoluti". Con due soli dati non è determinabile il meccanismo reale | Eventi riportati dall'umano (`U10`, `U11`); `backend/scheduler.py:45` e `backend/services/email_service.py:147-154`, che dimostrano l'uso quotidiano del token Gmail | **DISALLINEATO** | Sostituire la spiegazione causale con ciò che è stato **osservato**, senza rimpiazzare una regola sbagliata con un'altra inventata: *"Finché la schermata di consenso resta in stato «Testing», i refresh token Google scadono periodicamente. Il meccanismo esatto non è stato determinato: il 2026-09-02 il token Gmail è scaduto pur essendo usato ogni giorno (quindi non è una questione di inattività), mentre quello Drive, più vecchio di ~8 giorni, era ancora valido (quindi non è nemmeno una scadenza fissa a 7 giorni). Quel che è certo: l'healthcheck schedulato **rileva** la scadenza, non la previene, e l'unico rimedio noto che la elimina è portare la schermata a «In production»."* **Correzione prioritaria**: la formulazione attuale è la premessa su cui è stato deciso di rimandare `U2`, e non regge |

## Gravità BASSA

| # | Documento e riga | Cosa afferma | Cosa risulta | Prova | Verdetto | Correzione proposta |
|---|---|---|---|---|---|---|
| **D16** | `README.md:74-80`, `:90`, `:96-101`, `:107-111` | Inventari di `models/`, `schemas/`, `services/`, `routers/` | Incompleti: mancano **2 model su 8** (`package.py`, `review.py`), **4 schemi su 9** (`package`, `review`, `consulenza`, `pacchetto_richiesta`), **6 service su 12** (`retention`, `backup`, `google_oauth`, `package`, `booking`, `pagination`), **2 router su 7** (`consulenza.py`, `pacchetti_richieste.py`) | Fotografia §1.1 vs README | **INCOMPLETO** | Completare i quattro elenchi. Ogni voce mancante con una riga sola, nello stesso stile delle esistenti |
| **D17** | `README.md:119-122` | "Ci sono **due pagine web** completamente separate" (index + admin) | Sono **5**: `index.html`, `about.html`, `privacy.html`, `recensione.html`, `admin.html` — tre delle quali hanno una rotta dedicata in `main.py` | `git ls-files frontend/*.html`; `backend/main.py:250-264` | **DISALLINEATO** | "Ci sono cinque pagine: `index.html` (form di prenotazione) e `admin.html` (pannello) sono le due principali e completamente separate; `about.html` (con la vetrina delle recensioni approvate), `privacy.html` e `recensione.html` (pagina pubblica raggiunta dal link post-sessione) sono più semplici" |
| **D18** | `README.md:153` | "si mandano tre notifiche **in parallelo**: email al cliente, email al coach, messaggio Discord" | Sono tre, ma **sequenziali e sincrone**: `invia_conferma_cliente()`, poi `invia_notifica_admin()`, poi `invia_notifica_discord()`, una dopo l'altra dopo il `db.commit()`. Nessuna concorrenza | `backend/routers/booking.py:305-331` | **DISALLINEATO** | "...e si mandano tre notifiche, una dopo l'altra e **dopo** che la prenotazione è già salvata: email al cliente, email al coach, messaggio Discord. Se una fallisce, la prenotazione resta valida lo stesso" |
| **D19** | `STATO_PROGETTO.md:205` | "Le prime **12** sono descritte in dettaglio nella **versione precedente di questo documento** (crea tabelle iniziali → discord_id)" | Da `1972ef07e768` a `0bfc529cd9fd` inclusi sono **11**, non 12. E "la versione precedente" esiste solo nella storia git: chi legge oggi non può ricostruire 11 delle 18 migrazioni | Catena completa nella Fase 1.4 | **DISALLINEATO** + rimando irrisolvibile | Sostituire il rimando con la catena completa (già scritta per esteso in §1.4 di questo referto): 18 righe, costa poco e rende `STATO_PROGETTO.md` autosufficiente come dichiara di essere a riga 3 |
| **D20** | `STATO_PROGETTO.md:342` | "Tutti i punti della **versione precedente di questo documento** restano validi (fusi orari UTC naive, claim atomico, migrazioni automatiche non bloccanti, SMTP bloccato su Railway, ecc.)" | Stesso problema di `D19`, su una sezione più importante: §7 è la sezione dei comportamenti non ovvi, e la sua base è delegata a un testo non consultabile. L'elenco fra parentesi è l'unico appiglio | `STATO_PROGETTO.md:3` dichiara "Non presuppone la lettura di nessun'altra conversazione o documento precedente" — qui la promessa non è mantenuta | **INCOMPLETO** | Espandere i 4-5 punti ereditati in altrettante voci vere in §7 (ognuna 2-3 righe), eliminando il rimando |
| **D21** | `STATO_PROGETTO.md:461-463` | "**rimossa** `SECRET_KEY` (var d'ambiente mai letta, documentata per errore in README)" | Rimossa **solo dal README**. È ancora in `.env.example:5`, con una motivazione ("tenuta per compatibilità") che non corrisponde a nulla nel codice. La formulazione fa credere che la pulizia sia completa | `efbe886` tocca solo `README.md`; `.env.example:5` | **INCOMPLETO** | "rimossa `SECRET_KEY` **dalla tabella del README** (var d'ambiente mai letta, documentata per errore) — vedi `D5`: va tolta anche da `.env.example`" oppure, dopo aver applicato `D5`, semplicemente "rimossa `SECRET_KEY` da README e `.env.example`" |
| **D22** | `README.md:180` | "Serve **Python 3.11+**" | `nixpacks.toml` e la CI fissano **3.11 esatta**, e `STATO_PROGETTO.md` §12.0 racconta che il venv locale è stato ricreato apposta *perché* era su 3.14 — che è formalmente "3.11+". Il README autorizza esattamente la configurazione che è stata trattata come un problema | `nixpacks.toml`; `.github/workflows/tests.yml:27`; `STATO_PROGETTO.md:426` | **INCOMPLETO** | "Serve **Python 3.11** (la stessa versione di produzione e CI — vedi `nixpacks.toml`; una minore o maggiore fa girare i test su un interprete diverso da quello reale) e un server MySQL raggiungibile" |
| **D23** | `STATO_PROGETTO.md:221-229` (tabella Pagine/static) e `README.md` | Nessuno dei due menziona `/docs`, `/redoc`, `/openapi.json` | FastAPI le genera e **non sono disattivate**: l'intera superficie API, endpoint admin compresi, è navigabile pubblicamente da chiunque conosca l'URL. Non è una vulnerabilità (gli endpoint restano protetti), ma è una scelta mai dichiarata | `backend/main.py:171` — `FastAPI(title=..., version="1.0")` senza `docs_url=None` | **INCOMPLETO** | Aggiungere alla tabella §3 di `STATO_PROGETTO.md`: "\| GET \| `/docs`, `/redoc`, `/openapi.json` \| no \| documentazione API generata da FastAPI, **pubblica**: espone lo schema di tutti gli endpoint (non i dati). Scelta consapevole, disattivabile con `docs_url=None` se un domani non la si vuole più \|" |
| **D24** | `STATO_PROGETTO.md:266` | `/admin/dashboard`: "numeri chiave + prossimi slot liberi" | Tra i numeri c'è `media_voto_recensioni`, calcolata su **tutte** le recensioni, comprese quelle non ancora approvate — mentre la vetrina pubblica mostra solo le approvate. I due numeri quindi non coincidono, e nulla lo dice | `backend/routers/admin/dashboard.py:66` (`func.avg(Review.voto)` senza filtro) vs `booking.py:385` (`Review.approvata == True`) | **INCOMPLETO** | "numeri chiave + prossimi slot liberi. Nota: `media_voto_recensioni` è calcolata su **tutte** le recensioni ricevute, anche quelle non ancora approvate — è un dato interno per il coach, diverso da quello che il pubblico vede in `about.html`" |
| **D25** | `README.md:224` (tabella variabili) | `DISCORD_CLIENT_ID`/`SECRET`/`OAUTH_REDIRECT_URI` — "Obbligatoria: **No** (per il login Discord)" | `DISCORD_OAUTH_REDIRECT_URI` fa **anche** un secondo lavoro non dichiarato: determina il flag `secure` di **entrambi** i cookie (sessione studente e state OAuth). In produzione, se non inizia con `https://`, il cookie di sessione viaggia senza `Secure`. Una variabile presentata come facoltativa ha quindi un effetto di sicurezza | `backend/routers/discord_auth.py:43` (`_IS_PRODUZIONE`), usata a `:103` e `:249`; `STATO_PROGETTO.md:345` lo documenta correttamente | **INCOMPLETO** | Spezzare la riga e aggiungere per `DISCORD_OAUTH_REDIRECT_URI`: "In produzione **deve** iniziare con `https://`: da questo l'app deduce di essere in produzione e marca `Secure` i cookie di sessione (Railway termina l'HTTPS a monte, quindi non è deducibile dalla richiesta)" |
| **D26** | `ANALISI_2026-08-31.md` — rimandi per numero di riga | Cita `STATO_PROGETTO.md:91`, `:370`, `:391`, `README.md:217`, `:270`, `:324`, `:327` e altri | Due sono **rotti** (`STATO_PROGETTO.md:91` oggi è `recensione.html`, allora era `Architettura.txt`; `README.md:217` oggi è `FRONTEND_ORIGINS`, allora era `SECRET_KEY`), gli altri sfalsati di 1-6 righe | Confronto diretto con i file attuali | **INCOMPLETO** — ma su un documento **storico**: non va corretto | Nessuna correzione a `ANALISI_2026-08-31.md`. La lezione da registrare altrove: **non citare i markdown per numero di riga**, si rompe in giorni. Usare il titolo di sezione (`§7.7`, "Area Sicurezza"). Vale per i rimandi futuri in `STATO_PROGETTO.md` e nei commenti del codice |

## Cosa ho verificato e risultava a posto

Registrato perché una sessione futura non ricontrolli a vuoto: i prezzi (backend ↔ frontend ↔
documenti), il catalogo pacchetti, il numero di test (82), il numero e la catena delle
migrazioni, gli 8 job dello scheduler con i rispettivi nomi, i 6 endpoint con rate limit,
tutte le colonne delle 8 tabelle in `STATO_PROGETTO.md` §2, `MAX_PRENOTAZIONI_ATTIVE`,
`ORE_INIZIO_VALIDE_2H` (backend ↔ frontend), le 6 metriche di `/admin/analytics`, il flag
`secure` derivato dal redirect URI, il venv su Python 3.11, la tabella variabili del README
(corretta su 25 voci su 26), e le sezioni Gmail/Calendar/Drive/Discord/Deploy/GDPR del README.

**Due casi in cui il documento ha ragione e il codice ha torto** — nessuna correzione al
documento, il fix è nel codice (sessione 2): `AvailabilityRule.attiva` (`R3`) e il docstring
di `DELETE /admin/slots/{id}` (`R7`).

## Domande che solo tu puoi chiudere

Riguardano stati esterni al repository. Le formulo in modo che si possano verificare e
rispondere una per una.

| # | Domanda esatta | Perché conta |
|---|---|---|
| **U1** | Nella dashboard Railway → progetto → Variables, sono impostate **tutte** le 26 variabili lette dal codice (elenco in §1.6)? In particolare `LOG_LEVEL`, `PUBLIC_BASE_URL`, `RETENTION_MONTHS`, `DRIVE_REFRESH_TOKEN`, `GOOGLE_DRIVE_BACKUP_FOLDER_ID`? | `STATO_PROGETTO.md` §12 backlog lo elenca come da verificare. Se `PUBLIC_BASE_URL` manca, i link di recensione nelle email puntano alla prima origine di `FRONTEND_ORIGINS`; se manca `DRIVE_REFRESH_TOKEN`, **non esiste nessun backup** |
| **U2** | Su Google Cloud Console → OAuth consent screen, lo stato è ancora **"Testing"** o è stato portato a **"In production"**? | Decide se i refresh token Gmail **e** Drive continuano a scadere dopo 7 giorni di inattività. È il primo item del backlog sia in `STATO_PROGETTO.md` §12 sia in `ANALISI_2026-08-31.md` |
| **U3** | La password dell'utente MySQL esposta in chiaro nel commit `15f536d` (2026-06-11) è stata **ruotata** sul server? | Aperta da giugno. `ROADMAP.md` P0-1 la segna "todo", `README.md:323` la ripete, `STATO_PROGETTO.md` §12 la lascia nel backlog: **nessun documento la dichiara chiusa**. È l'unico punto ancora aperto della roadmap storica |
| **U4** | Qual è il valore di `DISCORD_OAUTH_REDIRECT_URI` su Railway — inizia con `https://`? | Se no, i cookie di sessione studente in produzione vengono emessi **senza** il flag `Secure` (vedi `D25`) |
| **U5** | Il run GitHub Actions `33529945237` citato in `STATO_PROGETTO.md:3` è effettivamente verde, e ne sono seguiti altri dopo il commit `5c495cb`? | `STATO_PROGETTO.md` §9 costruisce su questo il "CI verde riconfermata sul push reale". Non verificabile dal repo |
| **U6** | Nel database di **produzione**, la riga di `alembic_version` corrisponde a `2eac6f32b19b`? | Se la produzione è indietro, alcune colonne (`anonimizzato_at`, gli indici) potrebbero non esistere e i job di retention fallirebbero silenziosamente |
| **U7** | La cartella Drive dei backup contiene file recenti prodotti **dalla produzione** (nome tipo `vgc-coaching-backup-AAAA-MM-GG_HHMM.sql`), o solo quelli generati in locale? | `STATO_PROGETTO.md` §9 lo elenca fra i "non ancora verificati". Un backup che non gira è indistinguibile da uno che gira, finché non serve |
| **U8** | Esiste un monitor esterno (UptimeRobot o simile) puntato su `GET /health` del dominio di produzione? | `STATO_PROGETTO.md` §9 dice di no, `README.md:309` lo raccomanda come step 7 del deploy. Serve solo confermare quale delle due è vera oggi |

---

# FASE 4b — ESITO DI U1/U4: LE VARIABILI REALI SU RAILWAY (2026-09-02)

> L'umano ha fornito il blocco variabili del servizio applicativo su Railway. Il file è stato
> letto **solo tramite filtri** che stampano nomi, lunghezze e i valori non segreti: nessun
> segreto è entrato nel referto né nel transcript. File di lavoro nello scratchpad di
> sessione, fuori dal repository, da cancellare a verifica conclusa.

**Struttura trovata:** 26 variabili impostate sul servizio app. **13 sono valori letterali**,
**13 sono riferimenti Railway** nella forma `${{MySQL.NOME}}`, cioè puntatori a variabili
definite sul servizio **MySQL** (pattern legittimo: metà della configurazione è tenuta lì e
referenziata da qui). I valori dietro quei 13 riferimenti **non sono visibili da questo file**
— per chiuderli serve l'elenco variabili del servizio MySQL (vedi `U1-bis`).

Riferimenti a `${{MySQL....}}`: `ADMIN_USERNAME`, `DATABASE_URL`, `EMAIL_ADMIN`,
`EMAIL_MITTENTE`, `GMAIL_CLIENT_ID`, `GOOGLE_CALENDAR_ID`, `GOOGLE_PRIVATE_KEY`,
`GOOGLE_SERVICE_ACCOUNT_EMAIL`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `JWT_SECRET`,
`PAYPAL_EMAIL`, `SECRET_KEY`.

**Conteggio rispetto alle 32 lette dal codice:** 23 presenti, **9 assenti**, **3 impostate e
mai lette** (`PAYPAL_EMAIL`, `SECRET_KEY`, `REMINDER_CHECK_INTERNAL_MINUTES`).

## Ritrovamenti di configurazione (numerati `P1`–`P9`)

> `P1`–`P6` sono emersi dal servizio app, `P7`–`P9` dal secondo giro sul servizio MySQL
> (sezione successiva). `P1`–`P8` sono stati corretti il 2026-09-02; `P9` resta aperto.

Sono difetti dell'**ambiente di produzione**, non dei documenti: vanno tenuti separati sia da
`D*` (documenti) sia da `R*` (codice). Nessuno è stato toccato.

### P1 — `DISCORD_CLIENT_ID` e `DISCORD_CLIENT_SECRET` non sono impostate. Il login Discord in produzione non può funzionare.
**Gravità: alta.** Nell'elenco compaiono `DISCORD_OAUTH_REDIRECT_URI` e `DISCORD_WEBHOOK_URL`,
ma **non** le due credenziali dell'app OAuth. Su Railway una variabile definita su un altro
servizio non è visibile finché non la si referenzia esplicitamente: se non è in questo elenco,
`os.getenv("DISCORD_CLIENT_ID")` restituisce `None` nel processo dell'app.

Conseguenza diretta nel codice: `discord_login()` (`backend/routers/discord_auth.py:77-84`)
costruisce l'URL di autorizzazione con `client_id=None`, e `discord_callback` non potrebbe
comunque scambiare il code senza `client_secret`. **Il bottone "Accedi con Discord" non può
portare a un login riuscito.**

Questo spiega retroattivamente perché `STATO_PROGETTO.md` §9 e §11 elencano da settimane
"Login Discord studente end-to-end in produzione" fra le cose *non ancora verificate*: non è
solo non verificato, è quasi certamente **non funzionante**. Da confermare con `U1-bis`
(potrebbero essere sul servizio MySQL ma non referenziate — che è comunque una rottura).

### P2 — Le email di richiesta recensione contengono un link rotto
**Gravità: alta.** `PUBLIC_BASE_URL` **non è impostata**. Il codice
(`backend/scheduler.py:38-41`) ricade allora sulla prima origine di `FRONTEND_ORIGINS`, che su
Railway vale `vgc-coaching-production.up.railway.app` — **senza schema `https://`**.

Il link costruito a `backend/scheduler.py:201` diventa quindi:
`vgc-coaching-production.up.railway.app/static/recensione.html?booking_id=...&token=...`
che non è un URL assoluto valido: un client email lo rende come testo o come link relativo,
non come indirizzo cliccabile. **La funzione recensioni non è mai stata utilizzabile in
produzione**, pur essendo descritta come attiva in `STATO_PROGETTO.md` §4.

Due modi per chiuderlo, entrambi da riga di configurazione:
impostare `PUBLIC_BASE_URL=https://vgc-coaching-production.up.railway.app`, **oppure**
aggiungere lo schema a `FRONTEND_ORIGINS` (che va comunque fatto, vedi `P3`).

### P3 — `FRONTEND_ORIGINS` non ha lo schema: il CORS non può corrispondere a nessuna origine
**Gravità: media.** Vale `vgc-coaching-production.up.railway.app`. `allow_origins` di
`CORSMiddleware` confronta stringhe con l'header `Origin` del browser, che è sempre nella
forma `https://host`: un hostname nudo non combacia mai. In pratica oggi è innocuo — frontend
e API stanno sulla stessa origine, quindi il browser non fa richieste cross-origin — ma
significa che la configurazione CORS **non autorizza nulla**, e che il giorno in cui servisse
una seconda origine non funzionerebbe. È anche la causa di `P2`.
**Correzione:** `FRONTEND_ORIGINS=https://vgc-coaching-production.up.railway.app`.

### P4 — `DISCORD_OAUTH_REDIRECT_URI` è `http://`, non `https://` → cookie di sessione senza `Secure`
**Gravità: media.** Vale `http://vgc-coaching-production.up.railway.app/auth/discord/callback`.
**Questa è la risposta a `U4`.** `backend/routers/discord_auth.py:43` deduce l'ambiente proprio
da qui: `_IS_PRODUZIONE = DISCORD_OAUTH_REDIRECT_URI.startswith("https://")` → **False**. Di
conseguenza **entrambi** i cookie (`student_token` e `discord_oauth_state`) vengono emessi in
produzione **senza il flag `Secure`** (righe 103 e 249).

`README.md:326` afferma che il cookie di sessione è "`secure` in produzione": oggi **non lo è**.
Va inoltre ricordato che Discord accetta redirect URI in `http://` solo per `localhost`, il che
è un secondo motivo per cui `P1` non potrebbe funzionare comunque.
**Correzione:** portare la variabile a `https://...` (e allineare il redirect URI sul Discord
Developer Portal).

### P5 — `REMINDER_CHECK_INTERNAL_MINUTES`: refuso, la variabile non viene mai letta
**Gravità: bassa.** Su Railway c'è `REMINDER_CHECK_INTERNAL_MINUTES` (INTER**N**AL); il codice
legge `REMINDER_CHECK_INTERVAL_MINUTES` (INTER**V**AL) a `backend/scheduler.py:30`. La
variabile impostata non ha quindi **nessun effetto**: lo scheduler usa il default di 5 minuti.
Oggi l'esito coincide (il valore impostato è anch'esso `5`), quindi non si nota — ma chiunque
provasse a cambiarla vedrebbe il sistema ignorarlo.
**Correzione:** rinominarla su Railway.

### P6 — `SECRET_KEY` e `PAYPAL_EMAIL` sono configurate in produzione e non le legge nessuno
**Gravità: bassa.** Entrambe presenti come riferimenti a `${{MySQL....}}`. `SECRET_KEY` è la
variabile morta di `D5`, che risulta quindi impostata **in tre posti** (`.env` locale,
`.env.example`, Railway) e letta in nessuno. `PAYPAL_EMAIL` è un residuo del flusso di
pagamento rimosso da `ROADMAP.md` P0-3 (agosto): il codice non la nomina più da nessuna parte.
**Correzione:** rimuoverle da Railway e dal servizio MySQL, insieme a `D5`.

### Assenti ma innocue (il default del codice copre)
`LOG_LEVEL` (→`INFO`), `RETENTION_MONTHS` (→24), `REVIEW_CHECK_INTERVAL_MINUTES` (→60),
`CALENDAR_SYNC_INTERVAL_MINUTES` (→60), `GMAIL_HEALTHCHECK_INTERVAL_HOURS` (→24),
`REMINDER_CHECK_INTERVAL_MINUTES` (→5, vedi `P5`). Nessun intervento necessario: vale la pena
notare però che `STATO_PROGETTO.md` §5 le presenta come impostate, mentre in produzione
funzionano per default.

## Secondo giro: le variabili del servizio MySQL (2026-09-02)

25 variabili sul servizio MySQL: 22 letterali e 3 riferimenti interni di Railway. **Tutti e 13
i riferimenti `${{MySQL....}}` del servizio app risolvono correttamente**: i valori esistono.
`DATABASE_URL` è ben formata (`mysql+pymysql://…@mysql.railway.internal:3306/railway`, driver
giusto, rete privata). Questo chiude il dubbio principale di `U1-bis`.

### P7 — La vecchia password admin **in chiaro** è ancora su Railway
**Gravità: alta.** Il servizio MySQL contiene `ADMIN_PASSWORD` con un valore di **13
caratteri**. Non è un hash bcrypt (sarebbero 60, e infatti `ADMIN_PASSWORD_HASH` sul servizio
app ne ha esattamente 60): è la **password in chiaro**, residuo della migrazione ad hash di
agosto. `scripts/hash_admin_password.py:70` istruisce esplicitamente a *"rimuovere
ADMIN_PASSWORD"* da Railway, e `STATO_PROGETTO.md` §11.5 dà lo scambio per fatto — **non lo è**.

Il codice non la legge (nessun `os.getenv("ADMIN_PASSWORD")`), quindi non c'è un impatto
funzionale: il problema è che la password del pannello admin è leggibile in chiaro da chiunque
apra la dashboard Railway, vanificando il senso di averla messa sotto bcrypt.

### P8 — `GMAIL_REFRESH_TOKEN` esiste in due copie **divergenti**
**Gravità: media.** È definito come valore letterale su **entrambi** i servizi, e i due valori
**sono diversi** (confronto fatto per hash SHA-256, senza mai leggere i valori:
`f275036a6297…` sul servizio app, `03003e442279…` sul servizio MySQL). Quella che conta è la
copia sul **servizio app**, perché il codice legge la variabile locale del proprio servizio;
la copia su MySQL non è referenziata da nessuno ed è verosimilmente un token vecchio, rimasto
lì da una re-autorizzazione precedente.

Il rischio è concreto e insidioso: la maggior parte della configurazione vive sul servizio
MySQL, quindi al prossimo `reauth_gmail.py` il posto "naturale" dove incollare il token nuovo
è proprio quello sbagliato — e l'invio email resterebbe fermo senza che nulla lo spieghi.
`GMAIL_CLIENT_SECRET` è anch'esso duplicato, ma con valore **identico**: innocuo oggi, stessa
trappola domani.

### P9 — La configurazione è divisa tra due servizi senza un criterio
**Gravità: bassa (ma è la causa di P8).** Le credenziali Gmail sono spezzate a metà:
`GMAIL_CLIENT_ID` sta sul servizio MySQL ed è referenziata, mentre `GMAIL_CLIENT_SECRET` e
`GMAIL_REFRESH_TOKEN` sono letterali sul servizio app. Non c'è una regola che dica dove va
cosa. Consolidare tutte le variabili **applicative** sul servizio app, lasciando su quello
MySQL solo ciò che Railway genera da sé, eliminerebbe alla radice la classe di problema di P8.

### G1 — Un commit non è mai stato pushato — **CHIUSO il 2026-09-03**
> Risolto: il push del 2026-09-03 (`61d4554..1e17319`, 8 commit, CI verde sul run
> `33690855235`) ha portato in remoto sia `5c495cb` sia tutto il lavoro delle sessioni 2 e 3.
> Il testo qui sotto resta com'era: descrive la situazione al 2026-09-01.

**Gravità: media.** `git status` → `master...origin/master [ahead 1]`. Il commit **`5c495cb`**
esiste solo su questa macchina; `origin/master` è fermo a `61d4554`. Nessun commit remoto
manca in locale, e **nessun codice è coinvolto**: `5c495cb` tocca solo `STATO_PROGETTO.md`
(+9/−6). Il codice su GitHub è quindi identico a quello locale.

Vale però la pena notare l'ironia, perché è esattamente il tipo di deriva che questa revisione
cerca: `5c495cb` si intitola *"docs: registra push+CI reali"* ed è il commit che aggiunge a
`STATO_PROGETTO.md` la frase *"il lavoro non esiste più solo su questa macchina"*. Quella
frase, in questo momento, esiste solo su questa macchina.

## Stato aggiornato delle domande U

- **U1 — CHIUSA.** Entrambi i servizi esaminati. 23 delle 32 variabili attese sono presenti e
  risolvono; 9 assenti, di cui 6 coperte da default sensati e 3 con effetto reale
  (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `PUBLIC_BASE_URL`); 5 impostate e mai lette
  (`SECRET_KEY` ×2, `PAYPAL_EMAIL` ×2, `ADMIN_PASSWORD`), più 1 con refuso
  (`REMINDER_CHECK_INTERNAL_MINUTES`). **`DISCORD_CLIENT_ID` e `DISCORD_CLIENT_SECRET` non
  esistono su nessuno dei due servizi**: `P1` è confermato, non è un problema di riferimenti
  mancanti. Piano di riallineamento nella sezione seguente.

## Piano di riallineamento Railway (esito operativo di U1)

> Questo piano è stato espanso in un runbook operativo a parte:
> **`RAILWAY_RIALLINEAMENTO_2026-09-02.md`** (root del progetto), con l'ordine delle
> operazioni, le avvertenze e i passi di verifica. Qui resta il riassunto.
>
> ## ✅ APPLICATO il 2026-09-02
>
> Gli step 1-5 sono stati eseguiti sulla dashboard Railway. **Sono modifiche alla
> configurazione di produzione, non al repository:** il vincolo "questa sessione non modifica
> niente" riguarda codice e documenti, che restano intatti. Il push di `5c495cb` e tutte le
> modifiche ai file sono ancora rimandate alla fine della sessione.
>
> **Chiusi in produzione:** `P1` (login Discord — ora funziona), `P2` (`PUBLIC_BASE_URL`
> impostata, da confermare alla prima email reale), `P3` (schema su `FRONTEND_ORIGINS`), `P4`
> (cookie con flag `Secure`, verificato), `P5` (refuso `INTERNAL`→`INTERVAL`), `P6` e `P7`
> (`SECRET_KEY`, `PAYPAL_EMAIL`, `ADMIN_PASSWORD` in chiaro rimosse), `P8` (copia divergente
> di `GMAIL_REFRESH_TOKEN` rimossa).
> **Resta aperto:** `P9` — il consolidamento della configurazione su un solo servizio,
> rimandato deliberatamente.
>
> **Effetto collaterale sui documenti:** l'affermazione di `README.md:326` (il cookie di
> sessione è "`secure` in produzione"), che al momento della revisione era **falsa**, ora è
> **vera**. Non richiede più correzione — è stato il codice a raggiungere il documento, non il
> contrario. Nasce invece un nuovo rilievo, `D27`.

### Servizio APP — da AGGIUNGERE (3)
| Variabile | Valore | Perché |
|---|---|---|
| `DISCORD_CLIENT_ID` | dal Discord Developer Portal → OAuth2 → General | Senza, il login Discord non può funzionare (`P1`) |
| `DISCORD_CLIENT_SECRET` | idem | idem |
| `PUBLIC_BASE_URL` | `https://vgc-coaching-production.up.railway.app` | Chiude il link rotto nelle email di recensione (`P2`) |

### Servizio APP — da CORREGGERE (3)
| Variabile | Da | A | Perché |
|---|---|---|---|
| `FRONTEND_ORIGINS` | `vgc-coaching-production.up.railway.app` | `https://vgc-coaching-production.up.railway.app` | Senza schema il CORS non combacia con nessuna origine (`P3`); è anche la concausa di `P2` |
| `DISCORD_OAUTH_REDIRECT_URI` | `http://…/auth/discord/callback` | `https://…/auth/discord/callback` | Ripristina il flag `Secure` sui cookie di sessione (`P4`). **Aggiornare lo stesso URI anche sul Discord Developer Portal**, devono coincidere |
| `REMINDER_CHECK_INTERNAL_MINUTES` | nome storpiato | `REMINDER_CHECK_INTERVAL_MINUTES` | Oggi la variabile non viene letta (`P5`) |

### Servizio APP — da ELIMINARE (2)
`SECRET_KEY`, `PAYPAL_EMAIL` — riferimenti a variabili morte, nessuna riga di codice le legge.

### Servizio MYSQL — da ELIMINARE (5)
| Variabile | Perché |
|---|---|
| `ADMIN_PASSWORD` | Password admin **in chiaro**, sostituita da `ADMIN_PASSWORD_HASH` ad agosto e mai rimossa (`P7`) |
| `GMAIL_REFRESH_TOKEN` | Copia **divergente e non referenziata**: quella viva è sul servizio app (`P8`) |
| `GMAIL_CLIENT_SECRET` | Copia identica ma non referenziata: l'app usa la propria (`P8`) |
| `SECRET_KEY` | Mai letta da nessuna riga di codice |
| `PAYPAL_EMAIL` | Residuo del flusso PayPal rimosso in `ROADMAP.md` P0-3 (agosto) |

### Da NON TOCCARE
- **Tutte le `MYSQL*` sul servizio MySQL** (`MYSQLDATABASE`, `MYSQLHOST`, `MYSQLPASSWORD`,
  `MYSQLPORT`, `MYSQLUSER`, `MYSQL_DATABASE`, `MYSQL_PUBLIC_URL`, `MYSQL_ROOT_PASSWORD`,
  `MYSQL_URL`): le genera e le gestisce Railway. Rimuoverle rompe il database.
- Gli 11 riferimenti `${{MySQL....}}` che restano dopo le eliminazioni, e i valori dietro:
  verificati esistenti e coerenti.
- `DATABASE_URL`: formato corretto, driver `mysql+pymysql`, host della rete privata interna.
- Sul servizio app: `ADMIN_PASSWORD_HASH` (bcrypt, 60 caratteri), `DRIVE_REFRESH_TOKEN`,
  `GOOGLE_DRIVE_BACKUP_FOLDER_ID`, `DISCORD_WEBHOOK_URL`, `GMAIL_CLIENT_SECRET`,
  `GMAIL_REFRESH_TOKEN`, `COACH_DISCORD_TAG`, `COACH_TELEGRAM_CONTACT`,
  `BACKUP_RETENTION_DAYS`, `REMINDER_HOURS_BEFORE`.
- **Le 6 variabili assenti che hanno un default sensato**: `LOG_LEVEL` (INFO),
  `RETENTION_MONTHS` (24), `REVIEW_CHECK_INTERVAL_MINUTES` (60),
  `CALENDAR_SYNC_INTERVAL_MINUTES` (60), `GMAIL_HEALTHCHECK_INTERVAL_HOURS` (24) e
  `REMINDER_CHECK_INTERVAL_MINUTES` (5, una volta rinominata). Non serve impostarle: i default
  del codice **sono** i valori voluti. Va però corretto `STATO_PROGETTO.md` §5, che le presenta
  come configurate.

### Da valutare (non un difetto, una scelta)
`MYSQL_PUBLIC_URL` esiste, quindi il database ha un proxy TCP pubblico raggiungibile da
Internet con la password di root. È il default di Railway ed è comodo per un ripristino
manuale (`README.md` §Backup lo presuppone). Se non serve, disattivare il proxy riduce la
superficie esposta; se serve, va lasciato — ma è bene saperlo.
- **U4 — CHIUSA e RISOLTA.** `DISCORD_OAUTH_REDIRECT_URI` iniziava con `http://`: i cookie di
  produzione erano emessi senza `Secure`. Corretta il 2026-09-02 e **verificata da DevTools**:
  `student_token` ha ora `Secure` e `HttpOnly`. Vedi `P4`.
- **U8 — CHIUSA: nessun monitor esterno è configurato.** Cercando `GET /health` nei log di
  Railway il 2026-09-02 non compare nessuna chiamata. L'endpoint **funziona** (verificato
  interrogandolo a mano: risponde correttamente, quindi anche il `SELECT 1` sul database va a
  buon fine): semplicemente **nessuno lo interroga**. È la conferma osservativa di quanto
  `STATO_PROGETTO.md` §9 già dichiarava. Resta da fare, se lo si vuole, il collegamento di
  UptimeRobot o simile raccomandato da `README.md:309` — azione facoltativa, non un difetto.
- **U2 — CHIUSA: la schermata di consenso OAuth è ancora in stato "Testing".** Il passaggio a
  "In production" è stato **rimandato per decisione**, non dimenticato: da eseguire in una
  sessione successiva.
  **Conseguenza sui documenti: nessuna.** `README.md` §Gmail API, `STATO_PROGETTO.md` §6 e §12
  e `ANALISI_2026-08-31.md` descrivono tutti correttamente questo stato e lo elencano come
  backlog aperto. È uno dei punti in cui i documenti sono fedeli alla realtà: **niente da
  correggere**.
  **Conseguenza sui rilievi: `D12` sale di importanza.** Finché si resta in "Testing", il token
  Drive può davvero scadere — e l'healthcheck schedulato controlla **solo** Gmail. Il rischio
  che `D12` descriveva come teorico è quindi reale: un `DRIVE_REFRESH_TOKEN` scaduto si scopre
  solo dal fallimento del backup notturno, cioè quando il database è già senza copia di
  sicurezza recente.
- **U3 — RISPOSTA: la password MySQL NON è ancora stata ruotata.** Aperta dal 2026-06-11
  (commit `15f536d`). I documenti che la segnalano come da fare (`ROADMAP.md` P0-1 `todo`,
  `README.md:323`, `STATO_PROGETTO.md` §12 backlog) sono quindi **corretti**: niente da
  correggere lì. Resta un'azione operativa aperta — l'unico punto della roadmap storica mai
  completato, e il più vecchio dell'intera revisione.
  *Attenuante emersa in questa sessione:* la credenziale esposta in git riguardava il database
  di **sviluppo locale**; la produzione su Railway usa credenziali root separate e generate
  dalla piattaforma (`MYSQL_ROOT_PASSWORD`). Nessun documento lo dice, ed è il motivo per cui
  la cosa è stata rimandabile per tre mesi senza conseguenze: **va scritto**, altrimenti chi
  legge oggi non sa se sta guardando un rischio di produzione o no. → nuovo rilievo `D28`.
- **U4 — CONFERMATA dall'umano.** `DISCORD_OAUTH_REDIRECT_URI` inizia ora con `https://`,
  modificata nell'intervento su Railway del 2026-09-02. Coerente con la verifica del flag
  `Secure` sui cookie (STEP 6 punto 4).
- **U5 — CHIUSA, verificata direttamente via `gh` (sola lettura).**
  Il run **`33529945237`** citato in `STATO_PROGETTO.md:3` risulta
  `"conclusion": "success"`, sul commit `61d455430534e271f9f17a04447353f9efe2b264` (= `61d4554`),
  branch `master`, del 2026-09-01T16:07:48Z. **L'affermazione del documento è vera.**
  Storia completa del workflow `Test` (6 run in tutto): 4 fallimenti fra il 25/08 e il 25/08
  notte, poi **verde dal run `32913636864` del 2026-08-26T00:05Z** (commit `1732fc2`) — il che
  conferma anche `STATO_PROGETTO.md` §6 ("Verde dal 2026-08-26") e il racconto di §11.6 sui fix
  in sequenza. **Nessun run successivo a `33529945237`**, coerente con `G1`: `5c495cb` non è mai
  stato pushato, quindi non ha mai fatto girare la CI.
  *Dettaglio utile per il futuro:* GitHub Actions gira **una volta per push, sul commit di
  punta**. I 18 commit della sessione del 31/08 sono stati validati solo nel loro stato finale
  (`61d4554`), non uno per uno — normale, ma va saputo prima di dire "ogni commit è passato
  dalla CI".
- **U6 — CHIUSA: lo schema di produzione è allineato.** Query diretta sul database MySQL di
  produzione: `alembic_version` contiene **`2eac6f32b19b`**, che è esattamente la head della
  catena delle migrazioni ricostruita in §1.4. Il database di produzione corrisponde quindi allo
  schema che il codice si aspetta: nessuna colonna mancante, nessun job a rischio di fallire in
  silenzio.
- **U7 — CHIUSA: il backup notturno funziona davvero da produzione.** La cartella Drive
  contiene esclusivamente backup prodotti dal progetto Railway, non dalle prove in locale.
  Il job `controlla_e_esegui_backup_database` gira quindi come previsto e
  `DRIVE_REFRESH_TOKEN` è valido. → confluisce in `D27`.
- **U8 — già CHIUSA (vedi sopra): non c'è nulla da verificare.** La domanda era "esiste un
  monitor esterno puntato su `/health`?" e la risposta è **no**, ottenuta come effetto
  collaterale dell'indagine sul punto 2 dello STEP 6: nei log di Railway non compare nessuna
  chiamata a quell'endpoint, mentre l'endpoint stesso funziona. Non resta una verifica, resta
  semmai un'**azione facoltativa**: collegare UptimeRobot o simile, come raccomanda
  `README.md:309`. `STATO_PROGETTO.md` §9 lo dichiara già correttamente come non configurato:
  **nessuna correzione documentale necessaria**.

**Stato complessivo delle domande U:** chiuse `U1`–`U8`. Restano `U9` (link nell'email di
recensione, rimandata per mancanza di sessioni concluse) e `U10` (quante volte è stato
necessario rilanciare `reauth_gmail.py`, ancora senza risposta).

### Domanda nata dalla risposta a U2 — e sua risposta

- **U10 — CHIUSA, con esito che smentisce la documentazione.** Il `GMAIL_REFRESH_TOKEN` è
  **scaduto il 2026-09-02**, lo stesso giorno di questa verifica. È stato rinnovato con
  `scripts/reauth_gmail.py` e aggiornato sia nel `.env` locale sia su Railway.

  **Perché è importante.** L'app gira in continuo e il token viene esercitato **ogni giorno**:
  `controlla_credenziali_gmail` chiama `users.getProfile` una volta al giorno
  (`GMAIL_HEALTHCHECK_INTERVAL_HOURS=24`), e ogni prenotazione manda due email. Non c'è mai
  stata una finestra di 7 giorni di inattività — eppure il token è scaduto lo stesso. La
  formulazione **"scade dopo 7 giorni di inattività"**, ripetuta in quattro punti del progetto,
  **non descrive il comportamento osservato**. → nuovo rilievo `D29`.

  **Conseguenza su `U2`:** il rinvio del passaggio a "In production" era stato deciso sulla
  base di quella formulazione. Se la scadenza non dipende dall'uso, la mitigazione attuale non
  è una rete di sicurezza ma un promemoria ricorrente a tempo indeterminato — e pubblicare la
  schermata di consenso smette di essere una pulizia opzionale per diventare **il fix vero**.
  La decisione resta dell'umano, ma il presupposto su cui era stata presa non regge più.

  **Nota positiva, da registrare:** l'alert Discord ha funzionato come progettato. Il problema è
  stato scoperto dal sistema, non da un cliente che non riceveva l'email — che è esattamente lo
  scopo per cui `controlla_credenziali_gmail` era stato scritto.

  **Esclusa una correlazione con l'intervento di oggi:** le modifiche Railway del 2026-09-02
  non possono aver causato la scadenza. `GMAIL_REFRESH_TOKEN` era un valore **letterale sul
  servizio app** e non è mai stato toccato; lo STEP 4 ha rimosso soltanto la copia divergente e
  non referenziata che stava sul servizio MySQL (`P8`). Va detto esplicitamente perché
  "si è rotto subito dopo che abbiamo cambiato le variabili" è il tipo di coincidenza che
  fuorvia le indagini future.

### Domande nate dalla risposta a U10 — entrambe chiuse
- **U11 — CHIUSA: il `DRIVE_REFRESH_TOKEN` è valido.** Il backup su Drive continua a
  funzionare. **È però la prova che smonta anche la spiegazione alternativa**: emesso intorno
  al 25/08, ha ~8 giorni ed è vivo, quindi la scadenza non è nemmeno "7 giorni assoluti".
  Insieme al caso Gmail (`U10`) resta una sola conclusione difendibile: la regola documentata
  è sbagliata e quella vera non è determinabile da qui. → confluisce in `D29`.
  *Resta valido `D12`:* il token Drive non ha un healthcheck proattivo, quindi la prossima
  volta che scadrà — e scadrà — lo si scoprirà dall'alert di backup fallito delle 04:00, non
  prima.
- **U12 — CHIUSA: nessuna prenotazione nella finestra buia.** Nessun cliente è rimasto senza
  email di conferma e nessuna notifica è andata persa. Il guasto non ha avuto conseguenze
  visibili all'esterno.

### Domande sorte dopo l'intervento del 2026-09-02
- **U9** — Alla prima sessione conclusa dopo l'intervento, l'email di richiesta recensione
  contiene un link cliccabile che inizia con `https://`? *(Verifica finale di `P2`: al momento
  non ci sono ancora prenotazioni concluse su cui provarlo.)*

---

# FASE 5 — CORREZIONI APPROVATE, DA APPLICARE

> **✅ APPROVAZIONE COMPLETATA il 2026-09-02.** Tutte e 29 le voci `D1`–`D29` sono state
> approvate voce per voce. Nessuna è stata respinta; due sono state modificate rispetto alla
> proposta iniziale (`D13` opzione (a), `D15` correzione documentale invece che al codice) e
> una è stata corretta nel merito dall'umano (`D29`, la regola dei 7 giorni).
>
> **✅ APPLICATE il 2026-09-02 (terza sessione).** Tutte le voci qui sotto sono state scritte
> nei documenti, insieme a `D30` e `D31` nate dopo. Tre note su cosa è cambiato rispetto al
> testo congelato:
> - **`D1` riscritta**, come previsto dall'"Impatto sulle correzioni congelate": dopo il fix
>   `R1` l'avvertenza non serviva più, perché l'affermazione originale del README era diventata
>   vera. Applicata la versione breve.
> - **`D13` non applicata qui**: era già stata chiusa nella seconda sessione (commit `886b10b`).
> - **`D29` applicata solo dove serviva davvero**: elencava anche `.env.example`, ma quel file
>   **non conteneva** l'affermazione sbagliata sulla scadenza del token (l'unica occorrenza di
>   "inattività" lì riguarda `RETENTION_MONTHS`, ed è corretta). La voce citava un file di
>   troppo.
>
> Il testo qui sotto resta **quello approvato**, non riscritto a posteriori: serve a poter
> confrontare ciò che era stato deciso con ciò che è stato scritto.
> Le voci sono elencate nell'ordine in cui sono state approvate, non in ordine numerico:
> cerca per identificatore.
>
> Le correzioni qui sotto sono approvate ma **NON applicate**. Il motivo è deliberato: la
> sessione 2 modificherà il codice (a partire dai ritrovamenti `R1`–`R16`) e renderà obsoleta
> una parte di queste correzioni; scriverle ora significherebbe riscriverle dopo.
> **I documenti restano temporaneamente disallineati: è una condizione nota e voluta, non una
> dimenticanza.**

## ✅ D1 — `README.md:252` (tabella "Comandi disponibili")

**Testo attuale:**
> \| `pytest` \| Esegue la suite di test automatici (`tests/`) — usa un database SQLite in
> memoria, non tocca mai il MySQL di sviluppo o produzione \|

**Testo nuovo:**
> \| `pytest` \| Esegue la suite di test. I *test* girano su SQLite in memoria, ma l'import di
> `backend.main` esegue `run_migrations()` sulla `DATABASE_URL` dell'ambiente: **lancialo
> sempre con `DATABASE_URL` e `JWT_SECRET` fittizie**, come fa la CI, altrimenti tocca il
> database di sviluppo reale e può inviare un alert Discord. Vedi
> `.github/workflows/tests.yml`. \|

**Modifica collegata:** in `.github/workflows/tests.yml`, il commento allo step "Esegui i
test" afferma che la `DATABASE_URL` fittizia è «mai usata per davvero». Va corretto: è usata
da `run_migrations()` all'import.

> ⚠️ Il fix strutturale è `R1` (spostare `run_migrations()` fuori dall'import-time) ed è
> materiale per la **sessione 2**. Se `R1` viene applicato, questa correzione documentale
> **va riscritta di conseguenza**: sarebbe il primo caso in cui il codice raggiunge il
> documento invece del contrario.

## ✅ D2 — `ANALYSIS.md` e `ROADMAP.md` (intestazioni)

Il contenuto dei due file **non va toccato**: sono storici per costruzione. Si aggiunge solo
un cartello.

**Da inserire come primo blocco citato**, subito sotto il titolo `#`, in **entrambi** i file:

> ⚠️ **DOCUMENTO STORICO — non descrive lo stato attuale.** Fotografa il progetto al `<DATA>`.
> Quasi tutto ciò che segue è stato superato: per lo stato di oggi vedi `STATO_PROGETTO.md`.
> Conservato come memoria delle decisioni prese allora, **non va aggiornato**.

- in `ANALYSIS.md`, `<DATA>` = **2026-08-06** (ricavata da §5, "Decisioni prese con l'utente");
- in `ROADMAP.md`, `<DATA>` = **2026-08-06 → 2026-08-21** (periodo coperto dagli step P0–P3
  secondo il git log; il file non contiene alcuna data propria).

**In `ROADMAP.md`** va inoltre neutralizzata la riga 3, che lo fa sembrare un piano vivo:
"Stato aggiornabile a `in corso` / `fatto` man mano che si procede" → *"Lo stato di ogni step
è quello registrato alla chiusura di quella sessione."*

## ✅ D3 — `ANALISI_2026-08-31.md` (sotto la riga della data, riga 2)

Contenuto **non da allineare**: è il verbale di cosa quella review trovò quel giorno.

**Da aggiungere:**
> ✅ **Findings chiusi.** Tutte le criticità di questo referto sono state corrette nella
> sessione 31/08–01/09 (vedi `STATO_PROGETTO.md` §12 per l'elenco commit per commit). Questo
> file resta il verbale di **cosa la review trovò quel giorno**, non lo stato attuale: non va
> aggiornato.

## ✅ D4 — `STATO_PROGETTO.md:3` (intestazione)

**Testo attuale (frammento):** "…**aggiornato al commit `1732fc2`, 2026-08-31**, dopo la
sessione di conformità GDPR…"

**Testo nuovo (frammento):** "…**aggiornato al 2026-09-02**, dopo la sessione di conformità
GDPR…"

Motivo del cambio di criterio: `1732fc2` è del **2026-08-26**, non del 31/08, e inseguire
l'hash a ogni modifica ha già prodotto due disallineamenti. La data basta; gli hash li tiene
`git log`.

**Da tenere invariata** la frase sulla CI: verificata il 2026-09-02 con `gh`, il run
`33529945237` è davvero `success` sul commit `61d4554`. È corretta.

> ⚠️ **Ordine di applicazione:** questa voce va scritta **dopo** il push di fine sessione,
> altrimenti nasce già disallineata (oggi `5c495cb` non è ancora su `origin/master`).

## ✅ D5 — `.env.example` + `STATO_PROGETTO.md:14` e `:312`

**Tre modifiche, in quest'ordine.**

**1. `.env.example`, righe 4-5 — rimuovere il blocco:**
> \# Chiave segreta generica (non più usata direttamente, ma tenuta per compatibilità).
> `SECRET_KEY=change-me-to-a-random-secret`

Nessuna riga del progetto la legge (`grep 'getenv("SECRET_KEY")'` → zero risultati). Non
esiste nessuna "compatibilità" da mantenere. Da rimuovere **anche da Railway** — già fatto il
2026-09-02, vedi `P6`.

**2. `.env.example` — aggiungere, al posto del blocco rimosso:**
> \# Livello minimo dei messaggi di log (INFO/DEBUG/WARNING). Alzalo a DEBUG solo durante
> \# un'indagine su un problema: in esercizio normale INFO è quello giusto.
> `LOG_LEVEL=INFO`

**3. `STATO_PROGETTO.md`, righe 14 e 312** — le affermazioni "allineato al codice attuale" e
"verificato allineato al codice il 2026-08-31" vanno **ri-datate al 2026-09-02**, ma **solo
dopo** aver eseguito i punti 1 e 2. Applicarle prima ricreerebbe lo stesso difetto.

**Coordinare con `D21`** (§12.4 afferma che `SECRET_KEY` è stata "rimossa", mentre lo era solo
dal README): le due voci descrivono lo stesso disallineamento da due angoli diversi e vanno
applicate insieme.

## ✅ D6 — `STATO_PROGETTO.md:375` e `:460` (coverage)

**Due punti, stessa correzione.**

| Riga | Testo attuale | Testo nuovo |
|---|---|---|
| `:375` (§9) | "…riconfermata dalla CI il 2026-09-01 (coverage **78%**)" | "…riconfermata dalla CI il 2026-09-01 (coverage **80%**)" |
| `:460` (§12.3) | "Suite: 54 → **82 test**, coverage 67% → **78%**" | "Suite: 54 → **82 test**, coverage 67% → **80%**" |

**Misura di riferimento:** `1714` statement, `351` non coperti, `82 passed`, eseguito due volte
con il comando della CI (`DATABASE_URL="sqlite:///:memory:"`, `JWT_SECRET="test-secret"`).
Nessun commit dopo `2114b73` tocca il codice, quindi il valore era già 80% quando è stato
scritto 78%.

> ⚠️ Se la sessione 2 aggiunge o rimuove test, **questo numero va rimisurato prima di
> scriverlo**, non ricopiato da qui.

## ✅ D7 — `README.md`, tabella "Variabili d'ambiente"

**Da aggiungere** (posizione naturale: dopo `FRONTEND_ORIGINS`, fra le variabili generali):
> \| `LOG_LEVEL` \| No \| Livello minimo dei messaggi di log (default `INFO`). Portalo a
> `DEBUG` solo per un'indagine. \|

Con questa riga la tabella copre **tutte e 32** le variabili lette dal codice (elenco in §1.6
di questo referto). La parte `.env.example` della stessa lacuna è già coperta da `D5`.

## ✅ D8 — `README.md:100`

**Testo attuale:**
> `timezone_service.py` — un'unica funzione (`utc_to_rome`) che converte un orario UTC
> nell'ora italiana, usata ovunque serva mostrare un orario al coach.

**Testo nuovo:**
> `timezone_service.py` — le conversioni e i confronti di orario condivisi da tutto il
> progetto: `utc_to_rome()` (UTC → ora italiana, per la visualizzazione),
> `formatta_data_ora_rome()`, `ora_utc_naive()` ("adesso" nella stessa forma salvata nel
> database) e `intervalli_si_sovrappongono()`.

Le tre funzioni oltre a `utc_to_rome` sono state estratte nella sessione del 31/08 perché
ripetute in una dozzina di punti. `STATO_PROGETTO.md:76` le elencava già correttamente: era
una contraddizione fra due documenti attuali.

## ✅ D9 — `README.md:68`, `:139`, `:155`

**Riga 68 — testo attuale:**
> `scheduler.py` — Contiene il "lavoratore in background" che ogni tot minuti controlla se ci
> sono prenotazioni imminenti a cui inviare un promemoria via email/Discord.

**Riga 68 — testo nuovo:**
> `scheduler.py` — gli **8 lavori automatici in background** che girano senza che nessuno li
> chieda: promemoria pre-sessione, richieste di recensione, sync col Google Calendar,
> generazione notturna degli slot dalle regole ricorrenti, controllo del token Gmail,
> anonimizzazione GDPR dei clienti inattivi, pulizia degli slot passati, backup del database
> su Drive.

**Righe 139 e 155:** togliere "dei promemoria" — "Avvia lo scheduler ~~dei promemoria~~ in
background (`avvia_scheduler()`)". Al punto 8 della riga 155, sostituire "controlla
periodicamente se questa prenotazione si avvicina, e se sì manda un promemoria" con una
formulazione che non lasci intendere che sia l'unico compito.

Perché conta: chi legge solo il README crede che toccare lo scheduler riguardi le sole email
di promemoria, mentre lì dentro girano anche il **backup del database** e la **retention
GDPR**.

## ✅ D10 — `README.md:160`

**Testo attuale:** "**`backend/routers/admin.py`** verifica le credenziali (`auth_service.py`)
e restituisce un **token JWT**…"

**Testo nuovo:** "**`backend/routers/admin/__init__.py`** verifica le credenziali
(`auth_service.py`) e restituisce un **token JWT**…"

Quel file non esiste dal commit `f48fd22` (split del package). Il README si contraddiceva da
solo: a riga 110 dice già correttamente "È un package, non un singolo file".

## ✅ D11 — `README.md:150`

**Testo attuale (frammento):** "…Quella funzione chiede al database (tramite il model `Slot`)
**tutti gli slot con `is_available=True`**, e li restituisce come JSON…"

**Testo nuovo (frammento):** "…Quella funzione chiede al database (tramite il model `Slot`)
**tutti gli slot ancora liberi (`is_available=True`) e non ancora passati**, e li restituisce
come JSON…"

Il filtro sugli orari passati esiste dal commit `3260848` (19/08) e non era mai stato recepito
dal README. `STATO_PROGETTO.md:234` lo descriveva già correttamente.

## ✅ D12 — `README.md:288`

**Testo attuale:** "Lo stesso controllo di salute pensato per Gmail (refresh token che scade
dopo 7 giorni di inattività finché la schermata di consenso resta in "Testing") si applica
anche a questo token — vedi il box di attenzione nella sezione Gmail API sopra: portare la
schermata a "In production" risolve per entrambi insieme."

**Testo nuovo:** "La stessa **scadenza** vale anche per questo token. Attenzione però:
l'healthcheck schedulato controlla **solo** `GMAIL_REFRESH_TOKEN` — un `DRIVE_REFRESH_TOKEN`
scaduto si scopre dall'alert Discord del backup notturno fallito, non prima. Portare la
schermata di consenso a "In production" risolve per entrambi insieme."

**Coordinare con `D29`**, che riscrive la descrizione della scadenza in tutti i punti in cui
compare: il frammento "dopo 7 giorni di inattività" va rimosso anche qui.

> Questa voce è **salita di importanza** durante la sessione: `U2` ha confermato che la
> schermata resta in "Testing" e `U10` che i token scadono davvero (il token Gmail è scaduto
> il 2026-09-02). Il rischio che descriveva non è più teorico.

## ✅ D13 — 6 rimandi da codice e test → opzione (a) approvata

Riscrivere i rimandi citando l'**Area** di `ANALISI_2026-08-31.md` invece del "Blocco", che in
quel documento non esiste. Scartata l'opzione (b) — aggiungere una tabella di corrispondenza al
documento storico — per non toccare un file storico.

| File e riga | Testo attuale | Testo nuovo |
|---|---|---|
| `backend/routers/admin/dashboard.py:122` | `ANALISI_2026-08-31.md (Blocco B2)` | `ANALISI_2026-08-31.md (Area Dati)` |
| `tests/test_admin.py:112` | `ANALISI_2026-08-31.md, Blocco B2` | `ANALISI_2026-08-31.md, Area Dati` |
| `tests/test_admin.py:161` | `ANALISI_2026-08-31.md, Blocco C3` | `ANALISI_2026-08-31.md, Area Test` |
| `tests/test_admin.py:226` | `ANALISI_2026-08-31.md, Blocco D4` | `ANALISI_2026-08-31.md, Area Back-end` |
| `tests/test_admin.py:280` | `ANALISI_2026-08-31.md, Blocco D4` | `ANALISI_2026-08-31.md, Area Sicurezza` |
| `tests/test_booking.py:433` | `ANALISI_2026-08-31.md, Blocco B1` | `ANALISI_2026-08-31.md, Area Back-end` |

*Criterio della mappatura:* B1/B2 → le criticità su `note_admin` e sulla query analytics non
filtrata, che in ANALISI stanno rispettivamente in "Back-end: API, dominio, gestione errori,
validazione input" e "Dati: schema, query, indici, transazioni, migrazioni, N+1"; C3 → il debito
di test su `/admin/analytics`, in "Test: cosa è coperto davvero"; D4 → i query param di
`aggiorna_stato`/`aggiorna_note`, trattati sia in "Back-end" (validazione) sia in "Sicurezza"
(finiscono nei log di accesso) — da qui la scelta di aree diverse per le due righe.

`tests/test_booking.py:210` cita già correttamente "Area Sicurezza/Backend": **non va toccato**.

> ⚠️ Sono modifiche a **commenti nel codice**: da eseguire nella **sessione 2**, non ora.

## ✅ D14 — `STATO_PROGETTO.md:101`

**Testo attuale:** "MySQL, **9 tabelle attive**. Nessun ORM "autogenerate": ogni migrazione in
`alembic/versions/` è scritta a mano."

**Testo nuovo:** "MySQL, **8 tabelle applicative** (più `alembic_version`, gestita da Alembic e
non dal codice dell'app). Nessun ORM "autogenerate": ogni migrazione in `alembic/versions/` è
scritta a mano."

Il §2 elencava già 8 tabelle: il numero in testa contraddiceva l'elenco sottostante.

## ✅ D15 — `STATO_PROGETTO.md` §7, nuovo punto — **scelta: correggere la documentazione**

**Decisione presa:** si documenta il comportamento attuale, **non** si cambia il codice.
Scartata quindi l'alternativa di passare `timezone=ROME_TZ` a `BackgroundScheduler()`, che
sarebbe stata materia di sessione 2.

**Da aggiungere come nuovo punto numerato in §7:**
> **I job cron usano il fuso del processo, non Europe/Rome.** `BackgroundScheduler()` è
> costruito senza `timezone=`, quindi gli orari dei job notturni (03:00, 03:01, 03:02, 04:00)
> sono ore locali del processo. Su Railway il processo gira in UTC: il backup "delle 04:00"
> parte in realtà alle 06:00 italiane d'estate e alle 05:00 d'inverno. In locale sono davvero
> le 03:00/04:00 italiane. Nessun impatto pratico — restano ore a basso traffico — ma va
> saputo prima di leggere un log o di aspettarsi un file a un'ora precisa.

**Modifica collegata:** il commento in `backend/scheduler.py:379-383` parla di "ogni notte alle
03:00, un momento a basso traffico" senza dire in quale fuso. Sarebbe coerente aggiungerci un
inciso — ma è un commento nel codice, quindi **sessione 2**.

## ✅ D27 — `STATO_PROGETTO.md:382` (§9), `:407` (§11), `:491-492` (§12)

**Spostare in "Verificato"** i quattro punti chiusi il 2026-09-02, con la data e il rimando a
`RAILWAY_RIALLINEAMENTO_2026-09-02.md`:

1. Login Discord studente end-to-end in produzione col cookie httpOnly → **verificato,
   funziona**. Da annotare esplicitamente che *non poteva* funzionare prima (mancavano
   `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` su entrambi i servizi Railway), altrimenti
   sembra che fosse sempre stato a posto e solo mai provato.
2. Conferma del flusso cookie httpOnly → **verificato**: flag `Secure` e `HttpOnly` controllati
   da DevTools dopo il passaggio di `DISCORD_OAUTH_REDIRECT_URI` a `https://`.
3. "Verificare che le variabili d'ambiente reali su Railway riflettano `.env.example`" (backlog
   §12) → **fatto**: esaminati entrambi i servizi, trovate 9 variabili assenti e 5 morte, poi
   corrette.
4. "Che il cron di backup notturno (04:00) abbia davvero prodotto un file da produzione" →
   **verificato**: la cartella Drive contiene esclusivamente backup prodotti dal progetto
   Railway.

**Da lasciare dov'è**, perché ancora vero: l'uptime monitor esterno su `/health` non è
configurato (confermato: nessuna chiamata nei log). È l'unica voce superstite della lista.

**Da aggiungere** allo stesso §9, fra i verificati: lo schema di produzione è alla head
`2eac6f32b19b` (`U6`).

## ✅ D28 — `ROADMAP.md:15-20`, `README.md:323`, `STATO_PROGETTO.md:488-490`

**Da aggiungere in tutti e tre i punti**, adattando la formulazione al contesto:
> Riguarda il database di **sviluppo locale**. La produzione su Railway usa credenziali
> separate, generate dalla piattaforma (`MYSQL_ROOT_PASSWORD` sul servizio MySQL) e mai finite
> in git.

Senza questa riga chi legge non sa se sta guardando un'esposizione di produzione aperta da tre
mesi, ed è verosimilmente il motivo per cui il punto è stato rimandato tante volte senza che
nessuno stabilisse quanto fosse urgente.

**La rotazione resta comunque da fare:** `U3` è ancora aperta. La precisazione cambia la
priorità, non l'esistenza del compito.

## ✅ D29 — `README.md:267`, `STATO_PROGETTO.md:331`, `.env.example`, `email_service.py:141-143`

**Regola stabilita dall'umano:** i refresh token Google in stato "Testing" scadono dopo
**7 giorni**, punto — **non** dopo 7 giorni *di inattività*.

> **Correzione a un'ipotesi mia, registrata perché non induca in errore chi legge:** avevo
> proposto di non dichiarare nessuna regola, sostenendo che il token Drive (che ritenevo
> vecchio di ~8 giorni ed era ancora valido) smentisse anche la scadenza fissa a 7 giorni.
> Quella data di emissione era una **mia deduzione dai commit**, mai verificata: non regge
> come controprova. La regola dei 7 giorni resta quella corretta.

**Testo nuovo (da adattare a ciascun punto):**
> Finché la schermata di consenso OAuth resta in stato **"Testing"**, i refresh token Google
> scadono dopo **7 giorni**, indipendentemente dall'uso che se ne fa. Verificato in produzione
> il 2026-09-02: il `GMAIL_REFRESH_TOKEN` è scaduto pur essendo esercitato ogni giorno
> dall'healthcheck e dalle email di prenotazione. L'healthcheck schedulato **rileva** la
> scadenza, non la previene: l'unico rimedio che la elimina è portare la schermata a
> **"In production"**.

**Stato del token Drive al 2026-09-02, da registrare in `STATO_PROGETTO.md` §6:** ancora
valido, ma prossimo alla scadenza. **Attenzione a come si legge l'assenza di notifiche
Discord:** non esiste nessun healthcheck sul token Drive (`D12`), quindi il silenzio su Discord
**non è** una conferma che sia sano. L'unico segnale è l'alert di *fallimento* del backup delle
04:00 — che, essendo assente finora, dice soltanto che il token era valido **all'ultima
esecuzione notturna**, non che lo sia adesso.

**Azione consigliata (operativa, non documentale):** rilanciare `scripts/reauth_drive.py`
preventivamente, invece di aspettare l'alert a copia di sicurezza già saltata. È anche
l'argomento più forte a favore di `U2`: pubblicare la schermata di consenso chiude entrambi i
token in una volta ed elimina il lavoro manuale ricorrente.

> ⚠️ La parte in `backend/services/email_service.py:141-143` è un **commento nel codice**:
> **sessione 2**.

## ✅ D16 — `README.md:74-80`, `:90`, `:96-101`, `:107-111`

**Completare i quattro inventari.** Voci da aggiungere, nello stile didattico delle esistenti:

**`backend/models/` (mancano 2 su 8):**
- `package.py` → tabella `packages`: i pacchetti di sessioni pre-pagati assegnati a un cliente.
- `review.py` → tabella `reviews`: voto e commento lasciati dal cliente dopo una sessione.

**`backend/schemas/` (mancano 4 su 9):** aggiungere `package.py`, `review.py`, `consulenza.py`,
`pacchetto_richiesta.py` all'elenco della riga 90.

**`backend/services/` (mancano 6 su 12):**
- `retention_service.py` — anonimizza i clienti inattivi da troppo tempo (GDPR).
- `backup_service.py` — genera il dump SQL del database e lo carica su Google Drive.
- `google_oauth_service.py` — le credenziali OAuth condivise da Gmail e Drive, con cache.
- `package_service.py` — il catalogo fisso dei pacchetti (`CATALOGO_PACCHETTI`).
- `booking_service.py` — libera slot ed evento calendario quando una prenotazione è cancellata.
- `pagination_service.py` — sanifica `pagina`/`per_pagina` e costruisce l'envelope condiviso
  dalle liste admin.

**`backend/routers/` (mancano 2 su 7):**
- `consulenza.py` → `/consulenze` (richiesta di call conoscitiva gratuita, non crea slot né
  prenotazioni).
- `pacchetti_richieste.py` → `/pacchetti-richieste` (richiesta di attivazione pacchetto: manda
  solo i contatti al coach, non crea il pacchetto).

## ✅ D17 — `README.md:119-122`

**Testo attuale:** "Nessun framework: HTML, CSS e JavaScript "vanilla" […] Ci sono **due pagine
web completamente separate**:" seguito dai due punti elenco su `index.html` e `admin.html`.

**Testo nuovo:** "Nessun framework: HTML, CSS e JavaScript "vanilla" […] **Ci sono cinque
pagine.** `index.html` (form di prenotazione) e `admin.html` (pannello) sono le due principali
e completamente separate; `about.html` (con la vetrina delle recensioni approvate),
`privacy.html` e `recensione.html` (pagina pubblica raggiunta dal link ricevuto via email dopo
la sessione) sono più semplici."

Mantenere i due punti elenco esistenti e aggiungerne uno per le tre pagine minori.

## ✅ D18 — `README.md:153`

**Testo attuale (frammento):** "…e si mandano tre notifiche **in parallelo**: email al cliente,
email al coach (`email_service.py`), messaggio Discord (`discord_service.py`)."

**Testo nuovo (frammento):** "…e si mandano tre notifiche, **una dopo l'altra e dopo** che la
prenotazione è già salvata: email al cliente, email al coach (`email_service.py`), messaggio
Discord (`discord_service.py`). Se una fallisce, la prenotazione resta valida lo stesso."

Nessuna concorrenza: `backend/routers/booking.py:305-331` le chiama in sequenza, sincrone.

## ✅ D19 — `STATO_PROGETTO.md:205`

**Testo attuale:** "Le prime 12 sono descritte in dettaglio nella versione precedente di questo
documento (crea tabelle iniziali → discord_id). Aggiunte dopo il 19/08:" seguito dal blocco con
8 revisioni.

**Testo nuovo:** eliminare il rimando e riportare la **catena completa a 18 voci**:

```
1972ef07e768  crea tabelle iniziali (slots, users, bookings, payments)   [base]
  -> a4568987d2e7  aggiungi calendar_event_id a bookings
  -> d1af2a35c949  rimuovi tabella payments
  -> 98489ff817ea  aggiungi service_type a bookings
  -> 37a82dbead86  aggiungi discord_tag a users
  -> f56a5f50b503  aggiungi blocked_external a slots
  -> dcfea9cf2bb0  aggiungi vod_link, replay_code a bookings
  -> 60a355bf4f97  aggiungi reminder_sent a bookings
  -> cc755d0d6a6b  crea tabella client_notes
  -> 17c843945785  regole ricorrenti, blocchi eccezionali, blocked_admin
  -> 0bfc529cd9fd  aggiungi discord_id a users (+ unique)
  -> a1c92f7e4b18  categoria al posto di showdown_username su users
  -> b3d84a19e6f2  crea tabella packages + package_id su bookings
  -> c5f612a8d9e3  crea tabella reviews + review_token/review_email_sent su bookings
  -> d4a72e0f8b31  aggiungi slot_id_secondario a bookings
  -> a1b2c3d4e5f6  aggiungi approvata a reviews
  -> 215aa000de4b  indici su slots.start_time e bookings.status
  -> 2eac6f32b19b  aggiungi anonimizzato_at a users                       [HEAD]
```

Le revisioni fino a `0bfc529cd9fd` incluse sono **11**, non 12 come scritto. Riportando la
catena intera il documento torna autosufficiente come dichiara di essere a riga 3.

## ✅ D20 — `STATO_PROGETTO.md:342` (§7)

**Testo attuale:** "Tutti i punti della versione precedente di questo documento restano validi
(fusi orari UTC naive, claim atomico via UPDATE condizionale, migrazioni automatiche non
bloccanti, SMTP diretto bloccato su Railway, ecc.). Aggiunte rilevanti dopo il 19/08:"

**Testo nuovo:** eliminare il rimando ed espandere i punti ereditati in voci vere. Bozze
pronte, da rifinire in fase di scrittura:

1. **Tutti i datetime nel database sono UTC "naive"** — salvati senza fuso, ma da leggere
   sempre come UTC. La conversione da/verso Europe/Rome avviene solo ai bordi: in ingresso nel
   validator di `SlotCreate`, in uscita in `SlotResponse` e nei service che formattano per il
   coach (`timezone_service.py`). Mai nel mezzo.
2. **Il claim dello slot è atomico**, non "leggi e poi scrivi": un `UPDATE slots SET
   is_available=0 WHERE id=? AND is_available=1` con controllo di `rowcount`. Deliberatamente
   **nessun vincolo UNIQUE** a schema, perché incompatibile col flusso cancella/riprenota (uno
   slot cancellato torna prenotabile).
3. **Le migrazioni girano a ogni avvio e non bloccano il boot**: `run_migrations()` è dentro un
   `try/except` che, se fallisce, lascia partire l'app registrando l'errore e mandando un alert
   Discord. Scelta deliberata: un deploy con migrazione fallita si nota subito, invece che al
   primo cliente che usa la funzione nuova.
4. **SMTP diretto è bloccato dalla rete di Railway** (`OSError: Network is unreachable`): le
   email passano dall'API Gmail via HTTPS con OAuth2, non da una password SMTP.

## ✅ D21 — `STATO_PROGETTO.md:461-463` (§12.4)

**Testo attuale (frammento):** "rimossa `SECRET_KEY` (var d'ambiente mai letta, documentata per
errore in README)"

**Testo nuovo (frammento):** "rimossa `SECRET_KEY` da README, `.env.example` e Railway (var
d'ambiente mai letta da nessuna riga di codice)"

La formulazione originale faceva credere che la pulizia fosse completa: era avvenuta solo nel
README, ed è il motivo per cui la variabile è rimasta in `.env.example` e su Railway fino al
2026-09-02.

> ⚠️ **Da applicare insieme a `D5`**, e solo dopo che `.env.example` è stato effettivamente
> ripulito: altrimenti si sostituisce un'affermazione ottimista con un'altra.

## ✅ D22 — `README.md:180`

**Testo attuale:** "Serve Python 3.11+ e un server MySQL raggiungibile (locale o remoto)."

**Testo nuovo:** "Serve **Python 3.11** (la stessa versione di produzione e CI — vedi
`nixpacks.toml`; una versione diversa fa girare i test su un interprete diverso da quello
reale) e un server MySQL raggiungibile (locale o remoto)."

`STATO_PROGETTO.md` §12.0 racconta che il venv è stato ricreato apposta perché era su Python
3.14 — che soddisfa "3.11+". Il README autorizzava esattamente la configurazione poi trattata
come un problema.

## ✅ D23 — `STATO_PROGETTO.md:221-229` (tabella Pagine/static)

**Riga da aggiungere alla tabella:**
> \| GET \| `/docs`, `/redoc`, `/openapi.json` \| no \| documentazione API generata
> automaticamente da FastAPI, **pubblica**: espone lo schema di tutti gli endpoint, admin
> compresi (non i dati). Scelta consapevole; disattivabile con `docs_url=None` in
> `backend/main.py` se un domani non la si vuole più \|

Non è una vulnerabilità — gli endpoint restano protetti da `get_admin`/`get_studente` — ma è
una superficie pubblica che nessun documento nominava.

## ✅ D24 — `STATO_PROGETTO.md:266`

**Testo attuale:** "\| GET \| `/admin/dashboard` \| numeri chiave + prossimi slot liberi \|"

**Testo nuovo:** "\| GET \| `/admin/dashboard` \| numeri chiave + prossimi slot liberi. Nota:
`media_voto_recensioni` è calcolata su **tutte** le recensioni ricevute, anche quelle non
ancora approvate — è un dato interno per il coach, diverso da quello che il pubblico vede in
`about.html` \|"

`backend/routers/admin/dashboard.py:66` usa `func.avg(Review.voto)` senza filtro su
`approvata`, mentre la vetrina pubblica filtra. I due numeri non coincidono e nulla lo diceva.

## ✅ D25 — `README.md:224` (tabella variabili)

**Spezzare la riga** che oggi raggruppa `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` /
`DISCORD_OAUTH_REDIRECT_URI` sotto un unico "Obbligatoria: No (per il login Discord)", e per
`DISCORD_OAUTH_REDIRECT_URI` aggiungere:

> In produzione **deve** iniziare con `https://`: da questo l'app deduce di essere in
> produzione e marca `Secure` i cookie di sessione (Railway termina l'HTTPS a monte, quindi non
> è deducibile dalla richiesta). Deve inoltre coincidere carattere per carattere con il
> redirect URI configurato sul Discord Developer Portal.

**Costo dimostrato in questa sessione:** la variabile era `http://` e i cookie di produzione
uscivano senza `Secure` (`P4`), per settimane, senza che nessun documento segnalasse il legame.

## ✅ D26 — regola generale sui rimandi, non una correzione a un file

**Nessuna modifica a `ANALISI_2026-08-31.md`:** i suoi rimandi per numero di riga fotografano
lo stato di allora ed è un documento storico.

**Regola approvata, da annotare in `STATO_PROGETTO.md` §7:**
> **Non citare i markdown per numero di riga.** I riferimenti tipo `README.md:217` si rompono
> nel giro di giorni: di due citati in `ANALISI_2026-08-31.md`, entrambi puntano oggi a
> tutt'altro contenuto, e altri otto sono sfalsati di 1-6 righe. Citare invece il titolo di
> sezione (`§7.7`, "Area Sicurezza"), che sopravvive alle riscritture. Vale sia per i rimandi
> fra documenti sia per i commenti nel codice.

### ❓ Decisione aperta, sollevata dall'umano: eliminare `ANALISI_2026-08-31.md`?

L'idea: se un documento datato crea comunque confusione, tanto vale cancellarlo invece di
metterci un cartello.

**Raccomandazione: tenerlo.** Motivi concreti, non di principio:
- `D3` (già approvata) mette in testa al file la dichiarazione che i findings sono chiusi:
  il rischio di scambiarlo per attuale è già risolto, che è il problema per cui si valutava di
  eliminarlo;
- **sei commenti in codice e test lo citano per nome** (`dashboard.py:122`,
  `test_admin.py:112/161/226/280`, `test_booking.py:433`), e `D13` li riscrive perché puntino
  alle sue *Aree*: eliminarlo li lascerebbe orfani tutti;
- `STATO_PROGETTO.md` §12 vi rimanda esplicitamente per il dettaglio della sessione 31/08;
- contiene il **perché** di una decina di scelte difensive nel codice, che `git log` non
  conserva a quel livello di dettaglio.

Cancellandolo il contenuto resterebbe comunque nella storia git, ma diventerebbe
irrecuperabile in pratica: bisognerebbe sapere che è esistito per andarlo a cercare.

**Se invece si decidesse di eliminarlo**, andrebbe fatto *insieme* a: rimozione dei 6 rimandi
nel codice (non la riscrittura di `D13`), e sostituzione del rimando in `STATO_PROGETTO.md`
§12 con un riassunto autosufficiente. **Non è una cancellazione a costo zero.**

*Decisione rimandata: non è stata presa in questa sessione.*

---

# FASE 6 — SESSIONE 2: DEBUGGING E PULIZIA DEL CODICE (2026-09-02)

> Seconda delle tre sessioni. Lavora sui ritrovamenti `R1`–`R16` della Fase 1b e sulle parti
> delle correzioni congelate che toccano commenti nel codice. **La sezione "Fase 5 — Correzioni
> approvate" non viene modificata in questa sessione**: le sue voci si applicano nella terza.

## Nota operativa: permessi del progetto

`.claude/settings.local.json` conteneva un blocco `deny` con `Edit(backend/**)`,
`Edit(frontend/**)`, `Edit(tests/**)` e `Bash(git push:*)` — il paletto che ha reso la sessione 1
di sola analisi, e che ha funzionato. Su autorizzazione esplicita dell'umano sono stati rimossi
i divieti su `backend/**` e `tests/**`, **mantenendo** quelli su `frontend/**` (nessuna voce
approvata lo tocca) e su `git push` (push e deploy restano all'umano).

## Classificazione dei ritrovamenti

| Categoria | Voci |
|---|---|
| 🔴 BUG | `V1` (= `R1` + `R17`) |
| 🟠 RISCHIO | `V2` (= `R14`) — *in attesa di decisione di prodotto* |
| ⚪ MORTO | `V3` (= `R11`), `V4` (= `R12`), `V5` (= `R10`) — *in attesa di decisione* |
| 🟡 RUMORE | `V6`–`V13` (= `R3`, `R4`, `R5`, `R7`, e le parti in codice di `D13`, `D15`, `D29`, `D1`) |
| ⛔ NON TOCCARE | `R2`, `R6`, `R8`, `R9`, `R13`, `R15`, `R16` |

**Motivazioni dei NON TOCCARE** (registrate perché sapere cosa si è deciso di lasciare stare
vale quanto il resto): `R2` `/docs` pubblici — gli endpoint restano protetti, ed è già coperto
da `D23` come scelta da dichiarare; `R6` `.env.example` — è la parte operativa di `D5`,
congelata, spetta alla sessione 3; `R8` media voto sulle non approvate — difendibile come
numero interno, coperto da `D24`; `R9` `categoria` non anonimizzata — non è un identificativo;
`R13` fuso dei job cron — l'umano ha già deciso in sessione 1 di documentarlo, non di cambiarlo;
`R15` `EMAIL_APP_PASSWORD` — sta nel `.env` locale, che non è in git; `R16` wrapper negli
script — refactor cosmetico che i vincoli del progetto scoraggiano.

## Ritrovamento nuovo, emerso in questa sessione

### R17 — `avvia_scheduler()` è chiamato a livello di modulo
**Gravità: alta.** Stessa causa di `R1` e non annotata in sessione 1: `backend/main.py:219`
chiamava `avvia_scheduler()` a livello di modulo, quindi **il semplice `import backend.main`
avviava davvero il thread APScheduler** — verificato con `threading.enumerate()`, che dopo
l'import mostrava un thread di nome `APScheduler`. Durante la suite restavano quindi registrati
tutti e 8 i job, che usano il `SessionLocal` reale e non l'override dei test.

## Voci chiuse

### ✅ V1 (= `R1` + `R17`) — migrazioni e scheduler spostati nel lifespan
**Commit:** `1d2c850` — *"fix(avvio): sposta migrazioni e scheduler in un handler lifespan"*
**File toccati:** `backend/main.py`, `tests/test_avvio.py` (nuovo)

**Test prima del fix:** `tests/test_avvio.py::test_import_non_avvia_scheduler_ne_esegue_migrazioni`
falliva con `assert 'NESSUNO_SCHEDULER' in 'SCHEDULER_AVVIATO'`, e nell'output del sottoprocesso
compariva `Scheduler started`.

**Cosa è cambiato:** `run_migrations()` e `avvia_scheduler()` sono passati da livello di modulo
a un handler `lifespan` di FastAPI. Aggiunto `scheduler.shutdown()` alla chiusura — il valore
restituito da `avvia_scheduler()`, prima ignorato, ora viene usato.

**Perché il test gira in un sottoprocesso:** quando pytest arriva a `test_avvio.py`,
`backend.main` è già stato importato da `conftest.py`; l'unico modo di osservare gli effetti
dell'import è farne uno pulito in un processo nuovo. Il test azzera `DISCORD_WEBHOOK_URL`
nell'ambiente del sottoprocesso, altrimenti su una macchina con il `.env` reale avrebbe
riprodotto proprio il danno che previene.

**Verifiche:**
- suite intera: **83 passed** (82 + il nuovo test), su Python 3.11.9 del venv, con lo stesso
  comando della CI;
- **avvio reale con uvicorn**: il lifespan esegue davvero le migrazioni e registra tutti e 8 i
  job (`Scheduler started` nei log). Controllo necessario per escludere di aver "sistemato il
  test" rompendo la produzione.

**Coverage: 80% → 77%.** È l'effetto voluto, non una regressione: il codice di avvio non viene
più eseguito durante i test, quindi non risulta più coperto. Da tenere presente quando si
applicherà `D6`, che fissa il numero della coverage.

### ✅ V6–V12 — i commenti che descrivevano comportamenti inesistenti
**Commit:** `886b10b` — *"docs(codice): correggi i commenti che descrivono comportamenti
inesistenti (R3, R4, R5, R7, D13, D15, D29)"* — **un commit unico**, su richiesta dell'umano.
**File toccati:** `backend/models/availability_rule.py`, `backend/routers/admin/packages.py`,
`backend/routers/admin/availability.py`, `backend/routers/admin/dashboard.py`,
`backend/services/email_service.py`, `backend/scheduler.py`, `tests/test_admin.py`,
`tests/test_booking.py`.

**Nessuna riga eseguibile toccata:** solo commenti e docstring. 83/83 test verdi prima e dopo,
a riprova che il commit non cambia comportamento.

| Voce | Cosa diceva di falso | Cosa dice ora |
|---|---|---|
| `V6` (`R3`) | `attiva` "non viene ancora usata per filtrare nulla" | che `genera_slot_giornaliero` ci filtra davvero — più la nota che **nessun endpoint permette di cambiarla**: per sospendere una regola servirebbe intervenire a mano sul database |
| `V7` (`R4`) | rimandava a `GET /pacchetti/attivi`, inesistente | `GET /users/pacchetti-attivi` |
| `V8` (`R5`) | `Credentials.refresh()` "va rifatta ad ogni invio" | che `google_oauth_service.py` tiene le credenziali in cache e le rinnova solo alla scadenza |
| `V9` (`R7`) | uno slot con prenotazioni "viene invece disattivato" | che la richiesta viene **rifiutata con 400** e lo slot resta com'è — indicando il blocco eccezionale come strumento giusto per renderlo non prenotabile |
| `V10` (`D13`) | 6 rimandi a "Blocco B1/B2/C3/D4" di `ANALISI_2026-08-31.md` | l'**Area** corrispondente (Dati, Test, Back-end, Sicurezza), come già faceva `test_booking.py:210` |
| `V11` (`D15`) | job cron "ogni notte alle 03:00", senza dire in che fuso | che sono ore **locali del processo**: su Railway (UTC) le 03:00 sono le 05:00 italiane d'inverno, le 06:00 d'estate |
| `V12` (`D29`) | refresh token "scade dopo 7 giorni **di inattività**" | che scade dopo 7 giorni **a prescindere dall'uso**, e che l'healthcheck la **rileva** ma non la previene |

### ⊘ V13 (`D1`, parte in `.github/workflows/tests.yml`) — decaduta, nessuna modifica
Il commento nel workflow diceva che la `DATABASE_URL` fittizia è "mai usata per davvero".
**Al momento della revisione era falso** — `run_migrations()` la usava sul serio all'import.
Dopo `V1` non è più così: durante i test `DATABASE_URL` serve davvero solo a costruire
l'`Engine`, che nessuno interroga. **La frase è diventata vera da sé, quindi non è stata
toccata.** Secondo caso in cui è il codice a raggiungere il documento.

### ✅ V2 (= `R14`) — email mancante nel guest checkout: 422 invece di 403
**Commit:** `d3a0f32` · **File:** `backend/routers/booking.py`, `tests/test_booking.py`
**Decisione dell'umano:** validazione esplicita nel router (fra tre opzioni proposte).

**Test prima del fix:** `test_prenotazione_guest_senza_email_restituisce_422` falliva con
`AssertionError: atteso 422 per email mancante, ricevuto 403: {"detail":"user_id and email do
not match"}`.

Il 403 descriveva un problema diverso da quello reale: chi integra l'API leggeva "le due cose
non combaciano" mentre il motivo vero era "manca un campo obbligatorio". **`email` resta
`Optional` nello schema di proposito** — lo studente loggato non la manda, la sua identità
viene dal token — quindi l'obbligo è espresso nel router, sul solo ramo guest. Coerente con la
Checklist identità di `STATO_PROGETTO.md` §12. **84 passed.**

### ✅ V3 (= `R11`) — rimosso `GET /bookings/`
**Commit:** `a8bc99d` · **File:** `backend/routers/booking.py`, `backend/routers/admin/__init__.py`

Nessun consumatore [verificato]: nessuna chiamata nel frontend, nessun test. Il pannello admin
usa `GET /admin/prenotazioni`, paginato. Al suo posto resta un commento che spiega cosa c'era e
perché non c'è più, così chi lo cerca trova una risposta invece del vuoto.

**Effetto collaterale gestito:** `from backend.routers.admin import get_admin` in `booking.py`
serviva solo a quell'endpoint ed è diventato un import morto — rimosso. Aggiornato di
conseguenza il commento in `admin/__init__.py`, che elencava `booking.py` fra i file che
importano `get_admin` da fuori del pacchetto. **84 passed.**

`GET /admin/export/csv` **non** è stato toccato: `STATO_PROGETTO.md` §3 lo dichiara "non
paginato di proposito".

### ✅ V4 (= `R12`) — rimosso `GET /slots/{slot_id}`
**Commit:** `23544db` · **File:** `backend/routers/slots.py`, `tests/test_slots.py`

Endpoint pubblico che restituiva qualunque slot per id, anche prenotato, bloccato o passato —
asimmetria mai documentata rispetto a `GET /slots/`, che filtra. Nessun consumatore
[verificato].

> ⚠️ **La suite passa da 84 a 83 test**, perché è stato rimosso anche
> `tests/test_slots.py::test_get_slot_singolo`. Non è un test aggiustato per farlo passare: è
> il test di una funzionalità deliberatamente eliminata, che sarebbe rimasto rosso per forza.
> Segnalato all'umano prima di procedere, come impone il mandato.

Rotte `/slots` rimaste: `GET /slots/` e `POST /slots/`. **83 passed.**

### ⛔ V5 (= `R10`) — `escludi_id`: NON TOCCARE, per decisione
Il parametro non è mai passato da nessun chiamante [verificato], ma il commento accanto
dichiara esplicitamente che è tenuto pronto per un caso d'uso futuro. **Decisione dell'umano:
lasciarlo.** Coerente con il principio del mandato di non trattare come criticità ciò che è una
scelta documentata. Resta nel referto come debito noto, non è sparito.

## Impatto sulle correzioni congelate

> Sezione per la **sessione 3**: quali voci della Fase 5 questa sessione ha reso obsolete o da
> riformulare. **Non ho modificato la Fase 5** — le voci restano lì come approvate.

### `D1` — DA RIFORMULARE (non più applicabile com'è scritta)
`D1` correggeva `README.md:252` aggiungendo l'avvertenza «lancialo sempre con `DATABASE_URL` e
`JWT_SECRET` fittizie, altrimenti tocca il database di sviluppo reale». **Dopo `V1` quel
pericolo non esiste più**: importare `backend.main` non esegue più migrazioni. La riga del
README va comunque corretta, ma il testo nuovo va riscritto: l'affermazione originale («non
tocca mai il MySQL di sviluppo o produzione») **è diventata vera**, quindi basta molto meno.

Proposta di testo aggiornato, da validare in sessione 3:
> \| `pytest` \| Esegue la suite di test automatici (`tests/`) — usa un database SQLite in
> memoria e non tocca il MySQL di sviluppo o produzione. Le migrazioni e lo scheduler partono
> solo all'avvio di un server vero (handler `lifespan` in `backend/main.py`), mai al semplice
> import. \|

Vale anche per la **modifica collegata** prevista da `D1` sul commento in
`.github/workflows/tests.yml` («`DATABASE_URL` mai usata per davvero»): dopo `V1` quella frase
è **corretta**. La sua riformulazione è una delle voci di rumore (`V13`) di questa sessione.

**È il primo caso previsto dal referto in cui è il codice a raggiungere il documento invece
del contrario.**

### `D13`, `D15`, `D29` — PARTE IN CODICE GIÀ FATTA
Tutte e tre avevano due metà: una nei documenti markdown e una nei commenti del codice. **La
metà in codice è stata applicata in questa sessione** (commit `886b10b`, voci `V10`, `V11`,
`V12`). Alla sessione 3 resta **solo la metà documentale**:

- `D13` → nessuna metà documentale: la voce è **interamente chiusa**. Restava solo la scelta
  (a) sui 6 rimandi, ora applicata. *Si può spuntare.*
- `D15` → resta da aggiungere il punto sul fuso dei job cron in `STATO_PROGETTO.md` §7. Il
  commento in `backend/scheduler.py` è già a posto e può fare da testo di riferimento.
- `D29` → restano `README.md:267`, `STATO_PROGETTO.md:331` e `.env.example`. Il commento in
  `backend/services/email_service.py` è già riscritto e contiene la formulazione approvata:
  **usarlo come modello** invece di riscriverla da capo.

### `D6` — NUMERO DA RIMISURARE
`D6` fissa la coverage a **80%**. Dopo `V1` la misura reale è **77%**: il codice di avvio non
viene più eseguito durante i test. Il calo è voluto, non una regressione. **Il numero va
rimisurato al momento di applicare `D6`**, non ricopiato: se la sessione 3 aggiunge o toglie
test cambierà ancora. Comando di riferimento (lo stesso della CI):

```
DATABASE_URL="sqlite:///:memory:" JWT_SECRET="test-secret" ./venv/Scripts/python.exe -m pytest
```

### `D31` — LA FOTOGRAFIA E LE TABELLE ENDPOINT SONO CAMBIATE (creato da questa sessione)
Le rimozioni di `V3` e `V4` rendono **obsoleti dei documenti che al momento della revisione
erano corretti**. Da aggiornare in sessione 3:

- **`STATO_PROGETTO.md` §3**, tabella `/bookings`: va tolta la riga
  «\| GET \| `/bookings/` \| admin \| tutte le prenotazioni \|».
- **`STATO_PROGETTO.md` §3**, tabella `/slots`: va tolta la riga
  «\| GET \| `/slots/{id}` \| no \| un singolo slot, qualsiasi stato \|».
- **§1.2 di questo stesso referto**: la fotografia dichiara **47 endpoint** e descrive
  entrambe le rotte rimosse. Il numero corretto è ora **45** (4 nei router non-admin invece di
  5, e 4 in `booking.py` invece di 5). *La fotografia della Fase 1 è per definizione datata al
  2026-09-01 e non va riscritta — ma questa nota serve a chi la legge dopo.*

Nessuna di queste voci era un difetto: erano descrizioni fedeli di un codice che poi è
cambiato. È il caso simmetrico di `D1`.

### Nuova voce documentale emersa in questa sessione
**`D30` — `frontend/privacy.html` non dichiara il dato `categoria`.** La sezione "What data is
collected" elenca nome, email, telefono, tag Discord, note, dettagli delle sessioni e, per chi
fa login, id e username Discord — ma **non `categoria`** (junior/senior/master), che il form di
prenotazione raccoglie e il database conserva. Il commento in testa a quella pagina impone
esplicitamente di aggiornarla "se un nuovo tipo di dato raccolto" viene introdotto: `categoria`
è entrata con il commit `ecd0746` (20/08) e la pagina è stata aggiornata il 25/08 senza
recepirla. **Non toccata in questa sessione** (`frontend/**` resta fra i percorsi vietati, ed è
comunque materia documentale): da valutare in sessione 3.
*Questa scoperta chiude anche `R9`: `categoria` non è dichiarata come raccolta e non è un
identificativo, quindi non anonimizzarla non contraddice nulla.*

---
