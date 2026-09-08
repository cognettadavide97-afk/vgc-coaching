# Revisione 2 — Security

**Mandato:** security engineer. Ogni input è ostile, ogni utente autenticato è
malintenzionato. Verifica esplicita endpoint per endpoint.
**Perimetro:** `backend/`, più il frontend al confine (auth, contratti, escaping).
**Metodo:** lettura del codice **più verifica dinamica**. Ho eseguito il backend
contro il database SQLite di test e riprodotto gli attacchi: dove scrivo
[VERIFICATO] con un esito HTTP, quell'esito l'ho ottenuto, non dedotto.
Nessun altro documento di `audit/` è stato letto.
**Domanda guida:** cosa può fare un utente legittimo che non dovrebbe poter fare?

> **Avviso preliminare — un incidente causato da questa revisione.** Uno degli
> script di verifica ha importato l'app con il `.env` reale presente sul disco e
> una chiamata di cancellazione è arrivata **al Google Calendar di produzione**
> (`cognetta.davide97@gmail.com`), rispondendo 404 perché l'id evento era finto:
> nessun dato è stato toccato. Non è un incidente irrilevante, è un **finding**:
> importare qualunque modulo di questo progetto carica credenziali di produzione
> e le rende spendibili verso l'esterno (§S15). Ho poi isolato il trasporto nelle
> prove successive.

---

## 0. Rettifica al contesto fornito

Il contesto dice *"senza framework nulla è garantito di default"*. Il progetto usa
**FastAPI 0.136.3 + Pydantic 2.13.4** (`requirements.txt:21,44`,
`backend/main.py:25,129`). Ho comunque verificato endpoint per endpoint come da
mandato, senza dare per scontato nulla — e la parte che il framework copre
(coercizione dei tipi, `Literal`, `EmailStr`) regge. **Quello che il framework non
copre è ciò che non gli è stato chiesto**: nessuno schema dichiara un
`max_length` (§S4), e le regole di autorizzazione per-risorsa sono codice a mano
(che, va detto, ho trovato corretto — §1).

---

## 1. Quello che ho provato ad attaccare e ha retto

Lo scrivo per primo perché delimita il resto: **non ho trovato IDOR classici, né
SQL injection, né XSS**.

| Prova | Esito |
|---|---|
| 13 endpoint `/admin/*` + `GET /users/` + `POST /slots/` senza token | **401** su tutti |
| Token studente valido usato su endpoint admin | **401** su tutti (`auth_service.py:86`) |
| Studente B cancella la prenotazione di C (`PATCH /bookings/{id}/cancella`) | **403** `This booking doesn't belong to you` (`booking.py:296`) |
| `package_id` di un altro utente in `POST /bookings/` | 404 (`booking.py:143`, confronto con `studente.id` dal token, non col body) |
| Prezzo/sessioni pilotati dal client | Impossibile: listino server-side (`booking.py:205`, `admin/packages.py:43`) |
| SQL raw / concatenazione | Solo `text("SELECT 1")` (`main.py:184`) e i nomi tabella da `SHOW TABLES` (`backup_service.py:96,102`), auto-generati |
| XSS nel pannello admin su dati del pubblico | `escapeHtml` applicato su nome, email, discord, `replay_code`, note, commenti (`admin.js:377-389,497-500,601,776-779`) |
| `javascript:` in `vod_link` | Bloccato: `renderVodLink` ammette solo `^https?://` (`admin.js:213-224`) |
| XSS nella vetrina pubblica recensioni | `escapeHtml` su commento e nome (`about.js:31-32`) |
| Header injection SMTP via il campo `nome` | Rifiutata da Python: `ValueError: Header values may not contain linefeed` |
| Upload di file | Nessun endpoint lo accetta |
| Secret nel repository | `.env` ignorato (`.gitignore:1`) e **mai committato** (`git log --all -- .env` vuoto); `.env.example` contiene solo segnaposto |

L'autorizzazione per-risorsa, dove esiste, è fatta bene. I problemi sotto stanno
altrove: **nel flusso pubblico di prenotazione, che non ha alcuna prova di
identità**.

---

## 2. Findings

### S1 — BLOCCANTE — Chiunque, senza login, prenota a nome di terzi, ne esaurisce la quota e brucia l'agenda del coach

`backend/routers/users.py:104-137` — `backend/routers/booking.py:99-126,156-165,213,250-276`

**[VERIFICATO — riprodotto end-to-end]**

`POST /users/` è pubblico e si comporta da *get-or-create*: con un'email già nota
restituisce **l'id dell'utente esistente**. È un oracolo email → `user_id`:

```
POST /users/ {"nome":"Vittima","email":"vittima@example.com"}     -> 200 {"id": 1}
POST /users/ {"nome":"Qualsiasi","email":"vittima@example.com"}   -> 200 {"id": 1}   # stesso id
```

`POST /bookings/` senza login verifica solo che `user_id` ed `email` coincidano
(`booking.py:122-126`). L'oracolo qui sopra fornisce esattamente quella coppia:

```
POST /bookings/ {"user_id":1,"email":"vittima@example.com","slot_id":..,...}  -> 200
  -> booking id=1 per user_id=1 (la vittima)
  -> evento Google Calendar creato con email_cliente = vittima@example.com
  -> email di conferma inviata alla vittima dal Gmail del coach
```

Due prenotazioni bastano a saturare `MAX_PRENOTAZIONI_ATTIVE` (`booking.py:31`):

```
POST /bookings/ (terza, questa volta legittima)  -> 400
  "You already have 2 active bookings. Cancel or complete a session before booking another one."
```

**La vittima è ora esclusa dal servizio** e non ha modo di rimuovere prenotazioni
che non ha creato: `PATCH /bookings/{id}/cancella` richiede il login Discord
(`booking.py:284`), e se l'account Discord della vittima non è collegato a
quell'email non ha alcun percorso self-service.

Il commento a `booking.py:104-109` dichiara di aver *"alzato il costo
dell'attacco da 'indovina un id' a 'conosci già l'email della vittima'"*. È vero,
ma il costo residuo è zero in tre scenari: l'email è pubblica (Discord, social,
tornei), l'attaccante è un ex cliente, oppure **all'attaccante non serve una
vittima specifica**. Con email inventate — nessuna verifica di esistenza — al
ritmo consentito dal rate limit si ottengono 5 utenti/minuto × 2 prenotazioni,
cioè:

- **tutti gli slot del coach occupati** e non rivendibili;
- un evento su Google Calendar per ciascuno;
- **un'email inviata dal Gmail del coach a un indirizzo scelto dall'attaccante**,
  con `nome_cliente` pure scelto dall'attaccante nel corpo
  (`email_service.py:126`) — l'applicazione diventa un piccolo relay a template
  fisso, con la reputazione di invio dell'account del coach come garanzia.

**Intervento, in due tempi.**
*Tampone, oggi (2 ore):* `POST /bookings/` smette di accettare `user_id`; riceve
solo `email` e `nome` e risolve l'utente lato server. `POST /users/` smette di
restituire l'id (`202` senza corpo). Toglie l'oracolo, **non** la possibilità di
prenotare a nome di un'email nota.
*Cura, la vera (1-2 giorni):* la prenotazione senza login nasce
`status="pending"` e non occupa lo slot in modo definitivo finché il cliente non
clicca un link monouso ricevuto per email. È l'unico modo di legare una
prenotazione a un'identità quando non c'è login, ed è anche ciò che rende
inoffensivi §S2 e §S4.

---

### S2 — ALTA — Un a-capo nel nome sopprime silenziosamente la notifica al coach

`backend/schemas/users.py:17` — `backend/services/email_service.py:221,220-224`

**[VERIFICATO — riprodotto end-to-end]** `UserCreate.nome` è un `str` senza alcun
vincolo. Il nome finisce **nell'oggetto** dell'email al coach:
`f"Nuova prenotazione — {nome_cliente}"` (`email_service.py:221`). Python rifiuta
gli a-capo negli header (`ValueError`), e quella `ValueError` finisce nel
`try/except Exception` di `email_service.py:220-224`, che la registra e prosegue.

```
POST /users/  {"nome":"Mario Rossi\nBcc: chiunque@example.com", ...}  -> 200
POST /bookings/                                                        -> 200  status=confirmed
email effettivamente costruite: [('ostile@example.com', 'Booking confirmed')]
notifica al coach presente? False
```

La prenotazione è confermata, lo slot è consumato, il cliente riceve la sua
conferma, e **l'avviso al coach non parte**. Resta solo la riga di log e la
notifica Discord, che invece arriva (JSON, gli a-capo non la disturbano).

Non è header injection — Python la blocca, l'ho verificato — è **soppressione
selettiva di un canale di allerta**, che rende §S1 più silenzioso di quanto
sembri.

**Intervento minimo.** `nome: str = Field(min_length=1, max_length=100, pattern=r"^[^\r\n]+$")`
in `schemas/users.py:17`. **Costo: 15 minuti.**

---

### S3 — ALTA — Doppia spesa di un pacchetto: l'incremento del credito non è atomico

`backend/routers/booking.py:142,145-146,242-243` (a confronto con `:167-200`)

**[VERIFICATO — lettura del codice, confermata sull'oggetto funzione]** La
redenzione di un pacchetto è un classico check-then-write su tre istruzioni
distanti fra loro:

```
:142   package = db.query(Package).filter(...).first()
:145   if package.sessioni_usate >= package.sessioni_totali:  ->  400
:243   package.sessioni_usate += 1                            # read-modify-write in Python
:245   db.commit()
```

Nessun `with_for_update()`, nessun `UPDATE` condizionale, nessun vincolo di
database che impedisca `sessioni_usate > sessioni_totali` (`models/package.py:25-26`).

Due richieste concorrenti dello stesso studente con **un** credito residuo leggono
entrambe `sessioni_usate = 1`, superano entrambe il controllo, scrivono entrambe
`2`, e **ottengono due sessioni da un credito**. Con N richieste parallele, N
sessioni.

Quello che rende il finding netto è il confronto interno: **sessanta righe più su,
nella stessa funzione, l'autore ha risolto esattamente questo problema per gli
slot** con un `UPDATE` condizionale e il controllo di `rowcount`
(`booking.py:167-200`), spiegandolo in un commento di quattordici righe. La stessa
difesa non è stata estesa alla risorsa che ha un valore monetario diretto.

È anche l'unico finding che risponde in pieno alla domanda guida: lo sfruttatore è
un **cliente pagante autenticato**, che usa il servizio esattamente come previsto,
solo due volte nello stesso istante.

**Intervento minimo.** Lo stesso schema dello slot:

```python
esito = db.execute(
    update(Package)
    .where(Package.id == package.id, Package.sessioni_usate < Package.sessioni_totali)
    .values(sessioni_usate=Package.sessioni_usate + 1)
)
if esito.rowcount == 0:
    db.rollback(); raise HTTPException(400, "This package has no sessions left")
```

**Costo: 1 ora**, incluso il test.

---

### S4 — ALTA — Nessun campo di input ha un limite di lunghezza, in nessuno schema

`backend/schemas/users.py:17-21` — `backend/schemas/booking.py:36-38` —
`backend/schemas/client_note.py:9` — `backend/schemas/consulenza.py:12-15` —
`backend/schemas/pacchetto_richiesta.py:14-18` — `backend/routers/booking.py:213,240-245`

**[VERIFICATO]** Non esiste un solo `Field(max_length=...)` in tutto
`backend/schemas/`. L'unico vincolo dimensionale del progetto è `voto: int = Field(ge=1, le=5)`
(`schemas/review.py:10`). Le colonne però sono dimensionate:
`nome String(100)`, `vod_link String(500)`, `replay_code String(200)`,
`discord_tag String(100)`, `telefono String(20)`.

```
POST /bookings/  con vod_link di 5000 caratteri (colonna String(500))  -> 200
```

Su SQLite passa. **[SOSPETTO — si conferma così:** eseguire lo stesso `INSERT` sul
MySQL di Railway, o `SELECT @@sql_mode`; con `STRICT_TRANS_TABLES` attivo, che è
il default MySQL 8, l'inserimento fallisce con *Data too long for column* **]**.

Se fallisce in produzione, la sequenza in `create_booking` rende il fallimento
costoso: **l'evento su Google Calendar viene creato a riga 213, l'`INSERT` avviene
a riga 240-245**. Un `INSERT` che esplode lascia l'evento sul calendario del coach
senza alcuna prenotazione che lo giustifichi, e l'operazione è ripetibile 5 volte
al minuto da un endpoint senza autenticazione.

Indipendentemente da MySQL, restano verificati: `note_cliente` è `Text` senza
limite, scrivibile da chiunque; e le stringhe illimitate arrivano nei corpi email
(`email_service.py:216`) e negli embed Discord, dove il campo ha un tetto di 1024
caratteri lato API.

**Intervento minimo.** `max_length` su ogni campo, allineato alla colonna.
**Costo: 1 ora.**

---

### S5 — ALTA — [SOSPETTO] Il rate limiting conta quasi certamente per proxy, non per client — e diventa una leva di DoS

`backend/rate_limit.py:8,12` — `nixpacks.toml:5` — `venv/.../uvicorn/config.py:344`

**[VERIFICATO nel codice]** `get_remote_address` restituisce `request.client.host`
e nient'altro (`venv/Lib/site-packages/slowapi/util.py`). Il comando di avvio è
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT` (`nixpacks.toml:5`): non
passa `--forwarded-allow-ips`. In uvicorn 0.49 `proxy_headers` vale `True` ma
`forwarded_allow_ips` ricade su `os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")`
(`config.py:343-344`), e `FORWARDED_ALLOW_IPS` **non compare né in `.env` né in
`.env.example`**.

**[SOSPETTO — si conferma così:** guardare una manciata di righe di access log su
Railway, che hanno la forma `INFO: <ip>:<porta> - "POST /bookings/ HTTP/1.1" 200`.
Se l'indirizzo è sempre lo stesso, o è un indirizzo interno (`10.x`, `100.64.x`,
`::ffff:...`), invece di indirizzi pubblici diversi per visitatori diversi, è
confermato. In alternativa, un log temporaneo di `request.client.host` accanto a
`request.headers.get("x-forwarded-for")`. **]**

Se confermato, `@limiter.limit("5/minute")` non è un limite per chiamante ma **un
limite globale condiviso da tutti i visitatori**, e cambia natura: da protezione a
**arma**. Un solo attaccante che tiene 5 richieste al minuto rende inutilizzabile,
per tutti:

- `POST /users/` e `POST /bookings/` — il form di prenotazione, cioè il prodotto;
- `POST /consulenze/` e `POST /pacchetti-richieste/` — i due canali di contatto;
- **`POST /admin/login`** (`admin/__init__.py:42`) — **il coach non entra più nel
  proprio pannello**, e non ha modo di capire perché.

Costa cinque richieste HTTP al minuto. Nessuna autenticazione, nessuno strumento.

**Intervento.** Prima **verificare** (sopra). Poi impostare `FORWARDED_ALLOW_IPS`
sull'intervallo del proxy Railway — non `*`, che permetterebbe a un client di
falsificare `X-Forwarded-For` e azzerare del tutto il limite, a meno che
l'edge sovrascriva sempre l'header (da verificare con Railway).
**Costo: 1 ora più la verifica.** Nota: finché questo punto non è chiuso,
aggiungere altri rate limit (§S14) peggiora la superficie di DoS invece di
migliorarla.

---

### S6 — MEDIA — Over-serialization: `note_admin` esce da un endpoint pubblico

`backend/schemas/booking.py:56,77-95` — `backend/routers/booking.py:47`

**[VERIFICATO]** `POST /bookings/` è dichiarato `response_model=BookingResponse`,
e `BookingResponse` include `note_admin` — il campo che `models/booking.py:39`
descrive come *"riservate al coach, mai esposte allo studente"*. Campi
effettivamente restituiti a un chiamante **anonimo**:

```
['created_at','duration_hours','id','note_admin','note_cliente','package_id',
 'price_cents','replay_code','service_type','slot_id','slot_id_secondario',
 'status','user_id','vod_link']
```

Oggi non trapela nulla: alla creazione `note_admin` è `None`. Ma lo schema che
risolve il problema **esiste già** — `BookingResponseStudente`
(`schemas/booking.py:77-95`) è stato scritto apposta per escluderlo — ed è usato
solo sull'endpoint di cancellazione (`booking.py:281`). Basta la prima riga di
codice che restituisca una prenotazione esistente da questo endpoint perché la
nota interna sul cliente esca in chiaro.

**Intervento minimo.** `response_model=BookingResponseStudente` anche su
`booking.py:47`. **Costo: 5 minuti.**

---

### S7 — MEDIA — Un token di recensione non ASCII produce un 500

`backend/routers/booking.py:354` — `backend/schemas/review.py:9`

**[VERIFICATO]**

```
POST /bookings/1/recensione  {"token":"éééééééééé","voto":5}  -> 500 Internal Server Error
POST /bookings/1/recensione  {"token":"xxxxxxxxxx","voto":5}  -> 403
```

`secrets.compare_digest` solleva `TypeError` sulle stringhe non ASCII;
`ReviewCreate.token` è un `str` libero, quindi qualunque carattere arriva fino
alla riga 354. L'endpoint è pubblico. Non espone dati, ma è un errore non gestito
raggiungibile da chiunque, che sporca i log e — se un giorno ci sarà un
monitoraggio sugli errori 5xx — genera rumore a comando.

**Intervento minimo.** `token: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")` in
`schemas/review.py:9` (è il formato di `secrets.token_urlsafe`), oppure
confrontare i `bytes` con `.encode()` da entrambi i lati. **Costo: 10 minuti.**

---

### S8 — MEDIA — Il testo scritto dal pubblico entra negli embed Discord senza alcun escape

`backend/services/discord_service.py:72-78,119-122,158-161` — a confronto con
`backend/services/email_service.py:34-45`

**[VERIFICATO]** Il modulo `discord_service.py` non contiene la stringa `escape` in
nessuna forma. `nome_cliente`, `note_cliente`, `discord_tag` e `messaggio` — tutti
campi compilati da utenti non autenticati — finiscono grezzi nei campi
dell'embed.

Il confronto interno è la prova che è una svista e non una scelta: **per le email
lo stesso testo viene sanificato**, con una funzione dedicata e un commento che
spiega perché (`email_service.py:34-45`: *"un campo libero non filtrato
diventerebbe HTML attivo"*). Il ragionamento vale identico per Discord, dove il
formato attivo non è l'HTML ma il markdown: i campi degli embed rendono i **link
mascherati**, quindi una nota come

```
[Conferma la sessione](https://sito-che-non-e-quello.example)
```

arriva nel canale del coach come un collegamento cliccabile che sembra parte
della notifica di sistema. Chi lo scrive non ha bisogno di alcun account.

**Intervento minimo.** Neutralizzare `[ ] ( ) * _ \` ~` nei valori provenienti
dall'utente, o racchiuderli in un blocco di codice, dentro `_invia_embed`
(`discord_service.py:33`) che è già il punto unico di uscita.
**Costo: 30 minuti.**

---

### S9 — BASSA — Una recensione può essere lasciata per una sessione mai svolta o annullata

`backend/routers/booking.py:339-368`

**[VERIFICATO]**

```
prenotazione con slot fra 500 ore, sessione mai avvenuta
POST /bookings/{id}/recensione  con il token valido  -> 200
```

`lascia_recensione` verifica il token e l'unicità, ma **non** `booking.status` né
`slot.start_time`. Una prenotazione annullata o futura è recensibile come una
conclusa.

Impatto contenuto da due argini reali: il token non è mai restituito dall'API
(l'ho verificato: non compare fra i campi di `BookingResponse`) e arriva solo per
email dopo la sessione; e nessuna recensione è pubblica prima
dell'approvazione (`models/review.py:22`, `booking.py:323`). Resta il caso
concreto e non malevolo: un cliente che **non si presenta** riceve comunque la
richiesta di recensione (`scheduler.py:177-181` filtra su `status == "confirmed"`,
non su `no_show`) e può valutare una sessione a cui non ha partecipato.

**Intervento minimo.** Aggiungere `if booking.status != "confirmed" or fine_sessione > ora`
prima di accettare. **Costo: 20 minuti.**

---

### S10 — BASSA — Credenziali non più usate, ancora vive, lasciate in `.env`

`.env` (non versionato) — verificato incrociando con `grep -rn "getenv" backend/ scripts/`

**[VERIFICATO]** Ho elencato le chiavi del `.env` **senza stamparne i valori** e le
ho confrontate con le variabili effettivamente lette dal codice. Due sono lette da
nessuna riga del progetto:

| Chiave | Lunghezza valore | Letta da |
|---|---|---|
| `SECRET_KEY` | 25 | nessun file (il codice usa `JWT_SECRET`, `auth_service.py:19`) |
| `EMAIL_APP_PASSWORD` | 19 | nessun file (l'invio è passato all'API Gmail, `email_service.py:3-6`) |

`EMAIL_APP_PASSWORD` con quella lunghezza corrisponde al formato di una **app
password di Google** (16 caratteri più 3 spazi): è un residuo dell'epoca SMTP, e
una app password **resta valida finché non viene revocata a mano** — concede
l'invio di posta come il coach, a chiunque la ottenga.

L'esposizione oggi è locale: `.env` è in `.gitignore:1` e `git log --all -- .env`
è vuoto, quindi non è mai finito nel repository. Ma una credenziale viva che non
serve a nulla è solo rischio senza contropartita.

**Intervento minimo.** Revocare la app password dall'account Google, cancellare le
due righe. **Costo: 10 minuti.**

---

### S11 — BASSA — [SOSPETTO] Il flag `Secure` dei cookie di sessione dipende da una variabile non correlata

`backend/routers/discord_auth.py:35-40,72-75,179-184`

**[VERIFICATO nel codice]** `_IS_PRODUZIONE = (DISCORD_OAUTH_REDIRECT_URI or "").startswith("https://")`
è l'unica cosa che decide se il cookie di sessione dello studente parte con
`secure=True`. La motivazione nel commento (`:35-39`) è corretta — dietro un proxy
`request.url.scheme` è sempre `http` — ma l'indicatore scelto è **una variabile che
serve ad altro**: se un giorno viene svuotata, rinominata o riportata a `http://`
per una prova, i cookie smettono di essere `Secure` **senza che nulla lo segnali**.

**[SOSPETTO — si conferma così:** aprire il sito in produzione, fare login
Discord, e leggere i flag del cookie `student_token` negli strumenti per
sviluppatori del browser (deve mostrare `Secure` e `HttpOnly`). **]**

In positivo, e va detto: `httponly=True` e `samesite="lax"` sono impostati
correttamente su entrambi i cookie, e **`SameSite=Lax` è oggi l'unica difesa CSRF
del progetto** — non esiste alcun token anti-CSRF. Per gli endpoint in gioco
(`PATCH`, e `POST` con corpo JSON, che richiedono preflight CORS verso un elenco
di origini ristretto, `main.py:146-151`) è una difesa adeguata. Ma è un solo
strato, e questo finding è proprio il rischio che quello strato si spenga da solo.

**Intervento minimo.** Una variabile esplicita `COOKIE_SECURE` (o `ENVIRONMENT`),
con default sicuro. **Costo: 15 minuti.**

---

### S12 — BASSA — Le email dei clienti finiscono nei log applicativi a ogni invio

`backend/services/email_service.py:150,188,244,288,337`

**[VERIFICATO — osservato durante le prove]**
`logger.info(f"Email inviata a {email_cliente}")`, e altre quattro righe uguali.
Ogni conferma, promemoria e richiesta di recensione scrive un indirizzo email nei
log, che su Railway sono conservati e consultabili da chiunque abbia accesso al
progetto. È un dato personale registrato in un sistema che non è il database e non
rientra né nel job di anonimizzazione (`retention_service.py:50-55`) né nella
cancellazione GDPR (`admin/clients.py:95-133`): un cliente cancellato dal database
resta identificabile nei log.

**Intervento minimo.** Registrare l'id della prenotazione al posto
dell'indirizzo. **Costo: 15 minuti.**

---

### S13 — BASSA — [SOSPETTO] Il testo di un'eccezione di migrazione viene inoltrato su Discord

`backend/main.py:101-108`

**[VERIFICATO nel codice]** `invia_alert_sistema(..., f"... Dettaglio: {e}")`
inoltra al canale Discord il testo integrale di qualunque eccezione sollevata
durante le migrazioni, `DATABASE_URL` compreso se l'errore la contiene.

**[SOSPETTO — si conferma così:** in un ambiente di prova, impostare una
`DATABASE_URL` con password errata e leggere l'avviso che arriva su Discord: se
contiene la stringa di connessione, la password di produzione può finire in un
canale di chat. **]**

**Intervento minimo.** Inviare `type(e).__name__` e un identificativo, lasciando
il dettaglio ai log. **Costo: 10 minuti.**

---

### S14 — BASSA — Endpoint pubblici senza alcun rate limit

`backend/routers/slots.py:20` — `backend/routers/booking.py:281,310` —
`backend/routers/discord_auth.py:47,79` — `backend/main.py:172`

**[VERIFICATO — dalla tabella delle rotte generata a runtime]** Hanno un limite
solo 6 endpoint su 45. Restano senza:

- `GET /bookings/recensioni/pubbliche` — query con doppio `joinedload` e **senza
  `LIMIT`** (`booking.py:320-324`): il costo cresce con l'archivio recensioni;
- `GET /slots/` — restituisce tutti gli slot futuri liberi, senza limite;
- `GET /auth/discord/callback` — ogni chiamata innesca **due** richieste HTTP in
  uscita verso Discord (`discord_auth.py:103,119`);
- `GET /health` — esegue una query sul database a ogni colpo (`main.py:184`);
- `PATCH /bookings/{id}/cancella`.

`Limiter` è costruito senza `default_limits` (`rate_limit.py:12`), quindi
`SlowAPIMiddleware` non applica nulla di globale.

**Intervento minimo.** `default_limits` sul `Limiter` e un `LIMIT` sulla vetrina
recensioni. **Costo: 30 minuti** — ma **dopo** §S5, altrimenti si moltiplicano
gli endpoint che un singolo attaccante può spegnere per tutti.

---

### S15 — BASSA — Importare qualunque modulo del progetto carica le credenziali di produzione e le rende spendibili

`backend/database.py:11-13` — `backend/services/calendar_service.py:23` —
`backend/services/email_service.py:21` — `backend/services/discord_service.py:16`

**[VERIFICATO — mi è capitato durante questa revisione]** Cinque moduli chiamano
`load_dotenv()` **a livello di modulo**: importarne uno qualsiasi legge il `.env` e
popola le costanti globali con le credenziali reali. Uno script di verifica che
avesse stubato solo una parte delle integrazioni ha così raggiunto il Google
Calendar di produzione (404, nessun dato toccato). Con un id evento valido avrebbe
cancellato un appuntamento vero.

La suite si difende con undici `monkeypatch` in `tests/conftest.py:85-100`, ma è
una difesa **per enumerazione**: copre le funzioni note oggi e nulla impedisce che
la prossima resti scoperta.

**Intervento minimo.** Un interruttore letto una volta sola —
`INTEGRAZIONI_ATTIVE`, default spento quando `PYTEST_CURRENT_TEST` è
nell'ambiente — controllato nei tre punti unici di uscita già esistenti
(`email_service.py:81`, `discord_service.py:33`, `calendar_service.py:48`).
**Costo: 1 ora.**

---

### D1 — DA GIUSTIFICARE — Perché `POST /bookings/` accetta `user_id` dal client?

`backend/routers/booking.py:99-126` — `backend/schemas/booking.py:19`

Il commento a `:99-109` mostra che il problema è stato considerato e che la
verifica `user_id`↔`email` è deliberata. Quello che non vedo è perché il client
debba mandare `user_id`: l'email da sola identifica l'utente, il server può
risolverla, e il campo sparirebbe insieme all'oracolo di §S1.

**Domanda:** c'è un motivo per cui il frontend deve conoscere e reinviare
`user_id` — un flusso a due passi da preservare, un client esterno — oppure è
solo l'ordine storico delle due chiamate in `app.js:491,515`?

---

### D2 — DA GIUSTIFICARE — Token admin da 8 ore, senza possibilità di revoca

`backend/services/auth_service.py:21,39-51` — `frontend/js/admin.js:12,139-142`

`JWT_EXPIRE_MINUTES` vale 480 (8 ore). Il token è stateless: il commento a
`:42-43` riconosce esplicitamente che *"un token non può essere revocato prima
della scadenza"*. Il `logout()` del pannello azzera solo una variabile in memoria
(`admin.js:140`): un token già copiato resta valido fino alla scadenza e apre
l'intero archivio clienti, l'export CSV e la cancellazione definitiva.

La scelta di tenere il token **solo in memoria** (`admin.js:9-12`) è ottima e
motivata. Le 8 ore la contraddicono in parte: se il token non sopravvive a un
ricaricamento di pagina, non si capisce cosa debba servire una validità così
lunga.

**Domanda:** le 8 ore rispondono a un'esigenza reale (una sessione di lavoro
lunga sul pannello) o sono il default mai rivisto? Se è la seconda, 60 minuti
riducono la finestra di un token rubato di otto volte senza costo d'uso.

---

### D3 — DA GIUSTIFICARE — Il login admin distingue username giusto e sbagliato dal tempo di risposta

`backend/services/auth_service.py:29-36`

`if username != ADMIN_USERNAME or not ADMIN_PASSWORD_HASH: return False` esce
**prima** di `bcrypt.checkpw`, che costa un tempo misurabile (decine o centinaia
di millisecondi). La differenza rivela se lo username indovinato è quello giusto.

Su un'applicazione con un solo amministratore, e con `ADMIN_USERNAME` di 5
caratteri, il valore informativo per un attaccante è modesto.

**Domanda:** è una semplificazione consapevole? Eseguire comunque un `checkpw`
contro un hash fittizio costa due righe e chiude il canale.

---

## 3. Fuori mandato

- L'evento su Google Calendar è creato dentro la transazione aperta dalla riserva
  atomica dello slot (`booking.py:178-213`).
- `elimina_slot_obsoleti` (`availability_service.py:124-130`) carica in memoria
  l'intera tabella degli slot passati.
- `PUBLIC_BASE_URL` non è presente nel `.env` locale e ricade su
  `FRONTEND_ORIGINS.split(",")[0]` (`scheduler.py:42-45`).
- `run_migrations` (`main.py:86-108`) cattura ogni eccezione e lascia partire
  l'app con lo schema potenzialmente disallineato.

---

## 4. Non verificato

- **La produzione.** Nessun accesso a Railway: né log, né variabili d'ambiente
  effettive, né il MySQL. Da questo dipendono per intero §S5 (rate limiting per
  proxy), §S11 (flag `Secure`), la metà MySQL di §S4 e §S13 — tutti marcati
  [SOSPETTO], ciascuno con la sua procedura di conferma.
- **Le concorrenze, provate davvero.** §S3 è dimostrato per lettura del codice, non
  con due richieste realmente simultanee: SQLite con `StaticPool` serializza
  tutto e non può riprodurre la corsa. Servirebbe una prova contro MySQL con due
  connessioni.
- **La configurazione di rete di Railway.** Se l'edge sovrascriva sempre
  `X-Forwarded-For` o lo accodi soltanto: determina se, chiuso §S5, il limite
  diventi falsificabile dal client. Va chiesto o provato.
- **La superficie Google.** Non ho verificato gli scope effettivamente concessi ai
  due refresh token né i permessi del service account sul calendario. Se lo scope
  Drive fosse più ampio del necessario, `DRIVE_REFRESH_TOKEN` varrebbe più di
  quanto il codice lasci intendere.
- **I contenuti di `frontend/privacy.html`** rispetto a quanto il sistema fa
  davvero (§S12, log; §S15): non li ho confrontati.
- **Dipendenze e CVE note.** Nessun `pip-audit` eseguito: `requirements.txt` è
  interamente pinnato, il che è positivo, ma non ho verificato se qualche versione
  fissata abbia vulnerabilità pubbliche.
- **Un'analisi statica.** Nessun `bandit`, `semgrep` o simile: tutto quanto sopra
  è lettura più prova manuale.
- **Il codice in `scripts/`.** Fuori dal percorso servito, non l'ho esaminato.
- **Gli altri report in `audit/`.** Non letti, come da vincolo.
