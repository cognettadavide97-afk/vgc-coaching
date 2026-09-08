# Revisione 1 — Architettura

**Mandato:** staff engineer, struttura. Confini tra layer, dipendenze, dispersione
della logica di dominio, accoppiamenti, duplicazione sostanziale.
**Perimetro:** `backend/`, più il frontend al solo confine con l'API.
**Metodo:** lettura diretta delle 4.779 righe di `backend/` e dei punti di chiamata
in `frontend/js/`. Nessun altro documento di `audit/` è stato letto.
**Domanda guida:** se domani cambia il requisito X, quanti file devo toccare?

---

## 0. Rettifica al contesto fornito

Il contesto della committenza dice: *"Backend: Python 3.11, nessun web framework —
routing, validazione input ed error handling sono implementati a mano."*

**È falso, e la differenza cambia metà dell'analisi.** Il progetto usa FastAPI
0.136.3 con Pydantic 2.13.4, Starlette e slowapi (`requirements.txt:21,44,49,52`);
`backend/main.py:25` importa `FastAPI` e `main.py:129` costruisce l'app.

La conseguenza per il mandato: **routing e validazione dell'input SONO astratti in
un punto solo** — sono dichiarativi e li fornisce il framework. Non li ho trovati
riscritti a ogni endpoint, e non è un difetto di questo progetto. Il difetto sta
un passo più in là, ed è quello che riporto sotto: **la serializzazione non lo è**
(§A3), e **la logica di dominio vive dentro gli handler** (§A2).

Se il contesto è sbagliato su questo punto, vale la pena verificare da dove viene:
un documento di progetto che descrive un'architettura diversa da quella in essere
è già di per sé un problema di manutenzione a sei mesi.

---

## 1. Risposta alla domanda guida

Conteggi verificati, non stimati.

| Requisito che cambia | File da toccare | Punti |
|---|---|---|
| Il prezzo orario passa da 20 € a 25 € | **4 file, 6 punti** | `routers/booking.py:38`, `js/app.js:25`, `index.html:199,202`, `js/i18n.js:51-52,187-188` |
| Si aggiunge un quarto pacchetto | **6 file, 7 punti** | `services/package_service.py:7`, `schemas/package.py:7`, `schemas/pacchetto_richiesta.py:10`, `js/admin.js:191`, `index.html:363-395`, `js/i18n.js` (×2 lingue) |
| Si ammettono sessioni da 3 ore | **6 file backend** + frontend | `routers/booking.py:38,44,76-97`, `schemas/booking.py:34`, `schemas/slots.py:39`, `schemas/availability.py:32`, `services/availability_service.py:62` |
| Si aggiunge un canale di notifica (es. Telegram) | **5 file** | `routers/booking.py:250-276`, `routers/consulenza.py:32-46`, `routers/pacchetti_richieste.py:34-53`, il nuovo service, `tests/conftest.py:85-100` |
| Un nuovo endpoint protetto | **1 file, ma importando da 2 router** | `from backend.routers.admin import get_admin` oppure `from backend.routers.users import get_studente` |
| **Sbloccare uno slot bloccato** | **il percorso non esiste** | §A1 |

Il progetto è ben tenuto: i commenti sono seri, le decisioni non ovvie sono
motivate, le astrazioni che esistono (`timezone_service`, `pagination_service`,
`google_oauth_service`, `_invia_embed`) sono quelle giuste. Il problema non è
disordine — è che **le astrazioni si fermano un livello sotto quello dove il
dominio vive davvero**.

---

## 2. Findings

### A1 — ALTA — Lo stato di uno `Slot` non ha un proprietario, e le transizioni sono a senso unico

`backend/models/slots.py:27,33-34` — `backend/services/availability_service.py:167-168` —
`backend/services/calendar_service.py:225-226` — `backend/services/booking_service.py:26,31` —
`backend/routers/admin/availability.py:213-230` — `frontend/js/admin.js:844-863`

**[VERIFICATO]** Lo stato di uno slot è codificato da tre booleani indipendenti
(`is_available`, `blocked_external`, `blocked_admin`) scritti da quattro moduli
diversi. Ho cercato tutte le scritture su quei campi in `backend/`:

- `blocked_external = True` — solo `calendar_service.py:226`
- `blocked_admin = True` — solo `availability_service.py:168`
- `blocked_external = False` / `blocked_admin = False` — **in nessun punto del progetto**
- `is_available = True` — solo `booking_service.py:26,31`, cioè esclusivamente
  alla cancellazione di una prenotazione

**Conseguenza concreta.** Uno slot bloccato dalla sincronizzazione con Google
Calendar, o da un blocco ferie, non torna mai prenotabile. Se il coach cancella
l'impegno su Google, `sincronizza_slot_con_calendario` non lo rivede nemmeno:
`calendar_service.py:205` filtra `is_available == True`, e quello slot non lo è
più. Se il coach elimina il blocco ferie, `elimina_blocco_eccezionale`
(`availability.py:213-230`) rimuove la riga e lascia gli slot bloccati — il
docstring alla riga 221-222 lo dichiara: *"vanno sbloccati a mano se necessario"*.
Ma la mano non ha strumento: il pannello non offre alcuna azione di sblocco
(`grep -rn "sblocc\|unblock" frontend/` → nessun risultato) e per uno slot non
disponibile la colonna Azioni mostra `—` (`admin.js:857-862`), quindi non è
nemmeno eliminabile. L'unica uscita è `elimina_slot_obsoleti` quando lo slot è
ormai passato, oppure una `UPDATE` a mano sul database di produzione.

**Root cause architetturale.** Non esiste un punto che possieda il ciclo di vita
dello slot. Ogni modulo che ha bisogno di renderlo indisponibile scrive
direttamente i campi che gli servono, e nessuno possiede l'operazione inversa —
che infatti non è mai stata scritta. Lo stesso vuoto rende rappresentabili stati
incoerenti: `is_available=True` con `blocked_admin=True` passerebbe senza
obiezioni e `availability.py:55-57` lo renderebbe come "disponibile" e "bloccato
da admin" insieme.

**Intervento minimo.** Un `services/slot_state.py` con quattro funzioni —
`occupa`, `libera`, `blocca(motivo)`, `sblocca` — uniche scritture ammesse su quei
tre campi, più `PATCH /admin/slots/{id}/sblocca` e il bottone corrispondente.
**Costo: mezza giornata**, incluso il test sulle transizioni.

---

### A2 — ALTA — `create_booking` *è* il dominio dell'applicazione, e vive dentro un handler HTTP

`backend/routers/booking.py:31,38,44,47-278` — `backend/services/booking_service.py:1-31`

**[VERIFICATO]** La funzione `create_booking` occupa 230 righe e contiene, in
sequenza: validazione dello slot, regola delle sessioni da 2 ore, risoluzione
dell'identità del prenotante nei due rami (con e senza login), redenzione del
pacchetto, limite anti-abuso, riserva atomica di uno o due slot, calcolo del
prezzo, creazione dell'evento su Google Calendar, persistenza, scalo del credito e
tre notifiche.

Le costanti di prodotto stanno nel modulo del router:
`MAX_PRENOTAZIONI_ATTIVE` (`booking.py:31`), `TABELLA_PREZZI` (`:38`),
`ORE_INIZIO_VALIDE_2H` (`:44`). Il service che dovrebbe ospitarle,
`booking_service.py`, contiene 31 righe e solo il percorso di cancellazione.

**Conseguenza concreta.** Nessuna di queste regole è invocabile senza un client
HTTP. Verificare "un pacchetto esaurito non è spendibile" richiede di costruire
TestClient, cookie di sessione, utente, slot e corpo JSON per esercitare quattro
righe di logica (`:145-146`). Un secondo punto d'ingresso — prenotazione creata
dal coach dal pannello, riprogrammazione, importazione — obbligherebbe a
duplicare l'intero blocco o a riscriverlo. E fra sei mesi l'autore che deve
cambiare il vincolo delle 2 ore lo cerca in un service, non lo trova, e lo cerca
nel router solo dopo.

Va detto in positivo: la funzione è la parte meglio commentata del progetto e la
riserva atomica (`:178-200`) è fatta bene. Il problema non è la qualità del
codice, è la sua collocazione.

**Intervento minimo.** Spostare le righe 58-246 in
`booking_service.crea_prenotazione(db, dati, studente) -> Booking`, che solleva
eccezioni di dominio; il router traduce in `HTTPException` e mantiene le tre
notifiche post-commit. Le tre costanti seguono nel service.
**Costo: 1 giorno**, compresi i test unitari che diventano possibili.

---

### A3 — ALTA — Non esiste una convenzione unica di serializzazione: tre meccanismi e tre convenzioni di data

`backend/schemas/slots.py:68-78` — `backend/routers/users.py:87-101` —
`backend/routers/admin/bookings.py:56-89` — `backend/routers/admin/clients.py:70-92` —
`backend/routers/admin/reviews.py:38-56` — `backend/schemas/package.py:28` —
`backend/services/pagination_service.py:19-29` — `frontend/js/admin.js:734`

**[VERIFICATO]** Le risposte dell'API sono costruite in tre modi che coesistono:
`response_model` Pydantic (`slots.py:20`, `admin/packages.py:19`), dizionari
assemblati a mano nell'handler (`users.py:87-101`, `admin/clients.py:70-90`,
`admin/bookings.py:56-87`, `admin/dashboard.py:65-71`), e la busta di paginazione
(`pagination_service.py:19`).

Le date ne pagano il prezzo, con **tre convenzioni diverse sullo stesso tipo di
dato**:

1. `SlotResponse` serializza ISO-8601 con offset UTC esplicito
   (`schemas/slots.py:68-78`);
2. le liste admin inviano stringhe già formattate in ora italiana —
   `"07/09/2026"`, `"20:00"` (`admin/bookings.py:58,86`, `admin/clients.py:87`,
   `admin/reviews.py:48`);
3. `PackageResponse` invia il `datetime` naive grezzo (`schemas/package.py:28`).

**Conseguenza dimostrata.** `admin.js:734` rende la data di assegnazione di un
pacchetto con `p.created_at.replace('T',' ').slice(0,16)`, cioè mostra l'orario
**UTC** — sfalsato di un'ora d'inverno e di due d'estate rispetto a ogni altra
data della stessa schermata. Che sia lo stesso difetto e non una coincidenza lo
dice il codice: `admin/clients.py:83-86` e `admin/reviews.py:44-47` portano lo
**stesso identico commento** di quattro righe, perché lo stesso problema è stato
corretto due volte a mano, endpoint per endpoint; `admin/packages.py` non è stato
toccato. E `users.py:97-99` ha dovuto aggiungere un terzo campo `start_time_iso`
accanto alle stringhe formattate, con il commento che ne spiega il motivo — il
frontend non può fare aritmetica su una data già formattata.

Alla stessa radice appartiene l'incoerenza di forma: `/admin/prenotazioni`,
`/admin/clienti` e `/admin/slots` restituiscono `{items, totale, pagina, ...}`,
mentre `/admin/pacchetti` (`admin/packages.py:19`), `/admin/recensioni`
(`admin/reviews.py:18`) e `/admin/disponibilita/*` (`admin/availability.py:110,174`)
restituiscono un array nudo, senza limite. Il frontend deve sapere a memoria quali
sono quali (`admin.js:709` vs `admin.js:816-818`).

**Intervento minimo.** Una decisione sola, applicata ovunque: *il server invia
sempre ISO-8601 con offset, la formattazione appartiene al frontend*. Un helper
`formattaDataOra()` lato JS, e i cinque endpoint che oggi preformattano tornano a
`response_model`. **Costo: 1 giorno** (5 endpoint backend, 3 funzioni di render).

---

### A4 — ALTA — Il listino esiste in cinque copie indipendenti, nessuna delle quali è la fonte

`backend/routers/booking.py:38` — `backend/services/package_service.py:7-28` —
`backend/schemas/package.py:7` — `backend/schemas/pacchetto_richiesta.py:10` —
`frontend/js/admin.js:191-195` — `frontend/index.html:198-202,368,380,392` —
`frontend/js/i18n.js:51-52,187-188`

**[VERIFICATO]** Il prezzo orario è scritto in `TABELLA_PREZZI = {1: 2000, 2: 4000}`
(`booking.py:38`) e, indipendentemente, in `data-price="20"` / `data-price="40"`
(`index.html:198-202`), in `selectedPrice: 20` (`app.js:25`) e nelle stringhe
tradotte `'1 hour — €20'` / `'1 ora — €20'` (`i18n.js:51-52,187-188`).

Il catalogo pacchetti è in `CATALOGO_PACCHETTI` (`package_service.py:7-28`) e di
nuovo, con nomi e prezzi riscritti a mano, in `const CATALOGO_PACCHETTI`
JavaScript (`admin.js:191-195`) e nel markup delle tre card
(`index.html:363-395`). Le chiavi ammesse `["intro","team","tour"]` sono
dichiarate due volte lato backend, in `schemas/package.py:7` e
`schemas/pacchetto_richiesta.py:10`.

**Nessun endpoint espone il listino.** Non c'è un `GET /catalogo`: il frontend non
ha modo di leggerlo anche volendo.

**Conseguenza concreta.** Aggiungere un quarto pacchetto e dimenticare
`admin.js:191` produce un pacchetto che il sito pubblico offre, lo schema accetta
e l'API assegna correttamente, **ma che non compare fra le scelte del modale di
assegnazione** (`admin.js:659-664` itera su quella costante): il coach incassa e
non ha il bottone per attivarlo. Nessun test confronta le copie, quindi la suite
resta verde.

Nota collaterale: `prezzo_pieno_cents` (`package_service.py:13,20,27`) non è letto
da nessuna parte del backend — è il prezzo barrato, che vive solo nel markup
(`index.html:368,380,392`). Dato di dominio morto nel catalogo, vivo nell'HTML.

**Intervento minimo.** `GET /catalogo` pubblico che serve `CATALOGO_PACCHETTI` e
`TABELLA_PREZZI`; `index.html` e `admin.js` costruiscono le card leggendolo; i due
`Literal` derivati con `Literal[tuple(CATALOGO_PACCHETTI)]`.
**Costo: mezza giornata.**

---

### A5 — MEDIA — Gli effetti collaterali sono chiamati per nome dal router: l'unica cucitura per isolarli è il monkeypatch

`backend/routers/booking.py:22-26,250-276` — `backend/routers/consulenza.py:15-20,32-46` —
`backend/routers/pacchetti_richieste.py:16-21,34-53` — `tests/conftest.py:80-100` —
`backend/services/email_service.py:227-313`

**[VERIFICATO]** I tre router importano le funzioni di invio direttamente per nome
e le chiamano in sequenza. L'unico modo di neutralizzarle nei test è sostituire
l'attributo **sul modulo del router**, uno per uno: `conftest.py:85-100` lo fa
undici volte.

**Conseguenza già avvenuta, documentata dal codice stesso.** `conftest.py:92-95`:
*"Stessa cosa per consulenza.py e pacchetti_richieste.py: chiamano email e Discord
VERI tanto quanto booking.py, ma finora nessun test li copriva — un test che li
chiamasse senza queste righe manderebbe davvero email/messaggi Discord con le
credenziali reali del .env."* Il buco si è chiuso quando qualcuno se n'è accorto,
non per costruzione: **il prossimo router che notifica lo riapre in silenzio**, e
il sintomo sarà un'email vera partita da una suite verde.

Alla stessa radice la duplicazione del ventaglio: lo schema *(conferma al cliente
+ notifica al coach + embed Discord)* è ripetuto identico in tre router, e produce
nove funzioni quasi uguali nei service —
`invia_conferma_richiesta_consulenza` e `invia_conferma_richiesta_pacchetto`
(`email_service.py:227-246` e `:271-290`) differiscono per una frase;
`invia_notifica_richiesta_consulenza_admin` e `..._pacchetto_admin`
(`:249-268` e `:293-313`) per una riga di corpo.

**Intervento minimo.** Il punto unico di uscita esiste già ed è ben fatto
(`_invia_via_gmail` a `email_service.py:81`, `_invia_embed` a
`discord_service.py:33`): basta farvi passare un interruttore
`NOTIFICHE_ABILITATE`, spento per costruzione in test. Poi un
`notifiche_service.notifica_<evento>(...)` per i tre eventi, unico nome importato
dai router. **Costo: mezza giornata.**

---

### A6 — MEDIA — Le dependency di autorizzazione vivono dentro i router, e ogni nuovo router deve importare da altri due

`backend/routers/admin/__init__.py:8-9,23-37,58-61` — `backend/routers/users.py:35-56,104-126`

**[VERIFICATO]** `get_admin` è definito dentro il pacchetto dei router admin;
`get_studente`, `get_studente_opzionale`, la costante `STUDENT_TOKEN_COOKIE` e la
funzione di dominio `get_or_create_user` sono definiti dentro il router degli
utenti. Li importano: `slots.py:12` e `users.py:20` (da `admin`), e `booking.py:27`,
`consulenza.py:14`, `pacchetti_richieste.py:14`, `discord_auth.py:23` (da `users`),
oltre ai sei sotto-router admin.

**Conseguenza già visibile.** `admin/__init__.py:58-61` è costretto a importare i
sotto-router **in fondo al file**, con un commento che spiega che spostarli in
cima produce un import circolare; e `admin/__init__.py:8-9` dichiara che
`get_admin` non può essere spostato *"perché romperebbe quegli import"*. Il grafo
delle dipendenze fra router è già vincolato al punto da condizionare l'ordine
delle righe, e la prossima aggiunta lo peggiora.

**Intervento minimo.** `backend/dependencies.py` con le tre dependency,
`backend/services/user_service.py` con `get_or_create_user`. I router importano
solo da lì e l'import in fondo al file sparisce. **Costo: 2 ore**, meccanico e a
rischio nullo.

---

### A7 — MEDIA — Il frontend non ha un client API: 25 punti di chiamata, ciascuno con la propria gestione errori (o senza)

`frontend/js/admin.js:12,112,146-151` e i 25 `fetch` del file — `backend/routers/slots.py:57-61` —
`backend/services/auth_service.py:21`

**[VERIFICATO]** `admin.js` contiene 25 chiamate `fetch`, ognuna che ripete
`authHeaders()` e decide per conto proprio se controllare l'esito. Alcune lo
controllano (`:548, 623, 690, 881, 960, 1054, 1119`), altre no (`:432, 454, 801,
980, 1075, 1095`).

**Due conseguenze concrete.**

1. `creaSlot` (`admin.js:1094-1104`) ignora la risposta. Il backend risponde 400
   con *"Questo slot si sovrappone a uno slot già esistente"* (`slots.py:57-61`):
   il coach preme il bottone, la lista si ricarica identica, nessun messaggio.
   Il messaggio d'errore esiste, è scritto bene, e nessuno lo vedrà mai.
2. Nessuna gestione centrale del 401. Il token admin dura 480 minuti
   (`auth_service.py:21`) e vive solo in memoria (`admin.js:12`). Alla scadenza il
   pannello resta aperto: le letture falliscono nei rispettivi `catch` e le
   scritture senza controllo falliscono in silenzio, mostrando dati vecchi come se
   fossero aggiornati.

**Intervento minimo.** Una funzione `api(path, opzioni)` che aggiunge gli header,
solleva con `detail` su `!res.ok` e su 401 chiama `logout()`; i 25 `fetch` la
usano. **Costo: mezza giornata.**

---

### A8 — MEDIA — Lo schema con cui girano i test non è lo schema che gira in produzione

`tests/conftest.py:32-36,67` — `backend/main.py:86-98` — `backend/routers/slots.py:29-41`

**[VERIFICATO]** La suite costruisce le tabelle con `Base.metadata.create_all` su
SQLite in memoria (`conftest.py:67`); la produzione le costruisce con
`command.upgrade(alembic_cfg, "head")` su MySQL (`main.py:97`). Sono **due sorgenti
di verità per lo stesso schema**, e nulla le confronta mai.

Ho verificato che oggi non divergono: ogni colonna aggiunta dopo la migrazione
iniziale (`blocked_admin`, `blocked_external`, `review_token`,
`review_email_sent`, `anonimizzato_at`, `package_id`, `slot_id_secondario`,
`attiva`) ha la propria revisione in `alembic/versions/`. Il finding è quindi
strutturale, non un difetto in atto — ma il confine ha **già** prodotto un difetto
reale, e il codice lo documenta: `slots.py:29-41` racconta di un `ORDER BY`
mancante che SQLite mascherava e MySQL no, arrivato fino in produzione e visto dai
clienti come date che saltavano avanti e indietro.

**Intervento minimo.** Un test che, su un database vuoto, esegue `alembic upgrade
head` e verifica che `alembic revision --autogenerate` produca un diff vuoto.
Chiude la divergenza schema/migrazioni. La divergenza SQLite/MySQL resta e non si
chiude con un test: si chiude solo facendo girare la suite anche su MySQL in CI —
opzione da valutare a parte, non la propongo qui. **Costo: 2-3 ore.**

---

### A9 — BASSA — La formattazione delle date è duplicata proprio dove esiste l'helper che serve a evitarlo

`backend/services/timezone_service.py:1-10,34-42` — `backend/routers/booking.py:207-209` —
`backend/scheduler.py:135-137`

**[VERIFICATO]** `formatta_data_ora_rome` esiste e il docstring del modulo
(`timezone_service.py:8-9`) dichiara che vive lì *"perché la stessa conversione non
venga reimplementata — e sbagliata in modo diverso — in ogni punto d'uso"*.
Due punti d'uso la reimplementano comunque, con le stesse tre righe:

```python
slot_rome = utc_to_rome(slot.start_time)
data_slot = slot_rome.strftime("%d/%m/%Y")
ora_slot = slot_rome.strftime("%H:%M")
```

Sono `booking.py:207-209` e `scheduler.py:135-137`, cioè i due punti che
producono le date **dentro le email ai clienti**. Cambiare il formato nel pannello
non lo cambia nelle email. **Costo: 10 minuti.**

---

### A10 — BASSA — Due commenti descrivono un'architettura che non esiste

**[VERIFICATO]** `backend/services/calendar_service.py:198-200`: l'import di `Slot`
è locale alla funzione con la motivazione *"per evitare un ciclo: il router che
importa da qui importa a sua volta i model"*. Il ciclo non esiste: i file di
`backend/models/` importano soltanto `backend.database` (verificato su tutti e
otto), quindi nessun model dipende da `services`. L'import può stare in cima. Il
costo non è la riga: è che il commento insegna al lettore una regola di dipendenza
falsa, che verrà applicata altrove.

**[VERIFICATO]** `alembic/env.py:14` importa sei model su otto — mancano `Package`
e `Review`. Funziona solo perché `backend/models/__init__.py` li importa tutti e
`Base.metadata` risulta comunque completo. La riga *sembra* una lista da tenere
aggiornata e non lo è; chi la "correggesse" credendola la sorgente, o chi
alleggerisse `models/__init__.py`, otterrebbe un `autogenerate` che propone di
eliminare due tabelle. Sostituire con `import backend.models  # noqa` e una riga di
commento. **Costo: 15 minuti** per entrambi.

---

### A11 — DA GIUSTIFICARE — `POST /slots/` è l'unica scrittura amministrativa fuori dal prefisso `/admin`

`backend/routers/slots.py:50-71` — `backend/routers/admin/availability.py:30-107` —
`frontend/js/admin.js:1095,1114`

**[VERIFICATO]** La creazione di uno slot è protetta da `get_admin` ma sta in
`/slots/`, mentre elenco, eliminazione e sincronizzazione degli slot stanno in
`/admin/slots`. Nella stessa schermata del pannello, `admin.js:1095` chiama
`/slots/` per creare e `admin.js:1114` chiama `/admin/slots/{id}` per eliminare.

**Domanda per l'autore:** c'è una ragione per cui la creazione non sta sotto
`/admin` con le altre — un client esterno che la usa, una scelta di compatibilità —
oppure è un residuo di quando `slots.py` era l'unico modulo? Se è la seconda, lo
spostamento è meccanico e la superficie dell'API torna divisa per audience.

---

### A12 — DA GIUSTIFICARE — I messaggi d'errore dell'API sono in due lingue, e il frontend pubblico è bilingue

`backend/routers/booking.py:60,66,81,91,96,119,124,126,141,144,146,150,164` —
`backend/routers/admin/availability.py:90,132,195` — `backend/routers/admin/clients.py:112,168` —
`frontend/js/app.js:201,530` — `frontend/js/i18n.js:1-336`

**[VERIFICATO]** I `detail` delle `HTTPException` sono in inglese nei router
pubblici (*"This booking is not active"*, *"Slot not available"*) e in italiano in
quelli admin (*"Prenotazione non trovata"*, *"Slot non trovato"*). Il frontend
pubblico ha un dizionario completo it/en (`i18n.js`), ma `app.js:201` mostra
`errore.detail` così com'è: **un utente in modalità italiana riceve un messaggio in
inglese**. Nello stesso file, la creazione della prenotazione (`app.js:530`) scarta
del tutto il `detail` e mostra `t('generic_error')` — quindi messaggi precisi come
*"You already have 2 active bookings"* o *"The following hour isn't available"*,
scritti con cura lato server, non arrivano mai all'utente.

**Domanda per l'autore:** la divisione è deliberata (pubblico in inglese, admin in
italiano)? Se sì, resta incompatibile con il ramo italiano del frontend pubblico:
servirebbe un codice d'errore stabile nella risposta, con il testo scelto dal
frontend. Se non è deliberata, è un'incoerenza da chiudere in una direzione sola.

---

## 3. Fuori mandato

Segnalati in una riga ciascuno, senza approfondimento: sono di competenza di altre
sessioni.

- `create_booking` chiama Google Calendar (`booking.py:213`) dentro la transazione
  aperta dalla riserva atomica delle righe 178-200 — comportamento sotto latenza.
- `elimina_cliente` (`admin/clients.py:95-133`) è irreversibile e senza conferma
  lato server, su un endpoint raggiungibile con il solo token admin.
- `_ultimo_controllo_credenziali` (`scheduler.py:53`) è stato in memoria di
  processo: si azzera a ogni riavvio e non è condiviso fra istanze.
- `crea_dump_sql` (`backup_service.py:73`) usa `SHOW TABLES` e
  `SET FOREIGN_KEY_CHECKS`, sintassi MySQL: il backup non è testabile su SQLite.
- `elimina_slot_obsoleti` (`availability_service.py:124-128`) carica in memoria
  tutti gli id prenotati e tutti gli slot passati.
- `renderPaginazione` (`admin.js:78-91`) interpola un nome di funzione dentro un
  `onclick`, nello stesso file il cui commento in testa (`:20-42`) spiega perché
  l'interpolazione negli `onclick` era stata eliminata.

---

## 4. Non verificato

Cosa non ho potuto controllare, e perché.

- **Il comportamento a runtime.** Non ho eseguito l'applicazione né la suite: tutti
  i finding derivano dalla lettura del codice. Dove affermo "non esiste in nessun
  punto" (A1, A4) ho verificato con ricerca esaustiva su `backend/` e `frontend/`,
  ma non con un'esecuzione.
- **La produzione.** Non ho accesso a Railway, al database MySQL, ai log, né alle
  variabili d'ambiente effettivamente impostate. Il contesto indicava "config e
  secret via variabili d'ambiente" come da verificare: resta da verificare. In
  particolare non so se `FRONTEND_ORIGINS` (`main.py:141-144`) e
  `PUBLIC_BASE_URL` (`scheduler.py:42-45`) siano impostate, e i loro default
  puntano a `127.0.0.1:8000`.
- **Lo schema reale del database di produzione.** Ho verificato che ogni colonna
  dei model abbia una migrazione corrispondente (§A8), ma non che il database
  applicato coincida: `run_migrations` (`main.py:86-108`) cattura ogni eccezione e
  lascia partire l'app, quindi una migrazione fallita non è visibile dal codice.
- **La correttezza delle singole regole di dominio.** Non è il mio mandato: ho
  valutato dove vivono, non se calcolano il valore giusto. Le funzioni di
  `availability_service` e di `dashboard`/`analytics` andrebbero lette da chi ha il
  mandato sulla correttezza.
- **I test.** Ho letto `conftest.py` perché rivela un accoppiamento strutturale
  (§A5, §A8). Non ho valutato copertura né qualità dei 17 file di test.
- **Il frontend oltre il confine dell'API.** Struttura interna di `app.js` (668
  righe) e `admin.js` (1169 righe), gestione dello stato, accessibilità, CSS: fuori
  perimetro per esplicita istruzione.
- **`git log` e la storia del progetto.** Non consultati: valuto il codice
  presente, come da mandato.
- **Gli altri report in `audit/`.** Non letti, come da vincolo.
