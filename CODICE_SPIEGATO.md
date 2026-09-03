# CODICE_SPIEGATO.md — il progetto come materiale di studio

> **Cos'è questo file.** La spiegazione didattica del codice: cosa fa una riga, e soprattutto
> **perché è scritta così**. È pensato per chi sta imparando a programmare e usa questo progetto
> come esempio reale.
>
> **Non è** il manuale operativo: per installare, configurare e mettere online l'app vedi
> `README.md`. Per lo stato del progetto, le decisioni prese e il lavoro aperto vedi
> `STATO_PROGETTO.md`.

## Come è organizzata la documentazione (e perché)

Questo progetto tiene separati **due pubblici**, perché hanno bisogni opposti:

| Pubblico | Domanda che si fa | Dove trova risposta |
|---|---|---|
| Chi **studia** | "cos'è un decoratore? perché questa riga esiste?" | **questo file** |
| Chi **legge o modifica il codice** | "cosa fa questo blocco, cosa rompo se lo tocco?" | i **commenti nel codice** |

Prima le due cose stavano insieme dentro i sorgenti. Funzionava per imparare, ma rendeva i file
lunghi da scorrere per chi doveva solo cambiare qualcosa — e, col tempo, le spiegazioni lunghe si
sono disallineate dal codice senza che nessuno se ne accorgesse. Separandole, ognuna può essere
aggiornata con il ritmo che le serve.

C'è anche una ragione pratica. Il codice sorgente è la prima cosa che un'azienda guarda: commenti
che spiegano cos'è un decoratore suggeriscono un principiante che parla a se stesso, mentre
commenti che dichiarano contratti, invarianti e conseguenze di una modifica suggeriscono qualcuno
abituato a scrivere per un collega. I due obiettivi — imparare e mostrare — non sono in conflitto:
richiedono solo di stare in due file diversi. Per questo i commenti nel codice **non rimandano** a
questo documento: devono reggersi da soli.

**Come studiare con questo file:** tienilo aperto accanto al sorgente. Ogni sezione dice quale
file guardare. Non leggerlo tutto di fila: segui il **§3 (il giro di una prenotazione)**, che
attraversa l'intero progetto una volta sola, e torna al §4 quando vuoi il dettaglio di un modulo.

---

## 1. Il quadro generale

L'app è un **monolite**: un solo programma Python che fa due mestieri insieme.

```
                 ┌───────────────────────────────────────┐
                 │            IL TUO BROWSER             │
                 │       (dove vedi le pagine web)       │
                 └───────────────────┬───────────────────┘
                                     │  richieste HTTP (fetch)
                                     ▼
                 ┌───────────────────────────────────────┐
                 │       backend/main.py (FastAPI)       │
                 │  Un unico programma Python che:       │
                 │  1. Serve le pagine HTML/CSS/JS       │
                 │  2. Risponde alle chiamate API        │
                 └───────────────────┬───────────────────┘
                                     │
             ┌───────────────────────┼───────────────────────┐
             ▼                       ▼                       ▼
   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
   │  Database MySQL  │    │ Servizi esterni  │    │    Scheduler     │
   │  (dati salvati)  │    │  Email, Google,  │    │   (promemoria    │
   │                  │    │     Discord      │    │   automatici)    │
   └──────────────────┘    └──────────────────┘    └──────────────────┘
```

**Perché monolite.** Si poteva fare in due programmi separati (uno serve il sito, uno l'API). Per
un progetto di questa dimensione sarebbe stato più lavoro e più cose da tenere accese, senza
nessun vantaggio: un processo solo è più semplice da avviare, da mettere online e da capire. La
stessa logica spiega perché il frontend non usa React o Vue — solo HTML, CSS e JavaScript scritti
a mano, senza nessun passaggio di "build".

### I quattro strati del backend, e perché sono separati

Questa è la divisione più importante da capire, perché tutto il resto del codice la segue:

| Cartella | Risponde a | Esempio |
|---|---|---|
| `models/` | *com'è fatta una riga nel database* | `Slot` ha `start_time`, `is_available`… |
| `schemas/` | *com'è fatto un messaggio JSON in entrata/uscita* | per prenotare mandi `slot_id`, non `price_cents` |
| `services/` | *la logica riutilizzabile e il dialogo con l'esterno* | "manda un'email", "converti un orario" |
| `routers/` | *quale indirizzo web esegue quale funzione* | `POST /bookings/` → `create_booking()` |

**Perché model e schema sono due cose diverse** — è il punto che confonde di più all'inizio. Un
model descrive il *magazzino* (cosa c'è salvato); uno schema descrive la *lettera* (cosa viaggia
sulla rete). Non coincidono mai del tutto: quando prenoti mandi `duration_hours`, ma **non** mandi
il prezzo (lo decide il server, altrimenti chiunque potrebbe prenotare a 0€) né l'`id` (lo assegna
il database). Tenerli separati è ciò che permette di dire "questo campo esiste ma non lo espongo".

---

## 2. I concetti che ricorrono ovunque

Spiegati qui una volta sola, perché li ritrovi in quasi ogni file.

### Decoratore — la riga che inizia con `@`

```python
@router.get("/slots/")
def get_slots(...):
```

Un decoratore è una funzione che ne "avvolge" un'altra per aggiungerle un comportamento, senza
toccarne il contenuto. Qui non c'è magia: `@router.get("/slots/")` dice a FastAPI *"registra
questa funzione nell'elenco degli indirizzi, sotto GET /slots/"*. La funzione da sola non
saprebbe di essere un endpoint — è il decoratore a metterla in quell'elenco.

Puoi impilarne più di uno: in `create_user` ce ne sono due, la registrazione dell'indirizzo e il
limite anti-abuso.

### Dependency Injection — `Depends(...)`

```python
def get_slots(db: Session = Depends(get_db)):
```

Leggi così: *"questa funzione ha bisogno di una sessione del database; non me la costruisco io,
la chiedo a `get_db`"*. FastAPI, prima di eseguire l'endpoint, chiama `get_db()` e passa il
risultato. **Perché conviene:** senza, ogni singola funzione dovrebbe aprire e chiudere la
connessione a mano — decine di copie della stessa riga, e basta dimenticarne una chiusa per
esaurire le connessioni del database.

Le dependency si **incatenano**: in `backend/routers/users.py`, `get_studente` dipende da
`get_studente_opzionale`, che a sua volta legge il cookie. FastAPI risolve tutta la catena da
solo, in ordine, prima di eseguire l'endpoint.

È anche il meccanismo che protegge il pannello admin: `admin: str = Depends(get_admin)` nella
firma di una funzione significa *"prima di entrare qui, verifica il token; se non è valido,
l'endpoint non viene mai raggiunto"*.

### `yield` invece di `return` — la garanzia di chiusura

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Una funzione con `yield` non finisce quando restituisce il valore: si **mette in pausa**. FastAPI
riceve `db`, esegue l'endpoint, e quando la richiesta è finita la funzione **riprende** ed esegue
il `finally`. Il punto sottile: il `finally` gira **anche se l'endpoint è esploso con un errore**.
È questo che garantisce che la connessione venga sempre chiusa, in ogni scenario.

### ORM — scrivere Python invece di SQL

```python
db.query(User).filter(User.id == 5).first()     # invece di: SELECT * FROM users WHERE id = 5
```

SQLAlchemy traduce da solo in SQL. Il vantaggio non è solo scrivere meno: lavori con **oggetti
Python** (`utente.nome`, `utente.bookings`) invece che con tuple anonime, e gli errori di battitura
sui nomi delle colonne li becchi subito.

**Attenzione al costo nascosto (problema "N+1").** Se scorri 100 prenotazioni e per ognuna leggi
`prenotazione.user.nome`, SQLAlchemy fa **una query in più per ogni giro**: 1 + 100 query invece
di una. Nel progetto lo si evita con `joinedload()` e `contains_eager()` — le trovi in
otto punti del progetto, fra cui `scheduler.py`, `retention_service.py`, `routers/booking.py` e i
sotto-router di `admin/`. Cercare `joinedload` nel codice è un buon modo per vedere il problema e
la sua soluzione affiancati in casi diversi.

### Validazione con Pydantic

```python
class UserCreate(BaseModel):
    email: EmailStr
```

Dichiari la *forma* attesa, e Pydantic controlla i dati in arrivo **prima** che il tuo codice li
tocchi: un'email malformata viene respinta con un errore chiaro (HTTP 422) senza che tu scriva un
solo `if`. È anche una difesa: quello che non è dichiarato non entra.

### `async def` e `await`

Servono per operazioni che **aspettano** qualcosa (rete, disco) senza bloccare tutto il programma.
Nel backend qui si usano poco — FastAPI gestisce bene la concorrenza anche con normali `def`. Nel
JavaScript del frontend invece sono ovunque, perché ogni `fetch()` è un'attesa di rete.

### JWT — il "biglietto" che prova chi sei

Una stringa firmata (`eyJhbGc...`) che contiene informazioni in chiaro ("sono l'admin", "scado
tra 8 ore"). **Chiunque può leggerla**, ma solo chi ha la chiave segreta può crearne una valida o
verificarla. Per questo funziona come prova d'identità senza tenere sessioni sul server.

Conseguenza pratica da ricordare: **un JWT non si può "revocare"** prima della scadenza. Se ne
esce uno di mano, resta valido finché non scade.

### Migrazione (Alembic)

Un file che descrive **un cambiamento** allo schema del database ("aggiungi la colonna X").
Servono perché un database con dati dentro non si può "riscrivere": va detto esattamente come
modificarsi, passo per passo. Ogni file ha `upgrade()` (applica) e `downgrade()` (annulla), ed è
concatenato al precedente — vedi la catena completa in `STATO_PROGETTO.md` §2.

---

## 3. Il giro completo di una prenotazione

Questa è la sezione da leggere per prima: una sola richiesta che attraversa **tutti** gli strati.
File coinvolti, in ordine: `index.html` → `app.js` → `routers/slots.py` → `routers/users.py` →
`routers/booking.py` → `models/` + `services/` → di nuovo `app.js`.

### Passo 1 — la pagina si apre e chiede gli orari liberi

`frontend/js/app.js` chiama `fetch('/slots/')`. Arriva a `backend/routers/slots.py`:

```python
ora_utc = ora_utc_naive()
slots = db.query(Slot).filter(
    Slot.is_available == True,
    Slot.start_time >= ora_utc
).all()
```

Due filtri, due motivi diversi:
- `is_available == True` → non mostrare slot già presi;
- `start_time >= ora_utc` → **non mostrare orari già passati**. Serve perché nulla marca uno slot
  come "scaduto": resta `is_available=True` per sempre finché qualcuno non lo prenota. Senza
  questo secondo filtro il form proporrebbe appuntamenti nel passato.

Nota che questo endpoint **non ha** `Depends(get_admin)`: è pubblico apposta, deve funzionare per
chi non ha nessun account.

### Passo 2 — lo studente compila e conferma

`app.js` fa **due** chiamate in sequenza: prima `POST /users/`, poi `POST /bookings/`.

`POST /users/` usa il pattern **"get or create"** (`get_or_create_user` in `routers/users.py`):

```python
existing = db.query(User).filter(User.email == user.email).first()
if existing:
    return existing
```

Perché non dare errore se l'email esiste già? Perché `email` è `unique` nel database: un secondo
utente con la stessa email non si potrebbe creare comunque. Invece di far fallire la richiesta, si
trasforma il vincolo in un comportamento utile — *"se questo studente ha già prenotato in passato,
ritrovalo"*.

L'endpoint risponde **solo con l'`id`**, non con il profilo completo. È deliberato: è un endpoint
pubblico, e restituire nome/telefono di un cliente esistente a chiunque ne indovini l'email
sarebbe una fuga di dati.

### Passo 3 — la prenotazione vera (`routers/booking.py`)

È il file più denso del progetto. I controlli, nell'ordine in cui girano:

**a) Lo slot esiste e non è passato**
```python
if slot.start_time <= ora_utc_naive():
    raise HTTPException(status_code=400, detail="This slot is in the past")
```
Il form mostra solo slot futuri, ma **il server non si fida mai del client**: chiunque può mandare
una richiesta HTTP diretta scavalcando l'interfaccia. Questo principio ritorna a ogni controllo qui
sotto — è la lezione più importante del file.

**b) Sessione da 2 ore = due slot da 1 ora uniti**

Il calendario genera **solo slot da 1 ora**. Una sessione da 2 ore quindi "unisce" lo slot scelto
con quello dell'ora successiva, e può iniziare **solo alle 15:00 o alle 17:00**:

```python
ORE_INIZIO_VALIDE_2H = {15, 17}
```

Non è un limite tecnico ma una scelta di prodotto: con l'orario 15:00–19:00 (quattro slot da 1h),
permettere anche le 16:00 creerebbe blocchi che si accavallano (15–17 e 16–18 non possono
coesistere) e lascerebbe più facilmente un'ora isolata invendibile.

**c) L'identità di chi prenota**

```python
if studente:
    user = studente          # dal token verificato dal server
else:
    if not booking.email: ... # 422
    if user.email != booking.email: ... # 403
```

Se sei loggato, l'identità viene **dal token**, e `booking.user_id` dal corpo della richiesta non
conta più nulla. Senza login (il "guest checkout", scelta voluta perché non c'è pagamento in-app)
non esiste un token, quindi l'unica prova possibile è che l'email dichiarata corrisponda a quella
dell'utente indicato. Non elimina il rischio, ma **alza il costo dell'attacco**: da "indovina un
numero sequenziale" a "conosci già l'email vera della vittima".

**d) Il claim atomico dello slot — il pezzo più importante del progetto**

Immagina due studenti che cliccano "Conferma" nello stesso istante. Se il codice facesse:

```python
if slot.is_available:          # 1. leggi
    slot.is_available = False  # 2. scrivi
```

esiste una finestra piccolissima ma reale tra il momento in cui si **legge** "libero" e quello in
cui si **scrive** "occupato". Se la seconda richiesta legge dentro quella finestra, trova ancora
"libero" — e finisci con due prenotazioni sullo stesso orario. Si chiama **race condition**: il
risultato dipende da chi vince la corsa, in modo imprevedibile.

La soluzione è chiedere al database di fare leggi-e-scrivi come **una sola operazione indivisibile**:

```python
esito = db.execute(
    update(Slot)
    .where(Slot.id == booking.slot_id, Slot.is_available == True)
    .values(is_available=False)
)
if esito.rowcount == 0:
    db.rollback()
    raise HTTPException(status_code=400, detail="Slot not available")
```

Si legge: *"metti occupato, **ma solo se** in questo momento è ancora libero"*. `rowcount` dice
quante righe sono state davvero modificate: se è `0`, qualcun altro è arrivato prima.

Per le sessioni da 2 ore il claim si ripete sul secondo slot, e se **quello** fallisce il
`rollback` annulla **anche il primo** — o si riservano entrambi, o nessuno.

> **Perché nessun vincolo `UNIQUE` a schema?** Sembrerebbe la difesa ovvia, ma è incompatibile con
> il flusso cancella/riprenota: uno slot cancellato torna prenotabile, e un vincolo di unicità lo
> impedirebbe. Decisione deliberata, vedi `STATO_PROGETTO.md` §7.

**e) Le notifiche arrivano dopo il salvataggio**

`db.commit()` prima, poi email cliente, email coach, messaggio Discord — **in quest'ordine e dopo**.
Se una notifica fallisce, la prenotazione resta valida: le notifiche sono un "di più", non una
condizione di successo. È il motivo per cui i service di email e Discord non sollevano mai
eccezioni verso chi li chiama.

---

## 4. Modulo per modulo

### `backend/main.py` — il punto d'ingresso

Il file gira in **due fasi distinte**, ed è la cosa da capire per prima:

1. **All'import** (Python legge il file): configura il logging, crea l'oggetto `app`, registra
   rate limiter e CORS, monta i router e i file statici.
2. **All'avvio del server**: FastAPI esegue `lifespan`, che applica le migrazioni e fa partire lo
   scheduler.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    scheduler = avvia_scheduler()
    yield                      # <-- qui il server vive e risponde
    scheduler.shutdown()
```

**Perché la divisione conta.** Se migrazioni e scheduler stessero fuori da `lifespan`, girerebbero
al semplice `import backend.main` — cioè anche quando a importare non è un server ma **i test**.
È successo davvero: lanciare `pytest` applicava le migrazioni al database di sviluppo reale e
poteva mandare un alert Discord autentico. Con `lifespan`, importare il modulo non fa nulla,
avviare un server fa tutto.

Il codice dopo lo `yield` è la chiusura ordinata — ciò che rende il ciclo di vita simmetrico.

### `backend/database.py` — la connessione

```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
```

`create_engine` **non apre** una connessione: prepara solo il "come" connettersi. La prima
connessione vera avviene quando qualcuno la usa davvero.

`pool_pre_ping=True` risolve un problema concreto: le connessioni vengono riusate da un "pool",
ma un database può chiudere una connessione rimasta ferma troppo a lungo. Senza il ping
preventivo, la prima richiesta dopo una pausa fallirebbe con un errore incomprensibile. Con esso,
SQLAlchemy verifica che la connessione sia viva prima di consegnartela.

`DATABASE_URL` è obbligatoria e l'app **muore subito** se manca — un fallimento esplicito
all'avvio è molto meglio di uno silenzioso che si manifesta più tardi.

### `backend/models/` — le tabelle

Una classe = una tabella, un attributo `Column(...)` = una colonna. Otto tabelle in tutto.

Il caso più istruttivo è `booking.py`, che ha **due** colonne verso la stessa tabella `slots`:

```python
slot_id            = Column(Integer, ForeignKey("slots.id"), nullable=False)
slot_id_secondario = Column(Integer, ForeignKey("slots.id"), nullable=True)
...
slot = relationship("Slot", foreign_keys=[slot_id], backref="booking")
```

Serve `foreign_keys=[...]` esplicito perché con due strade verso la stessa tabella SQLAlchemy non
può indovinare quale intendi. **Conseguenza pratica che ti morderà:** da quel momento
`.join(Slot)` diventa ambiguo e va scritto `.join(Booking.slot)`. Se vedi quella forma in giro per
il progetto, il motivo è questo.

`relationship()` non crea nessuna colonna: è solo la scorciatoia Python per navigare
(`prenotazione.user.nome`). `backref` crea il collegamento inverso (`utente.bookings`).

### `backend/schemas/` — la forma dei messaggi

Di norma una coppia `...Create` / `...Response` per area, ma **non è una regola rigida**: si segue
quello che l'API fa davvero. `consulenza.py` ha solo il `Create` (quell'endpoint risponde con un
messaggio fisso); `booking.py` ne ha cinque, perché servono forme diverse per il cambio di stato,
per le note e per la vista ridotta dello studente.

Il caso più didattico è **`BookingResponseStudente`**: identico a `BookingResponse` **tranne**
`note_admin`. Le note interne sono documentate come "visibili solo al coach", quindi non devono
comparire in una risposta che lo studente stesso può leggere. È l'esempio pratico di *perché*
schema e model sono separati: il dato esiste, ma per quel destinatario non si espone.

In `schemas/slots.py` c'è l'altro pezzo interessante — la conversione di fuso avviene **nel
validator**, cioè al confine: quando il codice del router gira, l'orario è già in UTC.

### `backend/services/` — logica riusabile e mondo esterno

| File | Cosa fa | Perché esiste separato |
|---|---|---|
| `timezone_service.py` | conversioni UTC ↔ Roma, confronto intervalli | la stessa conversione serviva in una dozzina di punti |
| `auth_service.py` | crea/verifica JWT admin e studente | un claim `"type"` impedisce di usare un token studente come admin |
| `email_service.py` | invio via API Gmail | SMTP è **bloccato** dalla rete di Railway |
| `calendar_service.py` | eventi Google Calendar | scrittura e lettura, per il sync |
| `discord_service.py` | notifiche via webhook | un URL segreto, senza dover scrivere un bot |
| `availability_service.py` | genera slot da regola, blocchi, overlap, pulizia | il cuore del calendario |
| `retention_service.py` | anonimizza clienti inattivi | obbligo GDPR |
| `backup_service.py` | dump SQL + upload su Drive | il piano Railway non include backup |
| `booking_service.py` | libera slot ed evento alla cancellazione | serviva identica a cliente e admin |
| `pagination_service.py` | sanifica pagina/per_pagina | le tre liste admin ripetevano lo stesso codice |
| `google_oauth_service.py` | credenziali OAuth con cache | evitava un giro HTTPS a ogni email |

**La convenzione sui fusi orari, che vale per tutto il progetto:** nel database si salva **sempre
UTC**, senza fuso attaccato ("naive"). La conversione a ora italiana avviene **solo al momento di
mostrare** un orario a un umano, mai nel mezzo. Se ti trovi a convertire dentro la logica, quasi
certamente stai sbagliando qualcosa.

```python
def ora_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

`.replace(tzinfo=None)` **non cambia i numeri**, toglie solo l'etichetta del fuso — serve perché
confrontare un orario "con fuso" e uno "senza" in Python è un errore.

### `backend/routers/` — gli indirizzi

Ogni file raggruppa endpoint con un prefisso comune. `admin/` è un **package** (una cartella con
`__init__.py`) invece di un file solo, perché era diventato oltre 1000 righe: `__init__.py`
definisce l'autenticazione condivisa e il login, poi assembla i sotto-router per area.

L'ordine degli import in quel file **non è casuale**: i sotto-router vengono importati *in fondo*,
dopo che `get_admin` è stato definito, perché ognuno di loro lo importa da lì.

### `backend/scheduler.py` — le cose che accadono da sole

È l'unico punto dove il codice gira **senza che una richiesta lo attivi**, quindi serve una
libreria diversa da FastAPI: APScheduler, che esegue funzioni a intervalli su un thread separato.

Otto job: promemoria, richieste di recensione, sync calendario, generazione slot notturna,
controllo del token Gmail, retention GDPR, pulizia slot, backup del database.

Due dettagli che vale la pena notare:

```python
db = SessionLocal()
try:
    ...
finally:
    db.close()
```
Qui **non** c'è `Depends(get_db)`: non si è dentro una richiesta web, quindi la sessione va aperta
e chiusa a mano.

E il `commit()` sta **dentro** il ciclo, non alla fine: così, se il programma si interrompe a
metà, i promemoria già mandati non vengono rimandati al giro successivo.

> **Trappola da sapere:** i job notturni usano il fuso **del processo**, non Europe/Rome. Su
> Railway il processo gira in UTC, quindi le "03:00" nel codice sono le 05:00 italiane d'inverno.
> Nessun impatto pratico, ma spiega perché i log non tornano con l'orologio.

### `frontend/` — quello che vede l'utente

Cinque pagine, nessun framework. Il JavaScript chiama gli endpoint con `fetch()`, riceve JSON e
aggiorna la pagina modificando l'HTML direttamente.

`js/i18n.js` è il sistema di traduzione italiano/inglese di `index.html`, `about.html` e
`privacy.html`: ogni testo statico porta un attributo `data-i18n="chiave"` che viene sostituito
con la voce del dizionario. Il pannello admin non lo usa — è solo per il coach, resta in italiano.

**Una lezione di sicurezza che questo progetto ha imparato sul campo.** Il pannello admin mostra
dati scritti dal pubblico (il nome del cliente arriva dal form senza login). Se quel testo finisce
in un punto dove il browser lo interpreta come **codice** invece che come **testo**, un estraneo
può far eseguire istruzioni nel browser del coach: si chiama **XSS**.

La difesa non è "sfuggire meglio i caratteri", è **non mescolare dato e codice**:

```javascript
// SBAGLIATO — il nome finisce dentro codice JavaScript generato come stringa
onclick="apriPacchetto(${id}, '${nome}')"

// GIUSTO — il bottone porta solo un numero; il nome si ritrova a parte
<button data-azione="pacchetto" data-id="${id}">
```

E dove un dato *deve* comparire nell'HTML, si passa da `escapeHtml()`, che trasforma i caratteri
speciali in simboli innocui. Attenzione però: **quella funzione è adatta al testo, non agli
attributi** — vale per il contenuto di un tag, non per costruire codice. Il contesto in cui metti
il dato decide quale difesa serve.

---

## 5. Per chi deve mettere le mani nel codice

Regole pratiche ricavate da errori realmente commessi in questo progetto:

1. **Non fidarti mai del client.** Ogni controllo fatto nel form va rifatto nel server: chiunque
   può mandare una richiesta HTTP diretta.
2. **L'identità viene dal token, mai dal corpo della richiesta.** Se un endpoint tocca dati legati
   a un utente, quell'`user_id` deve arrivare da `get_studente`/`get_admin`.
3. **Aggiungi una colonna → serve una migrazione.** Cambiare solo il model non modifica il
   database reale.
4. **Orari: UTC nel database, conversione solo per mostrarli.**
5. **Non mettere dati non fidati dentro codice generato come stringa** (né HTML né SQL).
6. **Se un endpoint nuovo restituisce dati, chiediti chi può leggerli** — e se serve uno schema
   di risposta ridotto.
7. **Se scrivi un commento che afferma un fatto** (una scadenza, un limite, una decisione),
   verificalo prima: in questo progetto un commento sbagliato sulla scadenza dei token è
   sopravvissuto per settimane.

### Come verificare di non aver rotto niente

```bash
pytest                                    # database SQLite in memoria, servizi esterni finti
uvicorn backend.main:app --reload         # avvio locale
```

La suite non tocca MySQL né i servizi esterni: usa un database in memoria e integrazioni finte.
Gira anche in CI su ogni push.
