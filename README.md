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
- **`scheduler.py`** — Contiene il "lavoratore in background" che ogni tot minuti controlla se ci sono prenotazioni imminenti a cui inviare un promemoria via email/Discord.

#### `backend/models/` — la forma dei dati nel database

Ogni file qui dentro descrive **una tabella del database MySQL**, usando una libreria chiamata SQLAlchemy. Invece di scrivere query SQL a mano (`CREATE TABLE...`), scrivi una classe Python e SQLAlchemy si occupa di tradurla in tabelle vere. Questo si chiama **ORM** (Object-Relational Mapping — "mappatura oggetti-relazioni": ogni riga della tabella diventa un oggetto Python che puoi manipolare normalmente).

- `users.py` → tabella `users`: i dati di ogni studente/cliente (nome, email, tag Discord...).
- `slots.py` → tabella `slots`: gli orari che il coach ha reso disponibili.
- `booking.py` → tabella `bookings`: le prenotazioni vere e proprie, collegano uno `user` a uno `slot`.
- `client_note.py` → tabella `client_notes`: le note tecniche libere che il coach scrive su un cliente nel tempo.
- `availability_rule.py` → tabella `availability_rules`: le regole di disponibilità ricorrente ("ogni martedì 18-22").
- `availability_exception.py` → tabella `availability_exceptions`: i blocchi eccezionali (ferie, indisponibilità).
- `__init__.py` → non contiene logica, importa semplicemente tutti i model qui sopra in un unico posto, così altri file possono scrivere `from backend.models import User, Slot` invece di un import per ciascuno.

#### `backend/schemas/` — la forma dei dati che entrano/escono dall'API

Qui la libreria protagonista è **Pydantic**, non SQLAlchemy. È facile confondersi con i model, quindi è importante capire la differenza:
- Un **model** (SQLAlchemy) descrive una riga di una tabella nel database.
- Uno **schema** (Pydantic) descrive la forma di un messaggio JSON che entra o esce dall'API — cioè cosa il client deve mandare per creare qualcosa, e cosa il server restituisce.

Non sono la stessa cosa: per esempio, quando crei una prenotazione mandi `duration_hours` e `service_type`, ma non mandi `price_cents` (lo calcola il server) o `id` (lo assegna il database). Gli schemi Pydantic validano automaticamente i dati in arrivo (es. rifiutano una email scritta male) prima ancora che il tuo codice li tocchi.

- `users.py`, `slots.py`, `booking.py`, `client_note.py`, `availability.py` — uno schema `...Create` (cosa serve per creare) e uno `...Response` (cosa viene restituito) per ciascuna area.

#### `backend/services/` — la logica riutilizzabile

Ogni file qui incapsula la logica per **parlare con qualcosa di esterno o fare un calcolo complesso**, tenuta separata dai router per non ripetere codice e per poterla testare/riusare facilmente.

- `auth_service.py` — crea e verifica i token JWT (il "biglietto" digitale che prova che sei loggato, sia come admin che come studente — vedi il riquadro "Cos'è un JWT" più sotto).
- `email_service.py` — costruisce e invia le email (conferma, promemoria, notifica admin) tramite SendGrid.
- `calendar_service.py` — parla con le API di Google Calendar: crea/elimina eventi, legge gli eventi esistenti per la sincronizzazione.
- `discord_service.py` — invia messaggi al canale Discord del coach tramite un "webhook" (un URL segreto su cui puoi mandare messaggi senza dover programmare un vero bot).
- `timezone_service.py` — un'unica funzione (`utc_to_rome`) che converte un orario UTC nell'ora italiana, usata ovunque serva mostrare un orario al coach.
- `availability_service.py` — la logica per generare gli slot da una regola ricorrente e per applicare un blocco eccezionale.

#### `backend/routers/` — gli "indirizzi" dell'API

Ogni file definisce un gruppo di indirizzi web (endpoint) collegati tra loro da un prefisso comune. Se hai mai usato un sito e visto un indirizzo tipo `sito.com/utenti/5`, un router è il codice che decide "cosa succede quando qualcuno visita questo indirizzo".

- `users.py` → indirizzi che iniziano con `/users` (creare un utente, vedere il proprio profilo se loggato...).
- `slots.py` → indirizzi che iniziano con `/slots` (vedere gli slot liberi, crearne uno nuovo da admin).
- `booking.py` → indirizzi che iniziano con `/bookings` (creare una prenotazione — il cuore dell'app).
- `admin.py` → indirizzi che iniziano con `/admin` (login admin, dashboard, gestione prenotazioni/clienti/slot/regole/blocchi — il file più grande del progetto, perché il pannello admin fa molte cose).
- `discord_auth.py` → indirizzi che iniziano con `/auth/discord` (il flusso di login opzionale via Discord).

### `alembic/` — la "cronologia" del database

Alembic è uno strumento che tiene traccia di come cambia la struttura del database nel tempo (aggiungere una colonna, creare una tabella...), un po' come Git tiene traccia di come cambia il codice. Ogni file dentro `alembic/versions/` è un singolo cambiamento, con un `upgrade()` (come applicarlo) e un `downgrade()` (come annullarlo). `alembic/env.py` è il file di configurazione che collega Alembic ai tuoi model SQLAlchemy.

### `frontend/` — quello che vede l'utente (HTML/CSS/JavaScript)

Nessun framework: HTML, CSS e JavaScript "vanilla" (cioè scritti a mano, senza librerie come React). Ci sono due pagine web completamente separate:

- `index.html` + `js/app.js` + `css/style.css` → il form pubblico di prenotazione (3 step: scegli slot → i tuoi dati → conferma), più il login opzionale via Discord.
- `admin.html` + `js/admin.js` + `css/admin.css` → il pannello di amministrazione (dashboard, prenotazioni, clienti, slot).

Il JavaScript in questi file usa `fetch()` per chiamare gli indirizzi definiti nei router del backend, riceve JSON, e aggiorna la pagina modificando l'HTML direttamente (`document.getElementById(...).innerHTML = ...`) — senza nessun framework che lo faccia al posto tuo.

---

## Flusso di esecuzione: cosa succede davvero

### 1. Avvio del programma

Quando lanci `uvicorn backend.main:app`, succede questo, in ordine:

1. Python importa `backend/main.py`.
2. Prima ancora di creare l'app, il file chiama `run_migrations()` — applica automaticamente ogni cambiamento del database non ancora applicato (leggendo `alembic/versions/`).
3. Crea l'oggetto `app = FastAPI(...)`.
4. Registra le protezioni di base: rate limiting (`slowapi`) e CORS (chi può chiamare l'API da un browser).
5. "Monta" ogni router (`app.include_router(...)`) — da questo momento gli indirizzi definiti in `backend/routers/*.py` sono raggiungibili.
6. Avvia lo scheduler dei promemoria in background (`avvia_scheduler()`).
7. Monta la cartella `frontend/` come file statici, così il browser può scaricare HTML/CSS/JS.

Da qui in poi il programma resta "in ascolto", pronto a rispondere a richieste.

### 2. Esempio concreto: uno studente prenota una sessione

Questo è il percorso più importante da capire, perché attraversa quasi tutti i pezzi del progetto:

1. **Browser**: lo studente apre `index.html`. Il tag `<script src="/static/js/app.js">` in fondo alla pagina carica `app.js`.
2. **`app.js`**, al caricamento della pagina, chiama `fetch('/slots/')` per sapere quali orari sono liberi.
3. Questa richiesta arriva a **`backend/routers/slots.py`**, alla funzione collegata a `GET /slots/`. Quella funzione chiede al database (tramite il model `Slot` in `backend/models/slots.py`) tutti gli slot con `is_available=True`, e li restituisce come JSON (passando per lo schema `SlotResponse` in `backend/schemas/slots.py`, che decide esattamente quali campi includere).
4. `app.js` riceve il JSON e disegna una card per ogni slot nella pagina.
5. Lo studente sceglie uno slot, compila i suoi dati, clicca "Conferma". `app.js` fa due chiamate in sequenza: `POST /users/` (crea o ritrova l'utente in base all'email) e poi `POST /bookings/`.
6. La seconda chiamata arriva a **`backend/routers/booking.py`**. Qui succede la parte più "densa" del progetto: si controlla che lo slot esista e non sia già occupato (con un trucco per evitare che due persone prenotino lo stesso slot nello stesso istante — vedi i commenti nel file), si crea l'evento su Google Calendar (`calendar_service.py`), si salva la prenotazione nel database (model `Booking`), e si mandano tre notifiche in parallelo: email al cliente, email al coach (`email_service.py`), messaggio Discord (`discord_service.py`).
7. La risposta torna al browser, `app.js` mostra la schermata di conferma.
8. **Più tardi, in background**: lo `scheduler.py` (avviato al punto 6 dell'avvio) controlla periodicamente se questa prenotazione si avvicina, e se sì manda un promemoria — senza che nessuno debba fare nulla.

### 3. Esempio concreto: il coach guarda la dashboard

1. Il coach apre `admin.html`, inserisce username/password. `admin.js` manda `POST /admin/login`.
2. **`backend/routers/admin.py`** verifica le credenziali (`auth_service.py`) e restituisce un **token JWT** — una stringa firmata che prova "sono davvero il coach" senza dover rimandare la password a ogni richiesta.
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

Serve Python 3.11+ e un server MySQL raggiungibile (locale o remoto).

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
- Pannello admin: `http://127.0.0.1:8000/admin-panel` (credenziali da `ADMIN_USERNAME`/`ADMIN_PASSWORD`)

## Variabili d'ambiente

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `DATABASE_URL` | Sì | Stringa di connessione MySQL (`mysql+pymysql://utente:password@host/db`). L'app non parte senza. |
| `SECRET_KEY` | No | Chiave generica, tenuta per compatibilità. |
| `FRONTEND_ORIGINS` | No | Origini autorizzate via CORS, separate da virgola. Default locale già coperto nel codice. |
| `SENDGRID_API_KEY` | Sì (per le email) | API key SendGrid per l'invio di email transazionali. |
| `EMAIL_MITTENTE` | Sì (per le email) | Indirizzo email mittente di tutte le comunicazioni. |
| `EMAIL_ADMIN` | Sì (per le email) | Indirizzo email del coach, riceve le notifiche di nuova prenotazione. |
| `COACH_DISCORD_TAG` | No | Tag Discord del coach, mostrato nell'email di conferma al cliente. |
| `COACH_TELEGRAM_CONTACT` | No | Contatto Telegram del coach, mostrato nell'email di conferma al cliente. |
| `DISCORD_WEBHOOK_URL` | No | Webhook del canale Discord del coach, per le notifiche. |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` / `DISCORD_OAUTH_REDIRECT_URI` | No (per il login Discord) | Credenziali dell'app OAuth2 Discord. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Sì | Credenziali per accedere al pannello admin. |
| `JWT_SECRET` | Sì | Chiave di firma dei token JWT (admin e studenti). |
| `JWT_ALGORITHM` | No | Algoritmo di firma JWT (default `HS256`). |
| `JWT_EXPIRE_MINUTES` | No | Durata di validità dei token in minuti (default `480`). |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` / `GOOGLE_PRIVATE_KEY` / `GOOGLE_CALENDAR_ID` | No (per Google Calendar) | Credenziali del service account Google. |
| `REMINDER_HOURS_BEFORE` | No | Quante ore prima della sessione inviare il promemoria (default `24`). |
| `REMINDER_CHECK_INTERVAL_MINUTES` | No | Ogni quanti minuti lo scheduler controlla i promemoria da inviare (default `5`). |

## Comandi disponibili

| Comando | Cosa fa |
|---|---|
| `uvicorn backend.main:app --reload --port 8000` | Avvia il server in locale con reload automatico |
| `python -m alembic upgrade head` | Applica tutte le migrazioni pendenti |
| `python -m alembic downgrade -1` | Annulla l'ultima migrazione |
| `python -m alembic revision -m "descrizione"` | Crea una nuova migrazione vuota (da scrivere a mano) |
| `pip install -r requirements.txt` | Installa/aggiorna le dipendenze |

## Configurazione dei servizi esterni

### SendGrid (email)
1. Crea un account su [sendgrid.com](https://sendgrid.com) e genera una API key con permessi di invio (Settings → API Keys).
2. Verifica il dominio o almeno l'indirizzo mittente (Settings → Sender Authentication).
3. Imposta `SENDGRID_API_KEY`, `EMAIL_MITTENTE`, `EMAIL_ADMIN`.

### Google Calendar (sync disponibilità)
1. Crea un progetto su [Google Cloud Console](https://console.cloud.google.com), abilita la "Google Calendar API".
2. Crea un service account, genera una chiave JSON.
3. Condividi il calendario del coach con l'email del service account.
4. Imposta `GOOGLE_SERVICE_ACCOUNT_EMAIL`, `GOOGLE_PRIVATE_KEY`, `GOOGLE_CALENDAR_ID`.

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
6. Le migrazioni Alembic vengono eseguite automaticamente all'avvio.

## Sicurezza

- Nessun segreto è hardcoded nel codice: tutto passa da variabili d'ambiente, mai committate (`.env` è in `.gitignore`).
- Le credenziali del database MySQL erano finite in chiaro nel codice sorgente nei primi commit del progetto e restano nella cronologia git: se non è già stato fatto, ruota la password sul server MySQL indipendentemente da qualsiasi fix di codice.
