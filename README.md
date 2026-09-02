# VGC Coaching App — Guida di Studio

## Cosa fa questo progetto, in parole semplici

Immagina un coach di VGC (i tornei competitivi di Pokémon) che vuole vendere sessioni di coaching online, ma senza dover chattare avanti e indietro su Discord per trovare un orario libero. Questa app risolve esattamente questo problema:

- Uno **studente** apre un sito, vede quali orari sono liberi, sceglie che tipo di sessione vuole (analisi replay, team building, sparring...), inserisce i suoi dati e conferma. Fine — non serve creare un account, non c'è nessun pagamento da fare dentro l'app (quello si concorda dopo, privatamente).
- Il **coach** ha un pannello separato (protetto da password) dove vede tutte le prenotazioni, gestisce i suoi orari disponibili, tiene note sui suoi studenti, e riceve notifiche automatiche via email e Discord ogni volta che qualcuno prenota.

Il progetto è quindi diviso in due "facce" della stessa applicazione: una pubblica (il form di prenotazione) e una privata (il pannello di amministrazione). Dietro le quinte, un solo programma Python gestisce entrambe.

**Perché ti conviene studiare questo progetto**: è un esempio realistico e completo di applicazione web "full-stack" — tocca un database vero, un'API web, autenticazione, integrazioni con servizi esterni (email, Google Calendar, Discord), gestione dei fusi orari, e un frontend che parla con tutto questo. Sono gli stessi ingredienti che trovi in qualsiasi app web professionale, solo in scala ridotta e comprensibile.

---

## Il quadro generale: come sono collegati i pezzi

Prima di guardare i singoli file, è importante capire l'architettura generale — cioè come le parti si parlano tra loro.

```
                    ┌─────────────────────────────────────┐
                    │         IL TUO BROWSER               │
                    │  (dove vedi le pagine web)            │
                    └───────────────┬───────────────────────┘
                                    │  richieste HTTP (fetch)
                                    ▼
                    ┌─────────────────────────────────────┐
                    │      backend/main.py (FastAPI)        │
                    │  Un unico programma Python che:       │
                    │  1. Serve le pagine HTML/CSS/JS        │
                    │  2. Risponde alle chiamate API          │
                    └───────────────┬───────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌───────────────┐   ┌────────────────┐    ┌──────────────────┐
      │  Database MySQL │   │ Servizi esterni │    │  Scheduler         │
      │  (dati salvati) │   │ Email, Google,  │    │  (promemoria       │
      │                 │   │ Discord         │    │  automatici)       │
      └─────────────────┘   └────────────────┘    └──────────────────┘
```

Questa è una scelta architetturale importante da notare: **non ci sono due programmi separati** (uno per il sito, uno per l'API). C'è un solo processo Python (`uvicorn` che esegue `backend/main.py`) che fa entrambe le cose. Questo si chiama "monolite" — è la scelta più semplice possibile per un progetto di queste dimensioni, e infatti non c'è nessun framework frontend (React, Vue...): solo HTML/CSS/JavaScript scritti a mano, che nel browser chiamano l'API con `fetch()`.

---

## Struttura del progetto, file per file

### File nella root

| File | A cosa serve |
|---|---|
| `requirements.txt` | La lista di tutte le librerie Python di cui il progetto ha bisogno (l'equivalente di una "lista della spesa" per `pip install`). |
| `alembic.ini` | File di configurazione dello strumento che gestisce le "migrazioni" del database (vedi sotto, cartella `alembic/`). |
| `.env` / `.env.example` | `.env` contiene le password e chiavi segrete reali (password del database, API key...) e **non va mai condiviso o messo su GitHub**. `.env.example` è la stessa lista ma con valori finti, serve da modello. |
| `nixpacks.toml` | Dice al servizio di hosting (Railway) come costruire ed eseguire l'app quando la mandiamo online. |
| `.gitignore` | Elenco di file/cartelle che Git deve ignorare (tra cui `.env`, `venv/`, `__pycache__/`). |

### `backend/` — il "cervello" dell'app (Python)

Questa cartella contiene tutto il codice server. È organizzata in sotto-cartelle che seguono un pattern molto comune nelle app web: separare **cosa viene salvato** (models), **cosa viene scambiato con il client** (schemas), **la logica delle singole azioni** (services) e **gli indirizzi web disponibili** (routers).

#### File diretti in `backend/`

- **`main.py`** — Il punto di ingresso di tutto il programma. Quando lanci `uvicorn backend.main:app`, è questo file che viene eseguito per primo. Crea l'oggetto `app` di FastAPI, ci "attacca" tutti i router (le famiglie di indirizzi web), configura la sicurezza di base (CORS, rate limiting), avvia lo scheduler dei promemoria, ed esegue le migrazioni del database a ogni avvio.
- **`database.py`** — Configura la connessione al database MySQL. Definisce `Base` (la classe da cui ereditano tutti i "model", vedi sotto) e `get_db()`, una funzione che ogni pezzo di codice usa per ottenere una connessione al database in modo sicuro (e che la chiude sempre, anche in caso di errore).
- **`rate_limit.py`** — Un file piccolissimo che crea un solo oggetto (`limiter`), usato per impedire che qualcuno mandi troppe richieste di fila allo stesso indirizzo (protezione anti-abuso).
- **`scheduler.py`** — Gli **8 lavori automatici in background** che girano senza che nessuno li chieda: promemoria pre-sessione, richieste di recensione, sync col Google Calendar, generazione notturna degli slot dalle regole ricorrenti, controllo del token Gmail, anonimizzazione GDPR dei clienti inattivi, pulizia degli slot passati, backup del database su Drive. Partono all'avvio del server, non all'import del modulo (vedi `lifespan` in `main.py`).

#### `backend/models/` — la forma dei dati nel database

Ogni file qui dentro descrive **una tabella del database MySQL**, usando una libreria chiamata SQLAlchemy. Invece di scrivere query SQL a mano (`CREATE TABLE...`), scrivi una classe Python e SQLAlchemy si occupa di tradurla in tabelle vere. Questo si chiama **ORM** (Object-Relational Mapping — "mappatura oggetti-relazioni": ogni riga della tabella diventa un oggetto Python che puoi manipolare normalmente).

- `users.py` → tabella `users`: i dati di ogni studente/cliente (nome, email, tag Discord...).
- `slots.py` → tabella `slots`: gli orari che il coach ha reso disponibili.
- `booking.py` → tabella `bookings`: le prenotazioni vere e proprie, collegano uno `user` a uno `slot`.
- `package.py` → tabella `packages`: i pacchetti di sessioni pre-pagati assegnati a un cliente.
- `review.py` → tabella `reviews`: voto e commento lasciati dal cliente dopo una sessione.
- `client_note.py` → tabella `client_notes`: le note tecniche libere che il coach scrive su un cliente nel tempo.
- `availability_rule.py` → tabella `availability_rules`: le regole di disponibilità ricorrente ("ogni martedì 18-22").
- `availability_exception.py` → tabella `availability_exceptions`: i blocchi eccezionali (ferie, indisponibilità).
- `__init__.py` → non contiene logica, importa semplicemente tutti i model qui sopra in un unico posto, così altri file possono scrivere `from backend.models import User, Slot` invece di un import per ciascuno.

#### `backend/schemas/` — la forma dei dati che entrano/escono dall'API

Qui la libreria protagonista è **Pydantic**, non SQLAlchemy. È facile confondersi con i model, quindi è importante capire la differenza:
- Un **model** (SQLAlchemy) descrive una riga di una tabella nel database.
- Uno **schema** (Pydantic) descrive la forma di un messaggio JSON che entra o esce dall'API — cioè cosa il client deve mandare per creare qualcosa, e cosa il server restituisce.

Non sono la stessa cosa: per esempio, quando crei una prenotazione mandi `duration_hours` e `service_type`, ma non mandi `price_cents` (lo calcola il server) o `id` (lo assegna il database). Gli schemi Pydantic validano automaticamente i dati in arrivo (es. rifiutano una email scritta male) prima ancora che il tuo codice li tocchi.

- `users.py`, `slots.py`, `booking.py`, `client_note.py`, `availability.py`, `package.py`, `review.py`, `consulenza.py`, `pacchetto_richiesta.py` — uno schema `...Create` (cosa serve per creare) e uno `...Response` (cosa viene restituito) per ciascuna area.

#### `backend/services/` — la logica riutilizzabile

Ogni file qui incapsula la logica per **parlare con qualcosa di esterno o fare un calcolo complesso**, tenuta separata dai router per non ripetere codice e per poterla testare/riusare facilmente.

- `auth_service.py` — crea e verifica i token JWT (il "biglietto" digitale che prova che sei loggato, sia come admin che come studente — vedi il riquadro "Cos'è un JWT" più sotto).
- `email_service.py` — costruisce e invia le email (conferma, promemoria, notifica admin) tramite l'API Gmail (OAuth2, via HTTPS — non SMTP diretto, bloccato su Railway).
- `calendar_service.py` — parla con le API di Google Calendar: crea/elimina eventi, legge gli eventi esistenti per la sincronizzazione.
- `discord_service.py` — invia messaggi al canale Discord del coach tramite un "webhook" (un URL segreto su cui puoi mandare messaggi senza dover programmare un vero bot).
- `timezone_service.py` — le conversioni e i confronti di orario condivisi da tutto il progetto: `utc_to_rome()` (UTC → ora italiana, per la visualizzazione), `formatta_data_ora_rome()`, `ora_utc_naive()` ("adesso" nella stessa forma salvata nel database) e `intervalli_si_sovrappongono()`.
- `availability_service.py` — la logica per generare gli slot da una regola ricorrente e per applicare un blocco eccezionale.
- `retention_service.py` — anonimizza i clienti inattivi da troppo tempo (GDPR).
- `backup_service.py` — genera il dump SQL del database e lo carica su Google Drive.
- `google_oauth_service.py` — le credenziali OAuth condivise da Gmail e Drive, tenute in cache.
- `package_service.py` — il catalogo fisso dei pacchetti (`CATALOGO_PACCHETTI`).
- `booking_service.py` — libera slot ed evento calendario quando una prenotazione è cancellata.
- `pagination_service.py` — sanifica `pagina`/`per_pagina` e costruisce l'envelope condiviso dalle liste admin.

#### `backend/routers/` — gli "indirizzi" dell'API

Ogni file definisce un gruppo di indirizzi web (endpoint) collegati tra loro da un prefisso comune. Se hai mai usato un sito e visto un indirizzo tipo `sito.com/utenti/5`, un router è il codice che decide "cosa succede quando qualcuno visita questo indirizzo".

- `users.py` → indirizzi che iniziano con `/users` (creare un utente, vedere il proprio profilo se loggato...).
- `slots.py` → indirizzi che iniziano con `/slots` (vedere gli slot liberi, crearne uno nuovo da admin).
- `booking.py` → indirizzi che iniziano con `/bookings` (creare una prenotazione — il cuore dell'app).
- `admin/` → indirizzi che iniziano con `/admin` (login, dashboard, gestione prenotazioni/clienti/slot/regole/blocchi/recensioni/pacchetti). È un package, non un singolo file: `__init__.py` gestisce l'autenticazione (`get_admin`, `/login`) e assembla i sotto-router (`dashboard.py`, `bookings.py`, `clients.py`, `availability.py`, `packages.py`, `reviews.py`), separati per area così nessun file diventa enorme.
- `discord_auth.py` → indirizzi che iniziano con `/auth/discord` (il flusso di login opzionale via Discord).
- `consulenza.py` → `/consulenze` (richiesta di call conoscitiva gratuita: non crea slot né prenotazioni, manda solo i contatti al coach).
- `pacchetti_richieste.py` → `/pacchetti-richieste` (richiesta di attivazione pacchetto: anche qui solo un contatto, il pacchetto vero lo assegna l'admin dopo il pagamento).

### `alembic/` — la "cronologia" del database

Alembic è uno strumento che tiene traccia di come cambia la struttura del database nel tempo (aggiungere una colonna, creare una tabella...), un po' come Git tiene traccia di come cambia il codice. Ogni file dentro `alembic/versions/` è un singolo cambiamento, con un `upgrade()` (come applicarlo) e un `downgrade()` (come annullarlo). `alembic/env.py` è il file di configurazione che collega Alembic ai tuoi model SQLAlchemy.

### `frontend/` — quello che vede l'utente (HTML/CSS/JavaScript)

Nessun framework: HTML, CSS e JavaScript "vanilla" (cioè scritti a mano, senza librerie come React). Le pagine sono cinque, di cui due principali e completamente separate:

- `index.html` + `js/app.js` + `css/style.css` → il form pubblico di prenotazione (3 step: scegli slot → i tuoi dati → conferma), più il login opzionale via Discord.
- `admin.html` + `js/admin.js` + `css/admin.css` → il pannello di amministrazione (dashboard, prenotazioni, clienti, slot, pacchetti, recensioni).
- `about.html` + `js/about.js` → la pagina "Meet the Coach", con la vetrina delle recensioni approvate.
- `privacy.html` → l'informativa privacy/GDPR.
- `recensione.html` + `js/recensione.js` → la pagina pubblica raggiunta dal link ricevuto via email dopo la sessione, per lasciare voto e commento.

Il JavaScript in questi file usa `fetch()` per chiamare gli indirizzi definiti nei router del backend, riceve JSON, e aggiorna la pagina modificando l'HTML direttamente (`document.getElementById(...).innerHTML = ...`) — senza nessun framework che lo faccia al posto tuo.

---

## Flusso di esecuzione: cosa succede davvero

### 1. Avvio del programma

Quando lanci `uvicorn backend.main:app`, succede questo, in ordine:

1. Python importa `backend/main.py`.
2. Crea l'oggetto `app = FastAPI(..., lifespan=lifespan)`. Il semplice import **non** esegue migrazioni né avvia lo scheduler: succede tutto all'avvio del server vero, dentro l'handler `lifespan` (vedi il punto 6).
3. All'avvio, `lifespan` chiama `run_migrations()` — applica automaticamente ogni cambiamento del database non ancora applicato (leggendo `alembic/versions/`).
4. Registra le protezioni di base: rate limiting (`slowapi`) e CORS (chi può chiamare l'API da un browser).
5. "Monta" ogni router (`app.include_router(...)`) — da questo momento gli indirizzi definiti in `backend/routers/*.py` sono raggiungibili.
6. Sempre da `lifespan`, avvia lo scheduler in background (`avvia_scheduler()`) con i suoi 8 job periodici, e alla chiusura del server lo ferma.
7. Monta la cartella `frontend/` come file statici, così il browser può scaricare HTML/CSS/JS.

Da qui in poi il programma resta "in ascolto", pronto a rispondere a richieste.

### 2. Esempio concreto: uno studente prenota una sessione

Questo è il percorso più importante da capire, perché attraversa quasi tutti i pezzi del progetto:

1. **Browser**: lo studente apre `index.html`. Il tag `<script src="/static/js/app.js">` in fondo alla pagina carica `app.js`.
2. **`app.js`**, al caricamento della pagina, chiama `fetch('/slots/')` per sapere quali orari sono liberi.
3. Questa richiesta arriva a **`backend/routers/slots.py`**, alla funzione collegata a `GET /slots/`. Quella funzione chiede al database (tramite il model `Slot` in `backend/models/slots.py`) tutti gli slot ancora liberi (`is_available=True`) **e non ancora passati**, e li restituisce come JSON (passando per lo schema `SlotResponse` in `backend/schemas/slots.py`, che decide esattamente quali campi includere).
4. `app.js` riceve il JSON e disegna una card per ogni slot nella pagina.
5. Lo studente sceglie uno slot, compila i suoi dati, clicca "Conferma". `app.js` fa due chiamate in sequenza: `POST /users/` (crea o ritrova l'utente in base all'email) e poi `POST /bookings/`.
6. La seconda chiamata arriva a **`backend/routers/booking.py`**. Qui succede la parte più "densa" del progetto: si controlla che lo slot esista e non sia già occupato (con un trucco per evitare che due persone prenotino lo stesso slot nello stesso istante — vedi i commenti nel file), si crea l'evento su Google Calendar (`calendar_service.py`), si salva la prenotazione nel database (model `Booking`), e si mandano tre notifiche **una dopo l'altra, dopo** che la prenotazione è già salvata: email al cliente, email al coach (`email_service.py`), messaggio Discord (`discord_service.py`). Se una di queste fallisce, la prenotazione resta valida lo stesso.
7. La risposta torna al browser, `app.js` mostra la schermata di conferma.
8. **Più tardi, in background**: lo `scheduler.py` (avviato al punto 6 dell'avvio) controlla periodicamente se questa prenotazione si avvicina, e se sì manda un promemoria — senza che nessuno debba fare nulla.

### 3. Esempio concreto: il coach guarda la dashboard

1. Il coach apre `admin.html`, inserisce username/password. `admin.js` manda `POST /admin/login`.
2. **`backend/routers/admin/__init__.py`** verifica le credenziali (`auth_service.py`) e restituisce un **token JWT** — una stringa firmata che prova "sono davvero il coach" senza dover rimandare la password a ogni richiesta.
3. `admin.js` salva questo token e lo allega a ogni chiamata successiva nell'header `Authorization: Bearer <token>`.
4. Ogni endpoint del pannello admin ha `admin: str = Depends(get_admin)` nella sua firma — questo dice a FastAPI "prima di eseguire questa funzione, controlla che ci sia un token valido nell'header, altrimenti blocca la richiesta con errore 401". Questo è il meccanismo che protegge tutto il pannello.

---

## Concetti chiave spiegati semplice (per chi viene da Python puro)

- **Decoratore (`@qualcosa`)**: una riga che inizia con `@` sopra una funzione modifica il comportamento della funzione senza cambiarne il codice dentro. `@router.get("/slots/")` non è "magia" — dice semplicemente a FastAPI "quando arriva una richiesta GET su questo indirizzo, chiama questa funzione".
- **`async def` / `await`**: sono per funzioni che possono "aspettare" qualcosa (una risposta di rete, ad esempio) senza bloccare tutto il programma nel frattempo. In questo progetto il backend Python usa poco `async` (FastAPI gestisce comunque la concorrenza anche con funzioni normali `def`), ma il JavaScript del frontend lo usa spesso per le chiamate `fetch()`.
- **Dependency Injection (`Depends(...)`)**: quando una funzione FastAPI ha un parametro tipo `db: Session = Depends(get_db)`, non stai passando tu quel valore — è FastAPI che chiama `get_db()` per te e ti passa il risultato. Serve per non ripetere "apri una connessione al database" identica in ogni singola funzione.
- **ORM (SQLAlchemy)**: invece di scrivere `SELECT * FROM users WHERE id = 5`, scrivi `db.query(User).filter(User.id == 5).first()`. È Python normale (oggetti, metodi), ma dietro le quinte SQLAlchemy lo traduce in SQL vero.
- **Validazione (Pydantic)**: quando definisci `email: EmailStr` in uno schema, Pydantic controlla automaticamente che il valore ricevuto sia davvero una email valida, e rifiuta la richiesta con un errore chiaro se non lo è — senza che tu debba scrivere `if` a mano.
- **JWT (JSON Web Token)**: una stringa tipo `eyJhbGc...` che contiene informazioni (es. "sono l'admin", "scade tra 8 ore") firmate con una chiave segreta. Chiunque può leggerla, ma solo chi conosce la chiave segreta (il server) può crearne una valida o verificarla — per questo funziona come "prova d'identità" senza dover tenere una sessione salvata da qualche parte.
- **Migrazione (Alembic)**: un file che descrive un cambiamento incrementale alla struttura del database. Servono perché non puoi semplicemente "riscrivere" un database che ha già dati dentro — devi dirgli esattamente come modificarsi.

---

## Setup locale (per far girare il progetto sul tuo computer)

Serve **Python 3.11** — la stessa versione dichiarata in `nixpacks.toml` e pinnata in `.github/workflows/tests.yml`, così l'ambiente locale, la CI e la produzione girano sullo stesso interprete — e un server MySQL raggiungibile (locale o remoto).

**1. Crea l'ambiente virtuale** (un "contenitore" isolato di librerie Python, solo per questo progetto)
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**2. Installa le dipendenze**
```powershell
pip install -r requirements.txt
```

**3. Configura le variabili d'ambiente**
```powershell
copy .env.example .env
```
Poi apri `.env` e compila i valori veri (vedi la tabella sotto).

**4. Applica le migrazioni del database**
```powershell
python -m alembic upgrade head
```

**5. Avvia il server**
```powershell
uvicorn backend.main:app --reload --port 8000
```

- Form pubblico: `http://127.0.0.1:8000/`
- Pannello admin: `http://127.0.0.1:8000/admin-panel` (credenziali da `ADMIN_USERNAME`, password verificata contro `ADMIN_PASSWORD_HASH` — genera l'hash con `python scripts/hash_admin_password.py`)

## Variabili d'ambiente

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `DATABASE_URL` | Sì | Stringa di connessione MySQL (`mysql+pymysql://utente:password@host/db`). L'app non parte senza. |
| `FRONTEND_ORIGINS` | No | Origini autorizzate via CORS, separate da virgola. Devono includere lo schema (`https://...`): un hostname nudo non combacia mai con l'header `Origin` del browser. Default locale già coperto nel codice. |
| `LOG_LEVEL` | No | Livello minimo dei messaggi di log (default `INFO`). Portalo a `DEBUG` solo per un'indagine. |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | Sì (per le email) | Credenziali OAuth2 per inviare email tramite l'API Gmail (SMTP diretto è bloccato su Railway). |
| `EMAIL_MITTENTE` | Sì (per le email) | Indirizzo email mittente di tutte le comunicazioni. |
| `EMAIL_ADMIN` | Sì (per le email) | Indirizzo email del coach, riceve le notifiche di nuova prenotazione. |
| `COACH_DISCORD_TAG` | No | Tag Discord del coach, mostrato nell'email di conferma al cliente. |
| `COACH_TELEGRAM_CONTACT` | No | Contatto Telegram del coach, mostrato nell'email di conferma al cliente. |
| `DISCORD_WEBHOOK_URL` | No | Webhook del canale Discord del coach, per le notifiche. |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | No (per il login Discord) | Credenziali dell'app OAuth2 Discord. Senza, il bottone "Accedi con Discord" non può portare a un login riuscito. |
| `DISCORD_OAUTH_REDIRECT_URI` | No (per il login Discord) | URL di callback OAuth2. In produzione **deve** iniziare con `https://`: da questo l'app deduce di essere in produzione e marca `Secure` i cookie di sessione (Railway termina l'HTTPS a monte, quindi non è deducibile dalla richiesta). Deve inoltre coincidere carattere per carattere con il redirect URI configurato sul Discord Developer Portal. |
| `ADMIN_USERNAME` | Sì | Username per accedere al pannello admin. |
| `ADMIN_PASSWORD_HASH` | Sì | Hash bcrypt della password admin — **non la password in chiaro**. Genera l'hash con `python scripts/hash_admin_password.py` (chiede la password interattivamente, non va mai scritta come argomento da riga di comando o salvata in chiaro). |
| `JWT_SECRET` | Sì | Chiave di firma dei token JWT (admin e studenti). |
| `JWT_ALGORITHM` | No | Algoritmo di firma JWT (default `HS256`). |
| `JWT_EXPIRE_MINUTES` | No | Durata di validità dei token in minuti (default `480`). |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` / `GOOGLE_PRIVATE_KEY` / `GOOGLE_CALENDAR_ID` | No (per Google Calendar) | Credenziali del service account Google. |
| `REMINDER_HOURS_BEFORE` | No | Quante ore prima della sessione inviare il promemoria (default `24`). |
| `REMINDER_CHECK_INTERVAL_MINUTES` | No | Ogni quanti minuti lo scheduler controlla i promemoria da inviare (default `5`). |
| `PUBLIC_BASE_URL` | No | Dominio pubblico usato per costruire link assoluti nelle email (es. il link di recensione post-sessione). Se assente, si usa la prima origine di `FRONTEND_ORIGINS`. |
| `REVIEW_CHECK_INTERVAL_MINUTES` | No | Ogni quanti minuti lo scheduler controlla se ci sono richieste di recensione da inviare (default `60`). |
| `CALENDAR_SYNC_INTERVAL_MINUTES` | No | Ogni quanti minuti lo scheduler sincronizza automaticamente gli slot col calendario Google, oltre al bottone manuale in admin (default `60`). |
| `GMAIL_HEALTHCHECK_INTERVAL_HOURS` | No | Ogni quante ore lo scheduler controlla che `GMAIL_REFRESH_TOKEN` sia ancora valido, avvisando su Discord se smette di funzionare (default `24`). Vedi la sezione "Gmail API" più sotto. |
| `DRIVE_REFRESH_TOKEN` | No (per il backup automatico) | Token OAuth2 per caricare i dump del database su Google Drive. Vedi la sezione "Google Drive (backup automatico database)" più sotto. |
| `GOOGLE_DRIVE_BACKUP_FOLDER_ID` | No (per il backup automatico) | ID della cartella Drive di destinazione dei backup. |
| `BACKUP_RETENTION_DAYS` | No | Dopo quanti giorni un backup viene eliminato automaticamente da Drive (default `30`). |
| `RETENTION_MONTHS` | No | Dopo quanti mesi di inattività un cliente viene anonimizzato automaticamente, per conformità GDPR (default `24`). Vedi sezione "Conformità GDPR" più sotto. |

## Comandi disponibili

| Comando | Cosa fa |
|---|---|
| `uvicorn backend.main:app --reload --port 8000` | Avvia il server in locale con reload automatico |
| `python -m alembic upgrade head` | Applica tutte le migrazioni pendenti |
| `python -m alembic downgrade -1` | Annulla l'ultima migrazione |
| `python -m alembic revision -m "descrizione"` | Crea una nuova migrazione vuota (da scrivere a mano) |
| `pip install -r requirements.txt` | Installa/aggiorna le dipendenze |
| `pip install -r requirements-dev.txt` | Installa anche le dipendenze di test (pytest, httpx) |
| `pytest` | Esegue la suite di test automatici (`tests/`) — usa un database SQLite in memoria e non tocca il MySQL di sviluppo o produzione. Migrazioni e scheduler partono solo all'avvio di un server vero (handler `lifespan` in `backend/main.py`), mai al semplice import: è ciò che rende innocuo lanciare la suite con un `.env` popolato |
| `python scripts/hash_admin_password.py` | Genera l'hash bcrypt da mettere in `ADMIN_PASSWORD_HASH` (chiede la password in modo interattivo, senza echo) |

La stessa suite `pytest` gira automaticamente su ogni push/PR tramite GitHub Actions (`.github/workflows/tests.yml`), così un errore emerge prima del deploy, non dopo.

## Configurazione dei servizi esterni

### Gmail API (email)
SMTP diretto è bloccato dalla rete di Railway (`OSError: Network is unreachable`), quindi l'invio passa dall'API Gmail via HTTPS con autenticazione OAuth2, non da una semplice password.
1. Su [Google Cloud Console](https://console.cloud.google.com), nello stesso progetto usato per Google Calendar (o uno nuovo), abilita la "Gmail API".
2. Configura la schermata di consenso OAuth (tipo "Esterno"), aggiungi l'ambito `https://www.googleapis.com/auth/gmail.send`, e aggiungi l'account Gmail mittente come utente di test.
3. Crea credenziali → ID client OAuth → tipo "App per computer" → copia Client ID e Client Secret.
4. Imposta `GMAIL_CLIENT_ID` e `GMAIL_CLIENT_SECRET` nel `.env`, poi ottieni un `GMAIL_REFRESH_TOKEN` eseguendo `python scripts/reauth_gmail.py` — apre il browser, chiede di autorizzare l'app con l'account Gmail mittente, e alla fine offre di scrivere subito il token nel `.env` locale (va comunque copiato a mano anche su Railway).
5. Imposta anche `EMAIL_MITTENTE` (lo stesso account autorizzato) ed `EMAIL_ADMIN`.

**⚠️ Scadenza del refresh token — leggi con attenzione.** Finché la schermata di consenso OAuth resta in stato **"Testing"**, il `GMAIL_REFRESH_TOKEN` scade dopo **7 giorni, a prescindere dall'uso che se ne fa** — non dopo 7 giorni di *inattività*, come si è creduto a lungo. Osservato in produzione il 2026-09-02: il token è scaduto pur essendo esercitato ogni giorno dall'healthcheck e dalle email di ogni prenotazione. Prima o poi le email smettono di partire, silenziosamente. Ci sono due livelli di protezione:
- **Rete di sicurezza già attiva**: lo scheduler (`controlla_credenziali_gmail` in `backend/scheduler.py`) controlla il token ogni `GMAIL_HEALTHCHECK_INTERVAL_HOURS` ore e avvisa il coach su Discord appena smette di funzionare — a quel punto rilancia `python scripts/reauth_gmail.py` e aggiorna `GMAIL_REFRESH_TOKEN` su Railway. Attenzione: questo controllo **rileva** la scadenza, non la previene.
- **Soluzione definitiva (consigliata)**: su Google Cloud Console, porta la schermata di consenso OAuth da "Testing" a **"In production"** (non richiede la verifica completa di Google per un solo scope non sensibile come `gmail.send`). Fatto questo, il token smette di scadere per inattività e il controllo automatico/lo script restano solo una rete di sicurezza, non una necessità periodica.

### Google Calendar (sync disponibilità)
1. Crea un progetto su [Google Cloud Console](https://console.cloud.google.com), abilita la "Google Calendar API".
2. Crea un service account, genera una chiave JSON.
3. Condividi il calendario del coach con l'email del service account.
4. Imposta `GOOGLE_SERVICE_ACCOUNT_EMAIL`, `GOOGLE_PRIVATE_KEY`, `GOOGLE_CALENDAR_ID`.

### Google Drive (backup automatico database)
Il piano Railway attuale (Hobby) non include backup né point-in-time recovery per il database MySQL (verificato nella dashboard Railway, tab "Backups" del servizio MySQL: "Backups and point-in-time recovery (PITR) are only available for customers on the Pro plan"). Per non restare senza nessuna rete di sicurezza, un job schedulato (`controlla_e_esegui_backup_database` in `backend/scheduler.py`, una volta al giorno) genera un dump SQL completo e lo carica su Google Drive — un posto diverso da Railway.

**⚠️ Non usa il service account** già configurato per Calendar (`GOOGLE_SERVICE_ACCOUNT_EMAIL`), anche se è lo stesso progetto Google Cloud — scoperto testando un upload reale: un service account non ha una propria quota di archiviazione su Drive, quindi ogni file che crea fallisce con `storageQuotaExceeded`, anche in una cartella condivisa con lui in modalità Editor (le Shared Drive risolverebbero, ma sono una funzionalità Google Workspace, non disponibile su un account Gmail personale). La soluzione è OAuth con l'account Google vero del coach, stesso schema già usato per Gmail:
1. Nello stesso progetto Google Cloud già usato per Calendar/Gmail, abilita la **"Google Drive API"**.
2. Sulla stessa schermata di consenso OAuth già configurata per Gmail (Google Cloud Console → OAuth consent screen → Scopes), aggiungi anche lo scope `https://www.googleapis.com/auth/drive.file`.
3. Su [Google Drive](https://drive.google.com), con il TUO account normale, crea una cartella dedicata ai backup (nessuna condivisione da fare — è già tua).
4. Apri la cartella nel browser: l'id è la parte finale dell'URL (`https://drive.google.com/drive/folders/QUESTO_È_L_ID`). Impostalo in `GOOGLE_DRIVE_BACKUP_FOLDER_ID`.
5. Esegui `python scripts/reauth_drive.py` — apre il browser, autorizza con il tuo account, e offre di scrivere subito `DRIVE_REFRESH_TOKEN` nel `.env` locale (va comunque copiato a mano anche su Railway).
6. Facoltativo: `BACKUP_RETENTION_DAYS` (default 30) decide dopo quanti giorni un backup viene eliminato da Drive automaticamente, per non accumularsi all'infinito.

Senza `GOOGLE_DRIVE_BACKUP_FOLDER_ID`/`DRIVE_REFRESH_TOKEN` configurati, il job registra solo un avviso nei log e non fa nulla (non blocca l'avvio dell'app) — finché non li imposti, il database resta senza backup. La stessa **scadenza** descritta nel box della sezione Gmail API vale anche per questo token. Attenzione però: l'healthcheck schedulato controlla **solo** `GMAIL_REFRESH_TOKEN` — un `DRIVE_REFRESH_TOKEN` scaduto si scopre dall'alert Discord del backup notturno fallito, quindi fino a 24 ore dopo e a copia di sicurezza già saltata. Portare la schermata di consenso a "In production" risolve per entrambi insieme.

### Discord — Webhook notifiche
1. Sul server Discord del coach: Impostazioni canale → Integrazioni → Webhook → Crea Webhook.
2. Copia l'URL del webhook in `DISCORD_WEBHOOK_URL`.

### Discord — OAuth2 login studenti (opzionale)
1. Crea un'app su [Discord Developer Portal](https://discord.com/developers/applications).
2. Sezione OAuth2 → General: copia Client ID e Client Secret.
3. Sezione OAuth2 → Redirects: aggiungi l'URL esatto configurato in `DISCORD_OAUTH_REDIRECT_URI`.

## Deploy

Configurato per Railway con builder Nixpacks (`nixpacks.toml`, unica fonte di verità per il comando di avvio).

1. Collega il repository a un nuovo progetto Railway.
2. Aggiungi un database MySQL.
3. Imposta tutte le variabili d'ambiente della tabella sopra.
4. Aggiorna `FRONTEND_ORIGINS` e `DISCORD_OAUTH_REDIRECT_URI` con il dominio reale.
5. Aggiungi lo stesso redirect URI di produzione anche sul Discord Developer Portal.
6. Le migrazioni Alembic vengono eseguite automaticamente all'avvio (con backup di sicurezza automatico se ce ne sono in sospeso — vedi sopra).
7. Collega un servizio di monitoraggio esterno gratuito (es. [UptimeRobot](https://uptimerobot.com), [Better Uptime](https://betteruptime.com)) all'endpoint `GET /health` del dominio di produzione, a intervalli di qualche minuto — senza, un sito che va giù si scopre solo quando un cliente si lamenta. L'endpoint controlla anche che il database risponda, non solo che il processo sia vivo.

## Backup e ripristino

Vedi "Google Drive (backup automatico database)" sopra per il setup. Per **ripristinare** un backup in caso di emergenza (database corrotto/perso):
1. Scarica il file `.sql` più recente dalla cartella Drive di backup.
2. `mysql -u UTENTE -p -h HOST NOME_DATABASE < backup.sql` (stesse credenziali di `DATABASE_URL`) — il file contiene sia lo schema (`CREATE TABLE`) sia i dati (`INSERT`), è autosufficiente.
3. Verifica che l'app riparta correttamente puntando allo stesso `DATABASE_URL`.

Non è mai stato provato un ripristino reale end-to-end — vale la pena farlo almeno una volta in un ambiente di prova, non aspettare una vera emergenza per scoprire se funziona.

## Sicurezza

- Nessun segreto è hardcoded nel codice: tutto passa da variabili d'ambiente, mai committate (`.env` è in `.gitignore`).
- Le credenziali del database MySQL erano finite in chiaro nel codice sorgente nei primi commit del progetto e restano nella cronologia git: se non è già stato fatto, ruota la password sul server MySQL indipendentemente da qualsiasi fix di codice. Riguarda il database di **sviluppo locale**: la produzione su Railway usa credenziali separate, generate dalla piattaforma (`MYSQL_ROOT_PASSWORD` sul servizio MySQL) e mai finite in git.
- La password admin non è mai salvata in chiaro: `ADMIN_PASSWORD_HASH` contiene solo un hash bcrypt, verificato con `bcrypt.checkpw` a ogni login.
- Il login admin (`POST /admin/login`) è protetto da rate limiting (`slowapi`) contro tentativi di forza bruta.
- La sessione dello studente (dopo login Discord) viaggia in un cookie `httpOnly`/`samesite=lax` (`secure` in produzione), non in `localStorage` — non leggibile da JavaScript, quindi non rubabile via XSS.
- Il flusso OAuth2 Discord usa un cookie `state` con confronto a tempo costante (`secrets.compare_digest`) per prevenire attacchi CSRF sul login.
- Ogni endpoint sensibile che tocca un pacchetto/prenotazione di uno studente verifica che l'oggetto appartenga davvero a chi ha fatto la richiesta (protezione IDOR), non solo che esista.

### Conformità GDPR
- `frontend/privacy.html` — informativa privacy (base giuridica, dati raccolti, diritti dell'interessato).
- Diritto alla cancellazione (Art. 17): `DELETE /admin/clienti/{id}` rimuove definitivamente un cliente e tutti i dati collegati (prenotazioni, recensioni, note, pacchetti) — pulsante "🗑️ Elimina" nel pannello admin.
- Limitazione della conservazione (Art. 5.1.e): `backend/services/retention_service.py`, eseguito ogni notte dallo scheduler, anonimizza automaticamente i clienti inattivi da oltre `RETENTION_MONTHS` mesi (colonna `User.anonimizzato_at` traccia chi è già stato processato, per non ripetere il lavoro).
