# ANALYSIS — VGC Coaching App

> ⚠️ **DOCUMENTO STORICO — non descrive lo stato attuale.** Fotografa il progetto al
> **2026-08-06** (vedi §5, "Decisioni prese con l'utente"). Quasi tutto ciò che segue è stato
> superato: gli endpoint pubblici sono stati chiusi, il CORS ristretto, le credenziali tolte dal
> codice, la password admin passata a hash bcrypt, l'invio email migrato da SendGrid all'API
> Gmail, i fusi orari sistemati, la race condition sullo slot risolta, e lo scheduler — qui
> dato per inesistente — oggi ha 8 job. Per lo stato di oggi vedi `STATO_PROGETTO.md`.
> Conservato come memoria delle decisioni prese allora, **non va aggiornato**.

> Documento generato da una sessione di analisi (nessun codice applicativo modificato in quella sessione). Autosufficiente: non presuppone di aver letto la conversazione originale.

## 1. Architettura in sintesi

Monolite Python/FastAPI che serve **sia** le API REST **sia** i file statici del frontend da un unico processo (nessun framework JS, nessuna build step: HTML/CSS/JS vanilla, serviti via `StaticFiles`/`FileResponse`). Persistenza su MySQL tramite SQLAlchemy ORM, migrazioni con Alembic. Deploy tipo Railway (Nixpacks + Procfile).

Due superfici applicative nettamente separate:
- **Pubblica** (`index.html` + `app.js`): wizard di prenotazione a 3 step (slot → dati → conferma), nessuna autenticazione, guest checkout de facto.
- **Admin** (`admin.html` + `admin.js`): pannello protetto da JWT, login con un singolo account admin da variabili d'ambiente (non un vero sistema utenti/ruoli).

## 2. Mappa dei file (ruolo effettivo, non presunto)

| Percorso | Ruolo reale |
|---|---|
| `backend/main.py` | Entrypoint FastAPI. Monta i router, monta `frontend/` come static, esegue le migrazioni Alembic a ogni avvio (import-time, prima ancora di creare `app`), dentro un `try/except` che non blocca il boot in caso di errore |
| `backend/database.py` | Engine SQLAlchemy + sessionmaker. Contiene un URL MySQL di fallback **con credenziali reali in chiaro** |
| `backend/models/users.py` | Tabella `users`: nome, email (unique), telefono, showdown username |
| `backend/models/slots.py` | Tabella `slots`: `start_time` (DateTime naive), `duration_hours`, `is_available` |
| `backend/models/booking.py` | Tabella `bookings`: collega user+slot, `duration_hours`, `price_cents`, `status` (pending/confirmed/cancelled), note cliente/admin, `calendar_event_id` |
| `backend/models/payment.py` | Tabella `payments` — **vestigiale**: nessuna integrazione Stripe/PayPal reale nel codice, solo colonna `stripe_session_id` mai popolata |
| `backend/schemas/*` | Pydantic per validazione input/output — puliti e minimali |
| `backend/routers/slots.py` | `GET /slots/`, `GET /slots/{id}`, `POST /slots/` — **nessuna autenticazione su nessuno di questi** |
| `backend/routers/booking.py` | `GET /bookings/` (pubblico, nessuna auth), `POST /bookings/` (crea prenotazione, invia email) |
| `backend/routers/users.py` | `GET /users/` (pubblico, nessuna auth — leak PII), `POST /users/` (get-or-create per email) |
| `backend/routers/admin.py` | Dashboard, gestione prenotazioni/clienti/slot, export CSV — protetti da JWT tranne l'export CSV che usa un secondo schema di auth via query param |
| `backend/services/auth_service.py` | JWT "fatto in casa" per un unico account admin da `.env`, confronto password in chiaro |
| `backend/services/calendar_service.py` | Google Calendar via service account: **solo scrittura** (crea/elimina evento), nessuna lettura |
| `backend/services/email_service.py` | Invio email via SendGrid; contiene il flusso di pagamento manuale PayPal (da rimuovere) |
| `frontend/index.html` + `js/app.js` + `css/style.css` | Wizard di prenotazione pubblico a 3 step |
| `frontend/admin.html` + `js/admin.js` + `css/admin.css` | Pannello admin SPA-like senza framework (show/hide di sezioni) |
| `alembic/versions/1972ef07e768_*.py` | Migrazione iniziale — crea le 4 tabelle |
| `alembic/versions/a4568987d2e7_*.py` | Migrazione `calendar_event_id` — **`upgrade()`/`downgrade()` vuoti**, non crea davvero la colonna |
| `nixpacks.toml` / `procfile` | Config di deploy duplicata (stesso comando uvicorn in entrambi) |
| `requirements.txt` | Include `bcrypt`/`passlib` mai usati; nessuna dipendenza Stripe/PayPal reale |
| `.env` | Correttamente in `.gitignore`; contiene tutti i segreti (DB, JWT, SendGrid, Google service account, PayPal, admin creds) |

## 3. Stack reale

- **Backend**: FastAPI + Uvicorn (Python 3.11), SQLAlchemy 2.0, driver PyMySQL → MySQL
- **Migrazioni**: Alembic
- **Auth**: JWT scritto a mano (`python-jose`), singolo account admin, nessun sistema utenti/ruoli
- **Email**: SendGrid
- **Calendar**: Google Calendar API via service account (solo scrittura)
- **Frontend**: HTML/CSS/JS vanilla, nessun framework/bundler
- **Deploy**: Nixpacks + Procfile (Railway-style)
- **Pagamenti**: nessuna integrazione reale — solo istruzioni di bonifico PayPal manuale in un'email statica, con stato di prenotazione `"pending"` in attesa di conferma admin dopo pagamento fuori banda

## 4. Visione target vs stato reale

### Già implementato
- Prenotazione slot base (guest checkout de facto)
- Google Calendar in scrittura (metà della sync richiesta: crea/elimina evento su conferma/cancellazione admin)
- Email di conferma cliente + notifica admin (via SendGrid)
- Dashboard admin: numeri base, lista prenotazioni, clienti, slot, export CSV
- JWT per pannello admin

### Abbozzato
- Mini-CRM: solo `note_admin` libero, nessuno storico strutturato
- Analytics: 3 numeri (totale, oggi, incassato) + prossimi slot liberi, niente di più
- Gestione slot: solo creazione singola manuale, nessuna ricorrenza

### Assente
- Gestione fusi orari (vedi §6, è un bug critico non solo una lacuna)
- Discord (OAuth2, campo Discord Tag, webhook notifiche)
- Menu servizi VGC (VOD Review, Team Building, Bo3 Sparring, Mentality) — oggi esiste solo selezione di durata
- Upload risorse pre-lezione (VOD/replay code)
- Link Discord/Telegram in email di conferma
- Sync Google Calendar in lettura (bloccare slot per tornei/stream)
- Stato/gestione no-show, promemoria automatici pre-sessione
- Rate limiting / anti-abuso sul form di prenotazione

## 5. Decisioni prese con l'utente (2026-08-06)

Queste risposte guidano la Roadmap e sono vincolanti per chi riprenderà il lavoro:

1. Il flusso di pagamento PayPal manuale va **rimosso completamente** — nessuno stato "in attesa di pagamento", conferma immediata al submit.
2. Le credenziali MySQL hardcoded in `database.py`/`alembic.ini` sono un **segreto esposto reale** (in git da sempre) — l'utente ha confermato di aver visto l'avviso ed è responsabile della rotazione della password sul server MySQL (azione fuori dal codice).
3. Il progetto è **ancora in sviluppo/test**, nessun dato reale in produzione — non serve pianificare migrazioni "a caldo" su dati esistenti.
4. La migrazione Alembic `a4568987d2e7` va sistemata per creare davvero la colonna `calendar_event_id`.
5. Il menu servizi VGC (VOD Review, Team Building/Poképaste Review, Bo3 Sparring, Mentality/Tournament Prep) ha **prezzo e durata fissi, uguali per tutti i servizi** — non serve un modello `Services` dedicato, basta un campo `service_type` con prezzo/durata costanti.
6. Discord: si parte con un **semplice campo testuale "Discord Tag"** nel form; OAuth2 rimandato a dopo (P3).
7. Le app/credenziali esterne mancanti (Discord bot/OAuth app, webhook URL) **vanno create da zero** — da includere nella roadmap come setup, non solo come codice consumer.

## 6. Problemi rilevati, ordinati per gravità

### Sicurezza critica
1. **Credenziali MySQL in chiaro nel codice sorgente**, committate in git dal primo commit — `backend/database.py:9`, `alembic.ini:89`. Azione utente: ruotare la password sul server MySQL indipendentemente da qualsiasi fix di codice, perché resta nella storia git.
2. **`GET /users/` pubblico, nessuna autenticazione** (`backend/routers/users.py:10-12`) — chiunque legge nome/email/telefono/showdown username di tutti i clienti.
3. **`GET /bookings/` pubblico, nessuna autenticazione** (`backend/routers/booking.py:15-17`) — espone note interne (`note_admin`) e dati di tutte le prenotazioni.
4. **`POST /slots/` pubblico, nessuna autenticazione** (`backend/routers/slots.py:22-30`) — chiunque può creare slot arbitrari; il frontend admin manda un `Authorization` header che il backend non verifica affatto su questo endpoint.
5. **Nessuna protezione anti-abuso sul form di prenotazione** — senza barriera economica (e con la rimozione del pagamento, ora zero barriere), niente rate limiting per IP, niente verifica email, niente limite di prenotazioni attive per persona: chiunque può occupare l'intero calendario.
6. Export CSV admin (`admin.py:319-329`) accetta il token JWT come query param invece che header — finisce in log server/cronologia browser/referrer; logica di verifica duplicata invece di riusare `Depends(get_admin)`.
7. Login admin senza rate limiting; confronto password in chiaro con `==` (`auth_service.py:20`, non a tempo costante); `bcrypt`/`passlib` presenti in `requirements.txt` ma mai usati.
8. CORS completamente aperto — `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]` (`main.py:30-35`).

### Bug funzionali critici
9. **Fusi orari assenti** — `Slot.start_time` è un `DateTime` naive (`backend/models/slots.py:9`), creato dall'admin via `<input type="datetime-local">` (`frontend/admin.html:113`) senza alcuna conversione esplicita di fuso orario prima dell'invio (`admin.js:326`). L'API lo restituisce come stringa ISO senza offset. Sul client, `formatDate`/`formatTime` (`app.js:13-29`) fanno `new Date(isoString)`: per una stringa naive, JS la interpreta nel **fuso orario del browser**, non in quello del coach. Uno studente in un altro fuso orario vede l'orario sbagliato. Nessuna conversione da nessuna parte nel flusso.
10. **Race condition su doppia prenotazione dello stesso slot** — `create_booking` (`backend/routers/booking.py:20-45`) legge `is_available`, poi scrive, senza lock/transazione atomica (niente `SELECT ... FOR UPDATE`, niente vincolo unico, niente update condizionale). Due richieste concorrenti sullo stesso slot possono generare due prenotazioni.
11. **Evento Google Calendar duplicato a ogni conferma** — `aggiorna_stato` (`backend/routers/admin.py:171-194`) chiama `crea_evento_calendario` **due volte** (residuo di debug del commit `d7cf366`, mai ripulito nel commit successivo). Il primo evento creato resta orfano sul calendario (il suo ID viene scartato), solo il secondo viene tracciato e sarà cancellabile.
12. **Migrazione incompleta** — `alembic/versions/a4568987d2e7_aggiungi_calendar_event_id_a_bookings.py` ha `upgrade()`/`downgrade()` vuoti (`pass`). Il model dichiara la colonna (`booking.py:17`) ma la migrazione non la crea: su un DB pulito, `alembic upgrade head` non genera `calendar_event_id` e l'app fallirà al primo utilizzo.
13. Nessuna validazione che `booking.duration_hours` corrisponda a `slot.duration_hours`; nessun controllo di sovrapposizione tra slot adiacenti — è possibile prenotare durate incoerenti con lo slot scelto.

### Incompleto / da rimuovere
14. Intero flusso di pagamento PayPal manuale (model `Payment` mai realmente usato oltre alla colonna, endpoint `GET /config/paypal-email` in `main.py:52-54`, testo hardcoded in `email_service.py`, sezione HTML di successo in `index.html:150-172`) — **in contraddizione diretta con la visione target**, da rimuovere per decisione esplicita dell'utente (§5.1).
15. Nessuno stato `no_show` nel campo `status` (oggi solo `pending`/`confirmed`/`cancelled`, vedi `admin.py:152`), nessun promemoria automatico pre-sessione, nessuno scheduler/cron nel codebase.
16. Migrazioni eseguite automaticamente a ogni boot (`main.py:13-26`) dentro un `try/except Exception` che stampa e continua — un fallimento di migrazione non blocca l'avvio, causando errori runtime confusi più avanti invece di un fallimento di boot pulito.

### Cattive pratiche / performance
17. N+1 query in `get_clienti` (`admin.py:233-267`) — due query aggiuntive per ogni cliente dentro un loop Python invece di un'unica query aggregata.
18. Nessuna paginazione su nessuna lista (`/bookings/`, `/admin/prenotazioni`, `/admin/clienti`, `/slots/`) — non urgente ora (progetto in sviluppo, pochi dati), ma da tenere presente.
19. Prezzo duplicato hardcoded sia in `frontend/js/app.js` (35/60/80) che in `backend/routers/booking.py` (`PRICE_TABLE`) — il backend è comunque l'autorità (non si fida del prezzo client), ma il valore va mantenuto sincronizzato manualmente in due posti.
20. Config di deploy duplicata tra `nixpacks.toml` e `procfile` (stesso comando uvicorn).

## 7. Decisioni architetturali da cambiare

- **Flusso di conferma prenotazione**: oggi la prenotazione nasce `"pending"` e passa a `"confirmed"` solo quando l'admin, manualmente, verifica di aver ricevuto il pagamento PayPal fuori banda. Questo è sbagliato per l'obiettivo dichiarato (attrito zero, nessun pagamento in-app). Il nuovo flusso deve confermare la prenotazione **immediatamente al submit**, spostando di conseguenza anche il momento in cui viene creato l'evento su Google Calendar (oggi legato al cambio di stato manuale dell'admin, va spostato alla creazione della prenotazione).
- **Storage dei tempi**: `start_time` va salvato in UTC nel database, con conversione esplicita al fuso orario dello studente lato client e al fuso orario del coach (Europe/Rome) lato input admin — oggi non esiste alcuna gestione dei fusi orari, è un buco strutturale non solo un dettaglio di formattazione.
- **Claim dello slot**: va reso atomico (update condizionale o lock) invece del pattern read-then-write attuale, per eliminare la race condition sulla doppia prenotazione.
