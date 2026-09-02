# Riallineamento variabili Railway — runbook operativo

**Data:** 2026-09-02 · **Origine:** esito della domanda `U1` della revisione documentale
(vedi `REVISIONE_2026-09-01.md`, sezione "Fase 4b").

## ✅ STATO: ESEGUITO il 2026-09-02

**Gli STEP 1-5 sono stati applicati.** Il servizio su Railway risponde correttamente dopo il
redeploy. Restano aperti due punti di verifica e il passo facoltativo.

| Step | Stato |
|---|---|
| STEP 1 — aggiungere 3 variabili (app) | ✅ fatto |
| STEP 2 — correggere 3 variabili (app) + redirect URI su Discord | ✅ fatto |
| STEP 3 — rimuovere 2 variabili (app) | ✅ fatto |
| STEP 4 — rimuovere 5 variabili (MySQL) | ✅ fatto |
| STEP 5 — non toccare il resto | ✅ rispettato |
| STEP 6 — verifica | ⚠️ **5 punti su 6 verificati** — resta solo il punto 6, rimandato |
| Passo facoltativo — consolidamento su un solo servizio | ⏸️ **aperto, rimandato** |

**Risultati concreti già confermati dalla verifica:**

- **Il login Discord in produzione funziona.** Era il problema `P1`: le credenziali OAuth non
  esistevano su nessuno dei due servizi. È anche la chiusura di un punto che
  `STATO_PROGETTO.md` §9 elencava fra i "non ancora verificati" da settimane.
- **I cookie di sessione hanno il flag `Secure`.** Era il problema `P4`. Di conseguenza
  l'affermazione di `README.md:326` ("`secure` in produzione"), che al momento della revisione
  era **falsa**, adesso è **vera**: non richiede più correzione.
- **Il login admin funziona** dopo la rimozione di `ADMIN_PASSWORD` in chiaro dal servizio
  MySQL (`P7`), confermando che `ADMIN_PASSWORD_HASH` risolve correttamente.
- **Le migrazioni girano pulite** all'avvio, nessun alert di sistema.

Il documento resta scritto al futuro ("da fare") perché è la traccia di *cosa è stato fatto e
perché*: serve a ricostruire il ragionamento, non solo l'elenco delle azioni.

---

## Stato di partenza (com'era prima dell'intervento del 2026-09-02)

Il progetto Railway ha **due servizi**: quello applicativo e quello **MySQL**. La
configurazione è divisa fra i due senza un criterio sistematico:

- **servizio app**: 26 variabili — 13 valori letterali e 13 *riferimenti* nella forma
  `${{MySQL.NOME}}`, cioè puntatori a variabili definite sul servizio MySQL;
- **servizio MySQL**: 25 variabili — le proprie di Railway (`MYSQL*`) **più** una dozzina di
  variabili applicative che con il database non c'entrano nulla.

Confronto con il codice: il progetto legge **32** variabili d'ambiente (elenco completo in
`REVISIONE_2026-09-01.md` §1.6). Di queste **23 sono presenti e risolvono correttamente**,
**9 sono assenti** e **5 chiavi sono impostate senza che nessuna riga di codice le legga**.

Tre problemi hanno un effetto concreto e osservabile in produzione:

1. il **login Discord non può funzionare** (mancano le credenziali OAuth);
2. le **email di richiesta recensione contengono un link non cliccabile**;
3. i **cookie di sessione vengono emessi senza il flag `Secure`**.

Il resto è pulizia.

---

## Prima di iniziare — tre avvertenze

**A. Ogni modifica alle variabili fa ripartire il servizio.** Railway riavvia l'app a ogni
salvataggio. Conviene fare tutte le modifiche di un servizio **in un colpo solo** con il Raw
Editor, invece di una alla volta: un riavvio invece di dieci.

**B. Prima di cancellare `ADMIN_PASSWORD`, salva quel valore.** È la password del pannello
admin in chiaro, ed è l'unico posto dove esiste in forma leggibile: `ADMIN_PASSWORD_HASH`
contiene solo l'hash bcrypt, da cui la password **non è ricavabile**. Copiala nel tuo gestore
di password *prima* di eliminarla, altrimenti resti fuori dal pannello senza poterla
recuperare (dovresti rigenerare l'hash con `scripts/hash_admin_password.py`).

**C. Le migrazioni girano a ogni avvio.** `backend/main.py` esegue `alembic upgrade head`
all'avvio dell'app. Un riavvio provocato da un cambio di variabile è quindi anche un momento in
cui il database può cambiare struttura. Oggi non ci sono migrazioni in sospeso, quindi non
succederà nulla — ma è il motivo per cui conviene guardare i log dopo il primo riavvio.

---

## STEP 1 — Servizio APP: aggiungere 3 variabili

| Variabile | Valore da impostare |
|---|---|
| `DISCORD_CLIENT_ID` | il Client ID dell'app OAuth2 Discord |
| `DISCORD_CLIENT_SECRET` | il Client Secret della stessa app |
| `PUBLIC_BASE_URL` | `https://vgc-coaching-production.up.railway.app` |

**Perché `DISCORD_CLIENT_ID`/`SECRET`.** Non esistono su **nessuno** dei due servizi. Il codice
le legge in `backend/routers/discord_auth.py:29-30`; senza, `discord_login()` costruisce l'URL
di autorizzazione con `client_id=None` e Discord rifiuta la richiesta. Il bottone "Accedi con
Discord" non può portare a un login riuscito. Questo spiega perché "login Discord end-to-end in
produzione" è fra i *non verificati* di `STATO_PROGETTO.md` da settimane: non è solo non
verificato, non funziona.

Dove prenderle: Discord Developer Portal → la tua applicazione → **OAuth2 → General**.

**Perché `PUBLIC_BASE_URL`.** Serve a costruire il link assoluto nelle email di richiesta
recensione (`backend/scheduler.py:38-41` e `:201`). Se manca, il codice ricade sulla prima
origine di `FRONTEND_ORIGINS` — che oggi è un hostname **senza schema**, quindi produce un
link tipo `vgc-coaching-production.up.railway.app/static/recensione.html?...` che nessun client
email rende cliccabile.

> **Conseguenza da sapere:** le richieste di recensione già inviate **non verranno rimandate**.
> Il job filtra su `Booking.review_email_sent == False`, e quelle prenotazioni hanno già il
> flag a `True`. Correggere la variabile sistema le email **future**; per recuperare le
> sessioni passate servirebbe rimettere `review_email_sent = False` su quelle righe, che è una
> modifica al database e va decisa a parte.

---

## STEP 2 — Servizio APP: correggere 3 variabili

| Variabile | Valore attuale | Valore corretto |
|---|---|---|
| `FRONTEND_ORIGINS` | `vgc-coaching-production.up.railway.app` | `https://vgc-coaching-production.up.railway.app` |
| `DISCORD_OAUTH_REDIRECT_URI` | `http://vgc-coaching-production.up.railway.app/auth/discord/callback` | `https://vgc-coaching-production.up.railway.app/auth/discord/callback` |
| `REMINDER_CHECK_INTERNAL_MINUTES` | `5` | **rinominare** in `REMINDER_CHECK_INTERVAL_MINUTES` (valore `5` invariato) |

**`FRONTEND_ORIGINS` — manca lo schema.** `CORSMiddleware` confronta i valori di
`allow_origins` con l'header `Origin` del browser, che ha sempre la forma `https://host`: un
hostname nudo non combacia mai con nulla. Oggi è innocuo — frontend e API stanno sulla stessa
origine, quindi il browser non fa richieste cross-origin — ma significa che la configurazione
CORS non autorizza niente, e che una seconda origine non funzionerebbe. È anche la causa del
link rotto dello STEP 1.

**`DISCORD_OAUTH_REDIRECT_URI` — deve essere `https`.** Due motivi distinti:

1. **Sicurezza.** `backend/routers/discord_auth.py:43` deduce l'ambiente proprio da questa
   variabile: `_IS_PRODUZIONE = DISCORD_OAUTH_REDIRECT_URI.startswith("https://")`. Oggi è
   `False`, quindi **entrambi** i cookie — quello di sessione studente e quello di stato OAuth
   — vengono emessi **senza il flag `Secure`** (righe 103 e 249). `README.md:326` afferma il
   contrario ("`secure` in produzione"): oggi non è vero. Railway termina l'HTTPS a monte,
   quindi l'app non può dedurlo dalla richiesta — questa variabile è l'unico segnale.
2. **Funzionamento.** Discord accetta redirect URI in `http://` solo per `localhost`. Anche
   con le credenziali dello STEP 1, con un URI `http://` su dominio pubblico il login
   fallirebbe comunque.

> ⚠️ **Da fare insieme, non dopo:** aggiorna lo stesso URI anche sul **Discord Developer
> Portal → OAuth2 → Redirects**. I due valori devono coincidere carattere per carattere,
> altrimenti Discord risponde `redirect_uri_mismatch`. Puoi tenere entrambi (`http` e `https`)
> nel portale durante la transizione, ma su Railway deve restare solo `https`.

**`REMINDER_CHECK_INTERNAL_MINUTES` — refuso nel nome.** Il codice legge
`REMINDER_CHECK_INTERVAL_MINUTES` (INTER**V**AL), su Railway c'è INTER**N**AL. La variabile
impostata non viene quindi mai letta e lo scheduler usa il default. Oggi non si nota perché il
default vale anch'esso `5`, ma chiunque provasse a cambiarla vedrebbe il sistema ignorarlo.

---

## STEP 3 — Servizio APP: rimuovere 2 variabili

| Variabile | Perché va via |
|---|---|
| `SECRET_KEY` | Nessuna riga del progetto la legge. Verificato: `grep 'getenv("SECRET_KEY")'` su tutto il repository → zero risultati. Non va confusa con `JWT_SECRET`, che è quella davvero usata per firmare i token |
| `PAYPAL_EMAIL` | Residuo del flusso di pagamento PayPal, rimosso dal codice ad agosto (step P0-3 di `ROADMAP.md`). Il codice non la nomina più da nessuna parte |

Entrambe sono impostate come riferimenti `${{MySQL....}}`: qui si cancella il puntatore, allo
STEP 4 si cancella il valore puntato.

---

## STEP 4 — Servizio MYSQL: rimuovere 5 variabili applicative

Sono tutte variabili **applicative** finite sul servizio del database. Nessuna serve al
database, e nessuna delle cinque è letta dal codice nella posizione in cui si trova.

| Variabile | Perché va via |
|---|---|
| `ADMIN_PASSWORD` | **Password del pannello admin in chiaro.** Sostituita da `ADMIN_PASSWORD_HASH` (bcrypt) nella migrazione di agosto; `scripts/hash_admin_password.py:70` istruisce esplicitamente a rimuoverla da Railway, e `STATO_PROGETTO.md` §11.5 dà lo scambio per fatto — non lo era. Il codice non la legge, quindi non rompe nulla: il punto è che rende inutile aver messo la password sotto hash. **Salvala prima** (avvertenza B) |
| `GMAIL_REFRESH_TOKEN` | Copia **divergente** e non referenziata. Il token vivo è quello letterale sul servizio app; questo è un valore **diverso** (verificato per hash), verosimilmente un token vecchio rimasto da una re-autorizzazione precedente. Tenerlo è peggio che inutile: al prossimo `reauth_gmail.py` il posto "naturale" dove incollare il token nuovo sarebbe proprio questo, quello sbagliato — e l'invio email resterebbe fermo senza spiegazione |
| `GMAIL_CLIENT_SECRET` | Copia **identica** a quella sul servizio app, ma non referenziata da nessuno. Innocua oggi, stessa trappola di sopra domani |
| `SECRET_KEY` | Il valore puntato dal riferimento rimosso allo STEP 3. Mai letto |
| `PAYPAL_EMAIL` | Idem |

---

## STEP 5 — Cosa NON toccare

### Sul servizio MYSQL: tutte le variabili `MYSQL*`

`MYSQLDATABASE`, `MYSQLHOST`, `MYSQLPASSWORD`, `MYSQLPORT`, `MYSQLUSER`, `MYSQL_DATABASE`,
`MYSQL_PUBLIC_URL`, `MYSQL_ROOT_PASSWORD`, `MYSQL_URL`.

Le genera e le gestisce Railway, non il nostro codice. In particolare:

- **`MYSQL_ROOT_PASSWORD` e `MYSQL_DATABASE` sono lette dal container MySQL stesso** all'avvio
  (sono le variabili standard dell'immagine ufficiale `mysql`, che le usa per impostare la
  password di root e creare il database). Rimuoverle **rompe il database**.
- `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`, `MYSQL_URL`,
  `MYSQL_PUBLIC_URL` sono alias di comodo che Railway crea perché altri servizi possano
  referenziarli. La nostra app non li usa (usa `DATABASE_URL`), quindi in teoria sarebbero
  superflui — **ma non li toccherei comunque**: sono gestiti dalla piattaforma, la dashboard
  Railway e la scheda "Connect" ci si appoggiano, e potrebbero essere rigenerati da soli. Il
  guadagno di rimuoverli è zero, il rischio no.

Questo è l'unico punto in cui non seguo alla lettera la richiesta di "pulizia completa": la
pulizia vera su questo servizio sono le 5 variabili dello STEP 4, che sono roba nostra finita
nel posto sbagliato. Le `MYSQL*` sono roba di Railway nel posto giusto.

### Sul servizio MYSQL: le 11 variabili applicative che invece servono

`ADMIN_USERNAME`, `DATABASE_URL`, `EMAIL_ADMIN`, `EMAIL_MITTENTE`, `GMAIL_CLIENT_ID`,
`GOOGLE_CALENDAR_ID`, `GOOGLE_PRIVATE_KEY`, `GOOGLE_SERVICE_ACCOUNT_EMAIL`, `JWT_ALGORITHM`,
`JWT_EXPIRE_MINUTES`, `JWT_SECRET`.

Sono referenziate dal servizio app e **risolvono correttamente** (verificato: i valori
esistono). Stanno in una posizione discutibile (vedi "Passo facoltativo" in fondo), ma
funzionano: **non vanno rimosse**. `DATABASE_URL` in particolare è ben formata — driver
`mysql+pymysql`, host della rete privata interna, porta e database corretti.

### Sul servizio APP: tutto il resto

`ADMIN_PASSWORD_HASH` (hash bcrypt, 60 caratteri, corretto), `DRIVE_REFRESH_TOKEN`,
`GOOGLE_DRIVE_BACKUP_FOLDER_ID`, `DISCORD_WEBHOOK_URL`, `GMAIL_CLIENT_SECRET`,
`GMAIL_REFRESH_TOKEN`, `COACH_DISCORD_TAG`, `COACH_TELEGRAM_CONTACT`, `BACKUP_RETENTION_DAYS`,
`REMINDER_HOURS_BEFORE`, e gli 11 riferimenti `${{MySQL....}}` rimasti.

### Le 6 variabili assenti che vanno lasciate assenti

`LOG_LEVEL` (default `INFO`), `RETENTION_MONTHS` (24), `REVIEW_CHECK_INTERVAL_MINUTES` (60),
`CALENDAR_SYNC_INTERVAL_MINUTES` (60), `GMAIL_HEALTHCHECK_INTERVAL_HOURS` (24) e
`REMINDER_CHECK_INTERVAL_MINUTES` (5, dopo la rinomina dello STEP 2).

**Non serve impostarle: i default scritti nel codice *sono* i valori voluti.** Aggiungerle
significherebbe solo avere gli stessi numeri scritti in due posti che possono divergere.
Va corretto semmai `STATO_PROGETTO.md` §5, che le presenta come configurate — è già registrato
come rilievo `D5` nella revisione documentale.

---

## STEP 6 — Verifica dopo il riavvio

Esito del 2026-09-02: **4 punti verificati su 6**.

| # | Controllo | Esito |
|---|---|---|
| 1 | Log di avvio, migrazioni | ✅ **verificato** |
| 2 | `GET /health` | ✅ **verificato** |
| 3 | Login admin | ✅ **verificato** |
| 4 | Flag `Secure` sui cookie | ✅ **verificato** |
| 5 | Login Discord end-to-end | ✅ **verificato — ora funziona** |
| 6 | Link di recensione nell'email | ⏸️ **rimandato** — nessuna sessione ancora conclusa |

**1. Log di avvio** — cerca `Migrazioni eseguite con successo`. Se compare `Errore migrazioni`
o arriva un alert Discord 🚨, fermati e leggi lo stack trace prima di procedere.
→ ✅ Nessun errore.

**2. `GET /health`** sul dominio di produzione → deve rispondere `{"status":"ok"}`. Controlla
anche il database, non solo che il processo sia vivo.
→ ✅ **Verificato.** L'endpoint risponde correttamente, quindi anche la connessione al
database è viva (esegue un `SELECT 1` reale, non un semplice "processo acceso").

Nota su come si è arrivati qui, perché è un equivoco facile da rifare: il controllo era stato
cercato nei **log** di Railway e non trovato. Non era un difetto — questo punto non consiste
nel cercare qualcosa nei log, ma nel **fare la richiesta**. L'endpoint non compariva
semplicemente perché nessuno lo stava chiamando, il che è a sua volta la conferma osservativa
che **nessun monitor esterno è collegato** (`STATO_PROGETTO.md` §9 lo dichiarava; è la domanda
`U8` della revisione).

Se poi colleghi un monitor esterno (UptimeRobot o simile, il passo che `README.md:309`
raccomanda come step 7 del deploy), da quel momento la riga comparirà nei log a intervalli
regolari e la sua **assenza** diventerà a sua volta un segnale utile.

**3. Login admin** → deve funzionare con la password di sempre. Se non funziona,
`ADMIN_USERNAME` o `ADMIN_PASSWORD_HASH` non stanno risolvendo: rimetti i valori prima di
indagare oltre.
→ ✅ Funziona. Conferma che la rimozione di `ADMIN_PASSWORD` in chiaro (`P7`) non ha rotto
nulla, come previsto: il codice legge solo l'hash.

**4. Flag `Secure` sui cookie** → DevTools → Application → Cookies: dopo un login Discord
riuscito, `student_token` deve avere la spunta su `Secure` e su `HttpOnly`.
→ ✅ Verificato. `P4` chiuso.

**5. Login Discord end-to-end** → il percorso che non aveva mai funzionato.
→ ✅ **Funziona.** `P1` chiuso, e con esso un punto che `STATO_PROGETTO.md` §9 e §11 elencavano
fra i "non ancora verificati" fin dal 25/08.

**6. Link di recensione** → alla prima sessione conclusa dopo la modifica, controlla che
l'email contenga un link cliccabile che inizia con `https://`.
→ ⏸️ **Non ancora verificabile:** serve una prenotazione la cui sessione sia già finita e per
cui la richiesta di recensione non sia ancora partita. Nessun modulo compilato finora.

Da tenere presente quando arriverà il momento: il job manda l'email **una volta sola per
prenotazione** (`Booking.review_email_sent`), e gira ogni 60 minuti — quindi l'email arriva
entro un'ora dalla fine della sessione, non subito. Se il link risultasse ancora rotto,
il sospetto numero uno è `PUBLIC_BASE_URL` scritta senza `https://`.

---

## Passo facoltativo — consolidare la configurazione su un solo servizio

**Non necessario, ma è la causa del problema `GMAIL_REFRESH_TOKEN` divergente.**

Oggi le credenziali Gmail sono spezzate a metà senza un criterio: `GMAIL_CLIENT_ID` sta sul
servizio MySQL ed è referenziata, mentre `GMAIL_CLIENT_SECRET` e `GMAIL_REFRESH_TOKEN` sono
letterali sul servizio app. È esattamente questa asimmetria ad aver prodotto due copie
divergenti dello stesso token senza che nessuno se ne accorgesse.

La regola che eliminerebbe la classe di problema: **sul servizio MySQL restano solo le
variabili che Railway genera da sé; tutto ciò che riguarda l'applicazione vive sul servizio
app.** In pratica significherebbe spostare le 11 variabili applicative dal servizio MySQL a
quello app come valori letterali, e cancellare i riferimenti corrispondenti.

Perché è marcato facoltativo: sono 11 valori da spostare a mano, alcuni lunghi
(`GOOGLE_PRIVATE_KEY` è ~1760 caratteri con `\n` letterali che vanno preservati esatti), e un
errore di copia manda offline l'app. Il guadagno è di manutenibilità, non di funzionamento.
Se lo fai, fallo in un momento tranquillo e **dopo** aver verificato che gli STEP 1-6 sono a
posto — non tutto insieme.

---

## Riepilogo in una tabella

| Azione | Servizio | Variabili | N. |
|---|---|---|---|
| **Aggiungere** | app | `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `PUBLIC_BASE_URL` | 3 |
| **Modificare** | app | `FRONTEND_ORIGINS`, `DISCORD_OAUTH_REDIRECT_URI`, `REMINDER_CHECK_INTERNAL_MINUTES`→`...INTERVAL...` | 3 |
| **Rimuovere** | app | `SECRET_KEY`, `PAYPAL_EMAIL` | 2 |
| **Rimuovere** | MySQL | `ADMIN_PASSWORD`, `GMAIL_REFRESH_TOKEN`, `GMAIL_CLIENT_SECRET`, `SECRET_KEY`, `PAYPAL_EMAIL` | 5 |
| **Invariato** | MySQL | tutte le `MYSQL*` (gestite da Railway) | 9 |
| **Invariato** | MySQL | le 11 variabili applicative referenziate e funzionanti | 11 |
| **Invariato** | app | i 13 letterali corretti e gli 11 riferimenti rimasti | — |
| **Invariato** | — | le 6 variabili assenti coperte da default | 6 |

**Fuori dalla dashboard Railway, ma parte dello stesso intervento:** aggiornare il redirect URI
su Discord Developer Portal (STEP 2) e mettere al sicuro la password admin prima di cancellarla
(avvertenza B).
