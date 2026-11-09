# PROBLEMI

Elenco dei problemi concreti ricavati da `AUDIT.md` e dalla rilettura diretta del codice
(`backend/`, `frontend/js/`, `scripts/`, `alembic/`, i file di configurazione, i tag e i campi
rilevanti dei cinque HTML). Nessun file è stato modificato.

Ogni voce riporta: dove sta, **cosa può succedere in concreto** (non "è brutto"), la gravità e
quali altri punti verrebbero toccati dalla correzione.

- **BLOCCA** — una funzione dichiarata rompe, perde dati o crea uno stato incoerente nel database.
- **RISCHIOSO** — funziona finché nulla va storto; il guasto è silenzioso o si manifesta altrove.
- **COSMETICO** — non produce guasti: codice morto, incoerenze visive, commenti che mentono.

Ordinato per gravità decrescente. All'interno di ogni fascia, prima i problemi di comportamento,
poi quelli di struttura.

---

## BLOCCA

### B1. La cancellazione di un cliente fallisce con 500 se ha usato un pacchetto

**Dove** — `backend/routers/admin/clients.py:115-132`, con `backend/database.py:28`
(`autoflush=False`) e `alembic/versions/b3d84a19e6f2_crea_tabella_packages.py:41`
(`fk_bookings_package_id`).

**Cosa succede** — `elimina_cliente` accoda le prenotazioni con `db.delete(p)` (`:123`), che
*non* emettono SQL: restano pendenti nella sessione. Subito dopo, `:128` esegue un **bulk delete**
`db.query(Package).filter(...).delete()`, che invece va al database immediatamente. Con
`autoflush=False` (`backend/database.py:28`) SQLAlchemy non svuota le operazioni pendenti prima di
un bulk delete, quindi l'ordine reale degli statement è:

1. `DELETE FROM client_notes WHERE user_id = X`
2. `DELETE FROM packages WHERE user_id = X` ← qui
3. `DELETE FROM bookings ...` (solo al `db.commit()` di `:132`)

Se il cliente ha almeno una prenotazione con `package_id` valorizzato, al punto 2 le righe di
`bookings` esistono ancora e referenziano il pacchetto: MySQL rifiuta con errore 1451 di vincolo di
chiave esterna. Risultato: **500 al pannello, cliente non cancellato, transazione persa**. È
l'endpoint che implementa il diritto alla cancellazione dichiarato nell'informativa privacy
(`clients.py:107-108`), quindi non è una funzione secondaria.

Perché non emerge dai test: la suite gira su SQLite in memoria (`tests/conftest.py:32-36`) che non
attiva `PRAGMA foreign_keys`, e `tests/test_admin.py:49-52` cancella un cliente con una nota ma
**senza pacchetto**. Il caso rotto non è coperto né osservabile in test.

**Gravità** — BLOCCA.

**Impatto della correzione** — un `db.flush()` prima di `:127`, oppure sostituire i due bulk delete
con cicli `db.delete(...)`, oppure invertire l'ordine. Tocca solo `clients.py:116-128`. Va aggiunto
un test con pacchetto **e** l'attivazione delle FK su SQLite in `tests/conftest.py` (un listener
`PRAGMA foreign_keys=ON`), altrimenti la regressione resta invisibile come oggi. L'attivazione delle
FK può far emergere altri punti oggi silenziosi nella stessa suite.

---

### B2. Uno slot bloccato non è più né sbloccabile né eliminabile dal pannello

**Dove** — `backend/services/calendar_service.py:224-227`,
`backend/services/availability_service.py:166-168`,
`backend/routers/admin/availability.py:75-107` e `:213-230`, `frontend/js/admin.js:845-861`.

**Cosa succede** — `blocked_external` e `blocked_admin` vengono scritti **solo a `True`**. Non esiste
in tutto il backend una riga che li riporti a `False` (verificato con ricerca su `backend/`: le
uniche scritture sono `calendar_service.py:226` e `availability_service.py:168`). Di conseguenza:

- se il coach cancella l'impegno dal proprio Google Calendar, la sincronizzazione successiva
  (`sincronizza_slot_con_calendario`) non riapre lo slot: passa in rassegna solo gli slot con
  `is_available == True` (`calendar_service.py:204-207`), e quello bloccato non ne fa più parte;
- se il coach elimina un blocco eccezionale, `elimina_blocco_eccezionale`
  (`availability.py:213-230`) rimuove solo la riga di `availability_exceptions`: gli slot restano
  bloccati (il docstring `:221-222` lo dichiara, ma non esiste il "a mano" a cui rimanda);
- **non c'è nemmeno una via d'uscita per eliminazione**: `admin.js:855` mostra il pulsante 🗑 Elimina
  solo quando `s.disponibile` è vero, quindi proprio gli slot bloccati non hanno alcun bottone.

Effetto concreto: un errore di sincronizzazione, o una settimana di ferie inserita per sbaglio, toglie
quegli orari dalla vendita **per sempre**, senza alcuna azione possibile dall'interfaccia. L'unico
rimedio è un `UPDATE` a mano sul database di produzione.

**Gravità** — BLOCCA.

**Impatto della correzione** — serve una decisione di prodotto (riapertura automatica alla sync vs.
azione manuale) e poi: un endpoint di sblocco in `routers/admin/availability.py`, il bottone
corrispondente in `admin.js:845-861`, ed eventualmente estendere la query di
`calendar_service.py:204` agli slot con `blocked_external=True` per riaprire quelli il cui evento è
sparito. Toccati: 1 router, 1 servizio, 1 file JS, `frontend/admin.html` se serve un secondo bottone.
Nessuna migrazione: le colonne esistono già.

---

### B3. Il cambio di stato di una prenotazione non è una macchina a stati: può liberare lo slot di un altro cliente

**Dove** — `backend/routers/admin/bookings.py:105-120`, con
`backend/services/booking_service.py:24-31`.

**Cosa succede** — `aggiorna_stato` assegna `prenotazione.status = dati.nuovo_stato` (`:113`) senza
guardare lo stato **di partenza**, e chiama `libera_slot_prenotazione` ogni volta che il nuovo stato
è `cancelled` (`:115-117`). Due conseguenze verificabili:

1. **Doppia liberazione.** Prenotazione A cancellata → slot liberato. Il cliente B prenota lo stesso
   slot. Se l'admin cancella di nuovo A (pagina rimasta aperta con dati vecchi, doppio click, o
   chiamata diretta all'API), `libera_slot_prenotazione` rimette `is_available = True`
   (`booking_service.py:26`) su uno slot che ora appartiene a B. Da quel momento **due prenotazioni
   confermate insistono sullo stesso orario**: il claim atomico di `booking.py:178-187`, che è la
   difesa contro la doppia prenotazione, viene aggirato da questo percorso.
2. **Riconferma senza slot.** `cancelled` → `confirmed` è ammesso dallo schema
   (`schemas/booking.py:68`) e non ri-riserva nulla: la prenotazione torna `confirmed` mentre lo slot
   resta `is_available = True` e prenotabile da chiunque. Stesso risultato del punto 1, per un'altra
   strada.

Nessuno dei due casi produce un errore: il pannello risponde `{"message": "Stato aggiornato a ..."}`.

**Gravità** — BLOCCA (integrità dei dati, e il conflitto si scopre solo quando i due clienti si
presentano).

**Impatto della correzione** — introdurre le transizioni ammesse in `bookings.py:105-120`:
liberare lo slot solo su `confirmed → cancelled`, e rifiutare (o ri-riservare atomicamente) la
`cancelled → confirmed`. Tocca `admin/bookings.py` e, se si vuole restare coerenti, il percorso
self-service `booking.py:281-307`, che il controllo `status != "confirmed"` (`:298-299`) già oggi
fa correttamente — è il pannello ad essere l'anello debole. Da riflettere su
`frontend/js/admin.js:427-441`, che non mostra alcun errore (vedi R3).

---

## RISCHIOSO

### R1. Conoscere l'email di un cliente basta per prenotare a suo nome

**Dove** — `backend/routers/users.py:104-137` (`get_or_create_user` + `POST /users/`),
`backend/routers/booking.py:99-126`.

**Cosa succede** — il commento in `booking.py:99-109` dichiara che, senza login, la corrispondenza
email↔`user_id` "alza il costo dell'attacco da *indovina un id* a *conosci già l'email della
vittima*". Il costo però non è alzato, perché `POST /users/` è pubblico, si comporta da *get or
create* (`users.py:111-113`) e **restituisce l'id dell'utente esistente** quando l'email è già nota.
Chi conosce l'email ottiene quindi l'`user_id` dallo stesso endpoint pubblico, e ha entrambi i valori
che `booking.py:125` confronta. Da lì può creare prenotazioni a nome della vittima: le consuma il
limite di 2 prenotazioni attive (`booking.py:156-165`), le manda email di conferma
(`booking.py:250-257`) e occupa slot reali.

Il limite di 5 richieste/minuto per IP (`users.py:133`, `booking.py:48`) rallenta ma non impedisce,
perché servono solo due chiamate.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — è una decisione di prodotto prima che di codice (rendere obbligatorio
il login per prenotare, o introdurre una conferma via email del guest checkout). Il minimo
difendibile — non restituire l'id di un utente **preesistente** su `POST /users/` — romperebbe il
flusso di `frontend/js/app.js:491-531`, che si aspetta sempre un id. Toccati: `users.py:104-137`,
`booking.py:110-126`, `app.js:483-545`, più i test `tests/test_booking.py` e `tests/test_users.py`.

---

### R2. Il limite di 2 prenotazioni attive si aggira cambiando email

**Dove** — `backend/routers/booking.py:31`, `:156-165`.

**Cosa succede** — il conteggio è per `user.id`, e per un ospite l'identità è l'email
(`users.py:111`). Una seconda email crea un secondo utente e riparte da zero. Il commento
`booking.py:153-155` presenta il limite come misura anti-abuso ("senza pagamento anticipato nulla
impedirebbe a una sola persona di occupare più slot"), ma per gli ospiti — cioè per il flusso in cui
il rischio esiste — non impedisce niente. Per gli studenti loggati, invece, funziona.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — non risolvibile senza una decisione di prodotto (limite per IP, o
prenotazione riservata agli account). Va almeno reso esplicito nel commento cosa il limite protegge
davvero. Toccato: `booking.py:31,153-165`.

---

### R3. Il pannello admin non controlla mai l'esito delle richieste: dopo la scadenza del token mostra pagine vuote senza dirlo

**Dove** — `frontend/js/admin.js`: `caricaDashboard:247`, `caricaAnalytics:308`,
`caricaPrenotazioni:345`, `caricaClienti:469`, `caricaPacchetti:709`, `caricaRecensioni:752`,
`caricaSlots:816`, `caricaRegole:898`, `caricaBlocchi:994`; e le scritture
`aggiornaStato:432`, `modificaNota:454`, `impostaApprovazioneRecensione:801`, `eliminaRegola:980`,
`eliminaBlocco:1075`, `creaSlot:1095`.

**Cosa succede** — nessuna di queste chiamate guarda `res.ok`. Il token admin dura
`JWT_EXPIRE_MINUTES` (480, `auth_service.py:21`) e vive solo in memoria (`admin.js:12`); alla
scadenza ogni endpoint risponde 401 con `{"detail": "Token non valido o scaduto"}`
(`routers/admin/__init__.py:32-36`). Il pannello:

- nelle letture, fa `dati.items` su un oggetto d'errore → `undefined.length` → eccezione → `catch`
  che scrive solo in console (`admin.js:422-424`, `531-533`, ecc.). **In pagina non compare nulla**:
  restano i dati vecchi o il contenitore vuoto. Il coach vede un pannello che sembra dire "non ci
  sono prenotazioni";
- nelle scritture è peggio: `aggiornaStato` (`:432-437`) fa `await fetch(...)` e poi ricarica la
  lista **come se avesse funzionato**. L'admin clicca "✗ Cancella", non vede errori, e la
  prenotazione è ancora lì. Stessa cosa per la nota, l'approvazione di una recensione,
  l'eliminazione di regole e blocchi.

`creaSlot` (`:1095-1104`) è il caso più netto: non controlla nulla, svuota il campo data
(`:1103`) e ricarica la lista. Un 400 "Questo slot si sovrappone a uno slot già esistente"
(`slots.py:58-61`) o un 422 sulla durata (`schemas/slots.py:39-44`) **spariscono senza traccia**, e
l'interfaccia si comporta esattamente come in caso di successo.

**Gravità** — RISCHIOSO (nessun dato viene corrotto, ma il coach agisce su informazioni false).

**Impatto della correzione** — un wrapper unico attorno a `fetch` in `admin.js` che controlli
`res.ok`, gestisca il 401 chiamando `logout()` (`:139-143`) e mostri il `detail` altrove. Tocca tutte
e 26 le chiamate del file, ma con una funzione sola: il cambio è meccanico e concentrato in
`admin.js`. Nessun impatto sul backend.

---

### R4. La chiamata a Google Calendar avviene dentro la transazione che tiene lo slot bloccato, senza timeout

**Dove** — `backend/routers/booking.py:178-245`, `backend/services/calendar_service.py:129-132`.

**Cosa succede** — l'ordine in `create_booking` è: `UPDATE slots SET is_available=0 ...` (`:178-182`)
→ [eventuale secondo slot, `:192-200`] → `crea_evento_calendario(...)` (`:213-221`) → `db.commit()`
(`:245`). L'`UPDATE` non committato tiene un **lock di riga** su `slots` per tutta la durata della
chiamata HTTP a Google. A differenza del webhook Discord (`discord_service.py:47`, `timeout=5`) e
dello scambio OAuth Discord (`discord_auth.py:114`, `timeout=10`), qui **non è impostato alcun
timeout**: `googleapiclient` usa il timeout di default del socket, cioè nessuno.

Se l'API Calendar è lenta o appesa, la richiesta di prenotazione resta aperta a tempo indeterminato
tenendo il lock; le richieste concorrenti sullo stesso slot si accodano sul lock, e le connessioni
del pool si esauriscono. Il commento a `:211-212` copre il caso "errore" (l'eccezione è catturata in
`calendar_service.py:137-139` e la prenotazione prosegue senza evento) ma non il caso "lenta", che è
quello che consuma risorse.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — due strade indipendenti: (a) passare un timeout esplicito al client
Google in `calendar_service.py:48-50`, che è un cambio locale; (b) spostare la creazione dell'evento
**dopo** il commit, insieme alle notifiche (`booking.py:250-276`), aggiornando poi
`calendar_event_id` con una seconda scrittura. La (b) tocca `booking.py:213-246` e cambia il
significato di `calendar_event_id` temporaneamente `None`, quindi va guardata insieme a R5 e a
`tests/test_booking.py`.

---

### R5. `calendar_event_id` viene azzerato anche quando l'evento non è stato cancellato

**Dove** — `backend/services/booking_service.py:20-22`, `backend/services/calendar_service.py:234-244`.

**Cosa succede** —

```python
if prenotazione.calendar_event_id:
    elimina_evento_calendario(prenotazione.calendar_event_id)
    prenotazione.calendar_event_id = None
```

`elimina_evento_calendario` non restituisce nulla e cattura ogni eccezione
(`calendar_service.py:243-244`): un fallimento (Google irraggiungibile, credenziali scadute,
calendario non più condiviso) è indistinguibile da un successo. L'id viene azzerato comunque, quindi
**l'applicazione perde l'unico riferimento all'evento** che resta sul calendario del coach. Effetto
concreto: prenotazione cancellata nel database, appuntamento fantasma nel calendario, e nessun modo di
ritrovarlo se non a mano. Vale per entrambe le vie di cancellazione, `booking.py:304` e
`admin/bookings.py:117`, e anche per la cancellazione di un cliente (`clients.py:118`).

**Gravità** — RISCHIOSO.

**Impatto della correzione** — far restituire un booleano a `elimina_evento_calendario`
(`calendar_service.py:234`) e azzerare l'id solo in caso di successo, lasciandolo altrimenti per un
tentativo successivo. Toccati: `calendar_service.py:234-244`, `booking_service.py:20-22`, i tre
chiamanti, e `tests/test_booking.py` dove la funzione è già sostituita da un finto.

---

### R6. Un'email digitata con maiuscole diverse produce un 403 incomprensibile — solo in produzione

**Dove** — `backend/routers/users.py:111`, `backend/routers/booking.py:125-126`.

**Cosa succede** — `get_or_create_user` cerca con `User.email == user.email` e `create_booking`
confronta con `user.email != booking.email`, entrambi senza normalizzare. Su MySQL la collation di
default è *case-insensitive*: `POST /users/` con `Mario@Example.com` **ritrova** la riga esistente
`mario@example.com` e ne restituisce l'id; il passo successivo, `POST /bookings/`, confronta in
Python (case-sensitive) `"mario@example.com" != "Mario@Example.com"` → vero → **403 "user_id and
email do not match"**. Il cliente ha appena inserito la propria email corretta e riceve un errore che
dice che non gli appartiene.

Su SQLite (`tests/conftest.py:32-36`) il confronto è case-sensitive: viene creato un secondo utente e
la prenotazione riesce. Il difetto quindi **non è riproducibile dalla suite**, che sarebbe l'unico
posto in cui verrebbe notato prima della produzione. È lo stesso schema del bug sull'ordinamento
degli slot già documentato in `backend/routers/slots.py:30-41`.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — normalizzare l'email (lowercase) in un punto solo, il validator di
`UserCreate` (`schemas/users.py:15-21`), così coprendo `POST /users/`, `/consulenze/` e
`/pacchetti-richieste/` insieme; e allineare il confronto in `booking.py:125`. Va valutata una
migrazione di normalizzazione per le righe già presenti, altrimenti restano duplicati storici.
Toccati: 1 schema, 1 router, eventualmente 1 migrazione, più `tests/test_booking.py` e
`tests/test_users.py`.

---

### R7. L'anonimizzazione GDPR lascia i dati personali nelle note e nelle prenotazioni

**Dove** — `backend/services/retention_service.py:50-55`, con `backend/models/client_note.py:18` e
`backend/models/booking.py:38`.

**Cosa succede** — `anonimizza_clienti_inattivi` azzera `nome`, `email`, `telefono`, `discord_tag` e
`discord_id` su `users`, ma non tocca:

- `client_notes.nota` — testo libero scritto dal coach su quel cliente (il placeholder del form,
  `admin.js:576`, invita esplicitamente a scriverci osservazioni personali);
- `bookings.note_cliente` e `bookings.note_admin` — testo libero, che l'informativa citata in
  `frontend/js/i18n.js:265` include fra i dati raccolti ("note sul tuo team attuale e sui tuoi
  obiettivi che scegli di condividere").

Le note restano collegate all'utente via `user_id`/`booking_id`, quindi restano attribuibili. Il
docstring del modulo (`retention_service.py:1-7`) dichiara che dopo l'anonimizzazione "il cliente
collegato smette di essere identificabile", il che non è vero se una nota contiene un nome o un
contatto. Da notare che `elimina_cliente` (`clients.py:127`) le cancella davvero: sono le **due vie**
a divergere.

**Gravità** — RISCHIOSO (esposizione dichiarativa più che tecnica, ma è una promessa scritta
nell'informativa pubblica).

**Impatto della correzione** — estendere `anonimizza_clienti_inattivi` alla cancellazione o
neutralizzazione di `client_notes.nota` e delle due colonne di note su `bookings`. Toccati:
`retention_service.py:43-56` e `tests/test_retention.py`. Va deciso se le note servono ancora per le
statistiche: oggi nessuna metrica le legge (`admin/dashboard.py` non le usa), quindi cancellarle non
rompe nulla.

---

### R8. Errori silenziosi nel frontend pubblico

**Dove** — `frontend/js/app.js:434-436`, `:157-159`; `frontend/js/about.js:35-38`.

**Cosa succede** —

- `controllaPacchettoAttivo` (`app.js:412-437`) ha un `catch` **vuoto** con un commento che spiega
  cosa si assume ("nessun pacchetto utilizzabile"). Ma il blocco cattura anche il caso in cui la
  richiesta fallisca per rete o per un 500: uno studente che **ha** un pacchetto pagato non vede il
  checkbox e prenota a 20 €/ora invece che a credito. Nessun messaggio, nessuna traccia in console;
- `loadBookingHistory` (`:152-160`) restituisce `[]` su qualsiasi errore: lo storico prenotazioni
  scompare dalla barra di login e il pulsante "Cancella" con esso, cioè lo studente perde la
  cancellazione self-service senza sapere perché;
- `about.js:35-38` cattura tutto e lascia il placeholder statico: la vetrina recensioni sembra
  semplicemente vuota.

Il terzo caso è accettabile (è dichiarato nel commento). I primi due no: nascondono la differenza fra
"non hai nulla" e "non sono riuscito a chiedertelo".

**Gravità** — RISCHIOSO.

**Impatto della correzione** — distinguere `!res.ok` (condizione applicativa) da `catch` (guasto) nei
due punti di `app.js`, e mostrare un avviso nel secondo caso. Toccato solo `app.js`, in due funzioni.

---

### R9. Il prezzo delle sessioni è scritto in tre posti indipendenti

**Dove** — `backend/routers/booking.py:38` (`TABELLA_PREZZI = {1: 2000, 2: 4000}`),
`frontend/index.html:198,201` (`data-price="20"` / `data-price="40"`, più il testo "1 hour — €20" /
"2 hours — €40"), `frontend/js/app.js:24-25` (`selectedPrice: 20`, default di partenza).

**Cosa succede** — il server decide il prezzo (giustamente, `booking.py:203-205`), ma il riepilogo
mostrato al cliente prima della conferma viene dal `data-price` dell'HTML e dallo stato JS. Cambiando
il listino nel backend, il cliente continua a vedere il vecchio importo in `summary-price`
(`app.js:405`), conferma quella cifra e riceve un'email di conferma
(`email_service.py:134`, `€{prezzo_euro:.2f}`) con l'importo **nuovo**. È una discrepanza visibile al
cliente proprio nel momento dell'acquisto.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — esporre il listino da un endpoint (o inserirlo nella risposta di
`GET /slots/`) e togliere `data-price` dall'HTML. Toccati: `booking.py:38`, un nuovo endpoint o
`schemas/slots.py:60-66`, `index.html:190-203`, `app.js:14-31,374-388,402-406`. Alternativa minima e
onesta: lasciare il numero duplicato ma aggiungere in `booking.py:35-38` il riferimento esplicito ai
due punti del frontend da aggiornare insieme.

---

### R10. Il vincolo sugli orari delle sessioni da 2 ore è duplicato in due linguaggi

**Dove** — `backend/routers/booking.py:44` (`ORE_INIZIO_VALIDE_2H = {15, 17}`),
`frontend/js/app.js:311` (`const ORE_INIZIO_VALIDE_2H = [15, 17]`).

**Cosa succede** — sono due liste separate che devono restare identiche. Se divergono, il frontend
mostra card da 2 ore che il backend rifiuta con 400 (`booking.py:78-82`), oppure — peggio — nasconde
slot che sarebbero prenotabili. Il secondo caso è già costato una regressione documentata in
`app.js:16-23`: partendo dalla vista a 2 ore, il visitatore vedeva una parte sola della
disponibilità senza capirne il motivo. Il frontend ricalcola inoltre l'ora italiana per conto proprio
(`app.js:304-309`, `Intl.DateTimeFormat` su `Europe/Rome`) mentre il backend usa `ZoneInfo`
(`timezone_service.py:17`): due implementazioni della stessa conversione.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — stessa strada di R9: far arrivare la regola dal server. In alternativa,
riferimenti incrociati espliciti nei due commenti. Toccati: `booking.py:40-44`, `app.js:300-332`.

---

### R11. Lo scheduler gira senza fuso orario esplicito

**Dove** — `backend/scheduler.py:350` (`BackgroundScheduler()`), commento `:371-376`.

**Cosa succede** — i cinque trigger `cron` (03:00, 03:01, 03:02, 03:30 dom, 04:00 dom) usano il fuso
locale del processo. Il commento dichiara che in produzione il processo gira in UTC e che l'effetto
pratico è nullo, ma la conseguenza vera non è l'orario: è che **la generazione degli slot dipende da
`date.today()`** (`availability_service.py:65`) e dal confronto con `ultimo_giorno_mese` (`:68`).
Nella notte dell'ultimo giorno del mese, il job che gira alle 03:00 UTC lavora su una data che in
Italia è già il giorno dopo (o il mese dopo): la finestra "fino a fine mese" si sposta di un giorno
rispetto a quello che il coach vede nel pannello, che è tutto in ora di Roma
(`admin/availability.py:49`). Non genera slot sbagliati — la conversione a UTC in
`availability_service.py:93-94` è corretta — ma può generarne uno in meno o uno in più al confine del
mese, in modo non riproducibile.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — `BackgroundScheduler(timezone=ROME_TZ)` in `scheduler.py:350` e
`date.today()` → data italiana in `availability_service.py:65`. Tocca 2 file e cambia l'orario reale
di esecuzione di tutti i job cron, quindi va deciso consapevolmente; `tests/test_scheduler.py` e
`tests/test_availability.py` vanno riletti perché costruiscono date di riferimento.

---

### R12. Percorsi relativi obbligano ad avviare il processo dalla radice

**Dove** — `backend/main.py:89` (`Config("alembic.ini")`), `:162`
(`StaticFiles(directory="frontend")`), `:190,194,198,202` (`FileResponse("frontend/*.html")`).

**Cosa succede** — sono percorsi relativi alla directory di lavoro del processo, non al file. Avviato
da una directory diversa, il server **parte lo stesso**: le migrazioni falliscono nel `try`
(`main.py:101-108`) con un alert Discord, `/` risponde 404 su un file inesistente e `/static` solleva
all'avvio del mount. Non c'è nulla nel codice che dichiari il vincolo, e `nixpacks.toml:5` non fissa
una `WORKDIR`.

**Gravità** — RISCHIOSO (funziona oggi per convenzione; si rompe al primo cambio di piattaforma o
container).

**Impatto della correzione** — derivare i percorsi da `Path(__file__).resolve().parent.parent`.
Tocca 6 righe di `main.py`, nessun altro file.

---

### R13. `hash_admin_password.py` reimplementa la scrittura del `.env` e può lasciarne due copie

**Dove** — `scripts/hash_admin_password.py:60-85`, contro `scripts/_env_utils.py:12-41`.

**Cosa succede** — l'helper condiviso `aggiorna_env_locale` è stato estratto (`_env_utils.py`) e i
due script `reauth_*.py` lo usano direttamente (`reauth_gmail.py:111-112`,
`reauth_drive.py:96-97`). `hash_admin_password.py` invece mantiene una **copia** della logica
(`:60-83`) per gestire la migrazione dalla vecchia riga `ADMIN_PASSWORD=` in chiaro, e delega
all'helper solo come ultimo ramo (`:85`). Il ramo legacy sostituisce `ADMIN_PASSWORD=...` con
`ADMIN_PASSWORD_HASH=...` **senza verificare se una riga `ADMIN_PASSWORD_HASH=` esista già**: in un
`.env` che le contiene entrambe (esattamente lo stato intermedio della migrazione) il risultato ha
due `ADMIN_PASSWORD_HASH`. `python-dotenv` tiene l'ultima, che è quella vecchia: **la nuova password
non funziona e il file non dà alcun segnale**.

Nota collaterale su `_env_utils.py:24-30`: il valore viene passato come stringa di sostituzione a
`re.subn`, dove `\` e `\g` sono sequenze speciali. Gli hash bcrypt e i refresh token OAuth non
contengono backslash, quindi oggi non si manifesta, ma è una trappola latente per qualunque valore
futuro.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — far rimuovere all'helper la riga legacy prima di aggiungere quella
nuova, e ridurre `hash_admin_password.py:60-85` a una sola chiamata. Usare `re.escape` o una
sostituzione con `lambda` in `_env_utils.py:26`. Toccati: 2 file di `scripts/`, nessun codice
applicativo.

---

### R14. Nel pannello convivono due formati di data e due fusi orari

**Dove** — lato Rome: `admin/bookings.py:58,86`, `admin/clients.py:87`, `admin/reviews.py:48`,
`admin/availability.py:49`. Lato UTC grezzo: `frontend/js/admin.js:601` (note cliente), `:735`
(pacchetti), `:1015-1016` (blocchi), `:920` (orari regole).

**Cosa succede** — il backend converte in ora di Roma e formatta `gg/mm/aaaa hh:mm` per prenotazioni,
clienti, recensioni e slot; per le **note cliente** (`ClientNoteResponse`, `schemas/client_note.py:17`)
e per i **pacchetti** (`PackageResponse`, `schemas/package.py:28`) restituisce invece il `datetime`
naive così com'è, e il JS lo taglia con `n.created_at.replace('T',' ').slice(0,16)` → formato
`aaaa-mm-gg hh:mm`, **in UTC**. I blocchi eccezionali mostrano `aaaa-mm-gg` (`admin.js:1015`).

Nella stessa schermata, quindi, "Registrato il 08/09/2026 14:30" (Roma) sta accanto a
"2026-09-08 12:30" (UTC) per un evento avvenuto nello stesso istante. Il commento ripetuto tre volte
nel backend (`bookings.py:82-85`, `clients.py:83-86`, `reviews.py:44-47`) spiega che mostrare il
valore grezzo lo sfalsa "di un'ora d'inverno e di due d'estate": la correzione è stata applicata a
tre viste su cinque.

**Gravità** — RISCHIOSO (il coach legge orari sbagliati di 1-2 ore quando incrocia una nota con una
sessione).

**Impatto della correzione** — passare anche note e pacchetti da `formatta_data_ora_rome`, cioè
sostituire i due `response_model` con risposte costruite a mano come già fanno gli altri endpoint.
Toccati: `admin/clients.py:136-174`, `admin/packages.py:19-25`, `schemas/client_note.py`,
`schemas/package.py`, e `admin.js:599-604,729-737,1013-1024`. È anche l'occasione per uniformare il
formato dei blocchi.

---

### R15. I messaggi d'errore mostrati al pubblico sono in una lingua sola, e non è sempre la stessa

**Dove** — messaggi inglesi: `booking.py:60,66,81,91,96,120,124,126,141,144,146,150,164,187,200,295,297,299,301,350,355,359`,
`users.py:55`. Messaggi italiani: `slots.py:60`, tutti i router `admin/*`, `admin/__init__.py:34,52`.
Consumo lato pubblico: `frontend/js/app.js:201` (`alert(errore.detail || ...)`),
`frontend/js/recensione.js:54,59`.

**Cosa succede** — il sito pubblico è bilingue (`i18n.js:13-285`, con `setLang` e `localStorage`), ma
i `detail` del backend sono stringhe fisse che il frontend mostra **così come arrivano**. Un
visitatore con l'interfaccia in italiano che tenta di cancellare una prenotazione passata riceve
"This session has already happened, it can no longer be cancelled" (`booking.py:301`). La pagina
recensione (`recensione.js:29,33,39,57,61`) è interamente in inglese hard-coded e
`frontend/recensione.html` non carica nemmeno `i18n.js` (`AUDIT.md` §1.3), quindi è l'unica pagina
monolingua del sito — ed è quella che riceve i clienti dal link email.

**Gravità** — RISCHIOSO (non tecnico: è la pagina che raccoglie le recensioni, cioè quella dove
l'attrito costa di più).

**Impatto della correzione** — sostituire i `detail` mostrati all'utente con codici tradotti lato
frontend, oppure limitarsi a tradurre i messaggi del percorso pubblico. Toccati: `booking.py`
(≈20 stringhe), `app.js:196-212`, `recensione.js` per intero, `frontend/recensione.html` per
aggiungere `i18n.js`, e le chiavi corrispondenti in `i18n.js`.

---

### R16. Due job caricano l'intera tabella in memoria

**Dove** — `backend/services/retention_service.py:35-40`,
`backend/services/availability_service.py:124-130`.

**Cosa succede** — `anonimizza_clienti_inattivi` carica **tutti** gli utenti non anonimizzati con
`joinedload` di prenotazioni e pacchetti, ogni notte alle 03:01. `elimina_slot_obsoleti` costruisce un
set Python con **tutti** gli `slot_id` di `bookings` (`:124-128`) e carica tutti gli slot passati
(`:130`). Entrambi crescono senza limite con la storia del servizio, mentre le altre liste sono
paginate (`pagination_service.py:14`) o filtrate su una finestra (`dashboard.py:107-118`). Oggi i
volumi sono minimi; il problema è che nulla nel codice mette un tetto, e il guasto — un job notturno
che va in memoria o in timeout — sarebbe silenzioso (`scheduler.py` non cattura né notifica le
eccezioni di questi due job, a differenza di backup e retention che hanno un alert dedicato).

**Gravità** — RISCHIOSO (differito, non immediato).

**Impatto della correzione** — trasformare entrambi in query SQL con filtro/`NOT EXISTS`. Toccati:
`retention_service.py:23-60`, `availability_service.py:109-140`, e i test corrispondenti
(`tests/test_retention.py`, `tests/test_availability.py`), che oggi verificano il comportamento
tramite oggetti in memoria.

---

### R17. La cache delle credenziali Google può restituire credenziali di un'altra integrazione

**Dove** — `backend/services/google_oauth_service.py:23,33-42`.

**Cosa succede** — `_credenziali_cache` è indicizzata **solo** sul refresh token, non su
`(refresh_token, client_id)`. Se `GMAIL_REFRESH_TOKEN` e `DRIVE_REFRESH_TOKEN` sono entrambi assenti
— configurazione parziale, o un `.env` incompleto in staging — le due chiamate
(`email_service.py:95` e `backup_service.py:69`) condividono la chiave `None` e la seconda riceve
l'oggetto costruito dalla prima. Entrambe fallirebbero comunque, ma i log e gli alert
(`scheduler.py:285-293`) attribuirebbero il guasto alla credenziale sbagliata: la sonda Drive
riporterebbe l'errore di Gmail, e il messaggio suggerirebbe `reauth_drive.py` per un problema che sta
altrove — esattamente il caso che `CredenzialeSorvegliata` (`scheduler.py:56-66`) dichiara di voler
evitare.

**Gravità** — RISCHIOSO.

**Impatto della correzione** — chiave composita in `google_oauth_service.py:33,42`, e/o rifiuto
esplicito di un `refresh_token` `None`. Tocca un solo file, 5 righe.

---

## COSMETICO

### C1. Codice e colonne che nessuno usa

| Dove | Cosa | Perché è un residuo |
|---|---|---|
| `backend/services/package_service.py:13,20,27` | `prezzo_pieno_cents` (8000/16000/24000) | Mai letto da nessun modulo (verificato su tutto il repo). I prezzi barrati che mostra il sito sono scritti a mano in `frontend/index.html:368,380,392` (€80/€160/€240) e non vengono da qui. |
| `backend/routers/users.py:59-61` | `GET /users/` | Nessuna pagina lo chiama (`AUDIT.md` §2.9, colonna "Chiamato dal frontend": vuota) e nessun test lo esercita. Restituisce `UserResponse` completo — nome, email, telefono, Discord — di **tutti** i clienti. Superficie di attacco senza contropartita. |
| `backend/models/users.py:19` + `schemas/users.py:19,42` | `User.telefono` | Nessun form lo raccoglie: `app.js:499` invia sempre `telefono: null`, e non esiste un campo telefono in `index.html`. La colonna è solo letta (`clients.py:77`) e azzerata (`retention_service.py:52`). |
| `backend/models/availability_rule.py:32` | `AvailabilityRule.attiva` | Letta da `scheduler.py:230`, mai scritta da un endpoint: non è in `AvailabilityRuleCreate` (`schemas/availability.py:8-12`) né valorizzata dal router (`admin/availability.py:134-139`), e non esiste un `PATCH` sulla regola. Il commento del model lo dichiara. Già segnalato in `DRIFT.md` §1. |
| `alembic/env.py:14` | Import di 6 model su 8 | Mancano `Package` e `Review`. Innocuo, perché `from backend.models import ...` esegue l'intero `backend/models/__init__.py:9-16` e registra tutte e otto le tabelle — ma la riga suggerisce una completezza che non ha, e chi aggiungesse un nono model potrebbe crederla la lista da mantenere. |

**Impatto della correzione** — rimozioni indipendenti l'una dall'altra. `prezzo_pieno_cents` e
`GET /users/` si eliminano senza toccare altro. `telefono` e `attiva` sono decisioni di prodotto
("completare o rimuovere"), non pulizia: la rimozione richiederebbe una migrazione.

### C2. Import locale giustificato da un ciclo che non esiste

**Dove** — `backend/services/calendar_service.py:198-200`.

Il commento dice: *"Import locale per evitare un ciclo: il router che importa da qui importa a sua
volta i model"*. Ma `backend/models/slots.py` importa solo `backend.database`, e non c'è nessun
percorso che riporti da `models` a `calendar_service`. Un import in cima al file funzionerebbe, come
già fa `availability_service.py:11`. È il residuo di una struttura precedente, e il commento
scoraggia attivamente dal sistemarlo.

**Impatto** — spostare l'import: 3 righe, un solo file.

### C3. La sonda delle credenziali chiede due access token invece di uno

**Dove** — `backend/services/google_oauth_service.py:44-45` e `:81`, con `email_service.py:108-111` e
`backup_service.py:62-65`.

`credenziali_oauth_google` fa già `credenziali.refresh(Request())` se il token non è valido (`:44-45`);
`verifica_credenziali_google` chiama subito dopo un secondo `refresh()` esplicito (`:81`). Il secondo
è **voluto** e il docstring lo spiega (`:72-74`: non fidarsi della cache), ma nel percorso "cache
vuota" — cioè al primo controllo dopo ogni riavvio, che è quello che conta di più — se ne fanno due
di fila. Una richiesta sprecata a settimana per credenziale, non un problema: solo una piccola
incoerenza fra due funzioni che si sovrappongono.

**Impatto** — un parametro `forza_refresh` su `credenziali_oauth_google`, oppure lasciare com'è e
correggere il commento. Un solo file.

### C4. Segnaposto e commenti che descrivono qualcosa di diverso dal codice

| Dove | Cosa dice | Cosa fa |
|---|---|---|
| `frontend/js/app.js:428-432` + `i18n.js:84,217` | Il segnaposto si chiama `{used}` ("used/total") | Riceve `compatibile.sessioni_residue`, cioè le **residue**. Il testo mostrato è corretto ("3/4 rimanenti") perché anche la frase dice "rimanenti", ma il nome della variabile dice il contrario del valore. Chi la leggerà per scrivere una terza lingua sbaglierà. |
| `backend/services/availability_service.py:28-31` | *"nessuna sessione dura più di 6 ore"* giustifica `margine = 6h` | La durata massima è 2 ore (`schemas/booking.py:34`, `TABELLA_PREZZI`). Il margine è quindi tre volte più largo del necessario: innocuo, ma il numero non ha più la ragione che il commento gli attribuisce. |
| `backend/scheduler.py:401-402` | *"Sfalsato di un minuto per non sovrapporlo al job precedente"* su `controlla_retention_clienti` (03:01) | Il job che lo precede **nel file** è `controlla_credenziali`, che gira la domenica alle 03:30. Quello da cui è realmente sfalsato è `genera_slot_giornaliero` (03:00), scritto più sopra. |
| `backend/services/calendar_service.py:25` | `SCOPES = ['.../auth/calendar']`, cioè accesso pieno al calendario | Gli altri due script scelgono deliberatamente lo scope minimo e lo dichiarano (`reauth_gmail.py:50-53` "SOLO invio", `reauth_drive.py:43-46` "principio di minimo privilegio"). Il service account Calendar non segue la stessa regola e nessun commento lo giustifica: `calendar.events` sarebbe sufficiente per insert/list/delete. |

**Impatto** — modifiche di sole stringhe e commenti, tranne l'ultima riga, che è un cambio di scope da
riautorizzare su Google Cloud e da provare con `verifica_credenziali_calendario`.

### C5. Le stesse etichette scritte quattro volte

**Dove** — `backend/schemas/booking.py:9` (elenco autorevole),
`backend/models/booking.py:32` (commento), `backend/services/discord_service.py:25-30`,
`frontend/js/admin.js:181-186`, `frontend/js/i18n.js:56-59` e `:191-194`,
`frontend/index.html:172` e seguenti (attributi `data-service`).

I quattro tipi di servizio e le loro etichette leggibili vivono in sei posti. Lo stesso vale per il
catalogo pacchetti: `backend/services/package_service.py:7-29` (autorevole),
`frontend/js/admin.js:191-195` (copia dichiarata tale nel commento `:188-190`),
`frontend/index.html:365-398` (nomi, sessioni e prezzi scritti a mano). Oggi sono allineati — la
verifica è stata fatta valore per valore — ma niente lo garantisce, e nessuno dei due elenchi
frontend ha un modo di accorgersi di una divergenza: `admin.js:732` e `:381` degradano silenziosamente
al valore grezzo (`|| p.tipo`).

**Impatto della correzione** — un endpoint pubblico che espone catalogo ed etichette, consumato da
`app.js`, `admin.js` e i due HTML. Tocca 1 router nuovo, 2 file JS, 2 HTML; non tocca il database.
Il guadagno è proporzionale a quanto spesso il listino cambia: se non cambia mai, un commento
incrociato nei sei punti è la risposta proporzionata.

### C6. `escapeHtml` duplicata e `event` implicito

**Dove** — `frontend/js/about.js:6-10` vs `frontend/js/app.js:55-64` vs `frontend/js/admin.js:199-210`
(tre copie, la prima con un commento che dichiara la duplicazione come scelta); `app.js:359` e
`admin.js:160` usano la variabile globale `event` dentro un handler invece del parametro.

Le tre copie sono una conseguenza accettata dell'assenza di build step, e il commento in `about.js:4-5`
lo dice. `event` globale funziona in tutti i browser attuali ma è deprecato: in una funzione chiamata
non da un handler (per esempio `showSection` invocata da codice, non da un click) sarebbe `undefined`
e la riga solleverebbe.

**Impatto** — passare `event` come parametro: 2 righe in 2 file, più i punti di chiamata negli HTML
(`onclick="showSection('...')"` diventerebbe `onclick="showSection(event, '...')"`).

---

## Accoppiamenti e dipendenze circolari

Non ci sono cicli di import che il Python non risolva, ma ci sono tre punti in cui la struttura
impone di caricare molto più del necessario e rende difficile toccare un modulo da solo.

### D1. Il router pubblico degli slot trascina dentro tutto il pannello admin

`backend/routers/slots.py:12` e `backend/routers/users.py:20` importano `get_admin` da
`backend.routers.admin`. Quell'import esegue `backend/routers/admin/__init__.py`, che in fondo
(`:61`) importa i **sei** sotto-router, ognuno dei quali importa i propri model, schemi e servizi.
Conseguenza concreta: non è possibile importare il router degli slot — per esempio in un test mirato
— senza caricare dashboard, analytics, export CSV, moderazione recensioni e il servizio calendario.
Il commento in `admin/__init__.py:8-9` riconosce il problema ("spostarlo altrove romperebbe quegli
import") ma lo tratta come un vincolo invece che come il sintomo.

**Correzione** — spostare `get_admin` (e `oauth2_scheme`) in un modulo di dipendenze neutro, per
esempio accanto a `backend/rate_limit.py`, che esiste già esattamente per questa ragione
(`rate_limit.py:3-5`). Toccati: `admin/__init__.py`, i 6 sotto-router, `slots.py:12`, `users.py:20`,
più `tests/conftest.py:30` se cambia il punto di import. È un cambio ampio ma meccanico, e
rimuoverebbe anche la necessità dell'import in fondo al file (`admin/__init__.py:58-61`).

### D2. Router che importano router

`backend/routers/booking.py:27` importa `get_studente`/`get_studente_opzionale` da
`backend/routers/users.py`; `consulenza.py:14` e `pacchetti_richieste.py:14` importano
`get_or_create_user` dallo stesso; `discord_auth.py:23` importa `STUDENT_TOKEN_COOKIE`. Il router
degli utenti è quindi diventato di fatto un modulo di servizio, ma vive in `routers/` e importa a sua
volta `get_admin` da `routers/admin` (D1): la catena `booking → users → admin → 6 sotto-router` si
percorre a ogni import.

**Correzione** — spostare le tre dependency in `backend/services/` o in un `backend/dependencies.py`.
Toccati: `users.py:32-56,104-126` e i quattro router che importano da lì. Da fare insieme a D1,
perché è la stessa catena.

### D3. `main.py` importa lo scheduler, che importa tutti i servizi

`backend/main.py:37` importa `avvia_scheduler`; `backend/scheduler.py:27-33` importa a catena
email, Discord, timezone, calendario, disponibilità, retention e backup, e legge **otto variabili
d'ambiente a livello di modulo** (`:35-47`). Il tutto avviene al semplice import di `backend.main`,
cioè anche quando il server non viene avviato — per esempio in `tests/conftest.py:27`. L'import è
privo di effetti su database e rete (verificato: nessuna query, nessuna chiamata HTTP), quindi non è
un difetto di correttezza; è però la ragione per cui i valori di `REMINDER_HOURS_BEFORE`,
`PUBLIC_BASE_URL` e compagnia sono **congelati all'import** e non rileggibili senza riavviare, e per
cui un test che voglia cambiarli deve ricaricare il modulo.

**Correzione** — leggere le variabili dentro `avvia_scheduler` invece che a livello di modulo.
Tocca `scheduler.py:35-47` e i punti che le usano (`:120,180,194,354,360,366`), più
`tests/test_scheduler.py`. Non tocca `main.py`.

---

## Nota di metodo

Tre problemi di questo elenco — **B1**, **R6** e, per costruzione, la mancata copertura di **B3** —
condividono la stessa causa: la suite gira su SQLite in memoria (`tests/conftest.py:32-36`) senza
chiavi esterne attive e con confronti di stringa case-sensitive, mentre la produzione è MySQL. Sono
esattamente i difetti che un test non può vedere, ed è la stessa dinamica già documentata nel codice
per l'ordinamento degli slot (`backend/routers/slots.py:30-41`, *"è la differenza fra i due database,
non la query, a nascondere il difetto"*). Attivare `PRAGMA foreign_keys=ON` nella conftest è
l'intervento con il miglior rapporto fra costo (una riga) e problemi che rende visibili.
