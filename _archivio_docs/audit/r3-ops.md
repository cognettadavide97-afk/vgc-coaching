# Revisione 3 — SRE / affidabilità in produzione

**Mandato:** cosa fa questo codice quando le cose vanno male. Blocking I/O,
timeout, retry, eccezioni silenziate, stato incoerente dopo un fallimento
parziale, sessioni e connessioni, qualità dei log. Più un'analisi specifica della
divergenza SQLite (locale/test) vs MySQL (produzione).
**Perimetro:** `backend/`, `alembic/`, `nixpacks.toml`, `tests/conftest.py`.
**Metodo:** lettura del codice **più verifica dinamica**. Ho misurato a runtime i
valori di default che determinano il comportamento sotto stress (pool, thread,
timeout, scheduler) invece di citarli a memoria. Nessun altro documento di
`audit/` è stato letto.
**Domanda guida:** alle 3 di notte, con i soli log, riesco a capire cos'è successo?

---

## 1. Risposta alla domanda guida: no, e per un motivo preciso

Non è una carenza generica di logging — è un'inversione. Nel punto in cui il
sistema funziona, il log dice **chi**; nel punto in cui fallisce, non lo dice.

```python
# email_service.py:150   (successo)
logger.info(f"Email inviata a {email_cliente}")
# email_service.py:151-152  (fallimento)
except Exception:
    logger.exception("Errore invio email")
```

La riga che serve alle 3 di notte è la seconda, ed è l'unica senza contesto. Lo
stesso schema in `calendar_service.py:138` (`"Errore Google Calendar"`: nessun
booking, nessuno slot, nessun cliente) e in `discord_service.py:51`.

A questo si somma che `LOG_FORMAT` (`main.py:22`) non porta alcun
identificativo di richiesta o di prenotazione, e che `asctime` usa l'ora locale
del processo — UTC in produzione, come lo stesso progetto riconosce a
`scheduler.py:372-376` — mentre ogni orario mostrato al coach è ora di Roma.

**Scenario concreto.** Un cliente scrive: *"ho prenotato ieri alle 20:00 e non ho
ricevuto nulla."* Con i log a disposizione si trova `ERROR ... Errore invio
email` alle 18:04 UTC. Non c'è modo di stabilire se sia la sua. Non c'è modo di
sapere quali altre prenotazioni della stessa finestra siano rimaste senza email.
E per via di **§O2**, il database dice che l'email è stata inviata.

Il rimedio più economico del report è qui: mettere un identificativo nelle righe
di errore. **30 minuti**, e la maggior parte del problema sparisce.

---

## 2. I numeri che decidono il comportamento sotto carico

Misurati a runtime su questo progetto, non citati da documentazione.

| Parametro | Valore | Dove |
|---|---|---|
| Endpoint dichiarati `async def` | **0** | tutti sincroni → threadpool |
| Thread del threadpool Starlette | **40** | default anyio, misurato |
| Connessioni DB massime | **15** (pool 5 + overflow 10) | `database.py:26`, misurato |
| Attesa massima per una connessione | **30 s**, poi eccezione | misurato |
| `pool_recycle` | **-1** (mai) — coperto da `pool_pre_ping` | `database.py:26` |
| Timeout chiamate Google (Calendar/Gmail/Drive) | **60 s** | `googleapiclient/http.py:75,1944-1948` |
| Timeout refresh credenziali Google | **120 s** | `google/auth/transport/requests.py:47` |
| Timeout Discord webhook / OAuth | 5 s / 10 s ✓ | `discord_service.py:47`, `discord_auth.py:113,122` |
| `socket.setdefaulttimeout` | **mai chiamato** | i 60 s restano il default |
| APScheduler `misfire_grace_time` | **1 secondo** | `apscheduler/.../base.py:911` |
| APScheduler `max_instances` / `coalesce` | 1 / True | idem |
| Retry su chiamate esterne | **nessuno, in nessun punto** | — |

Due squilibri saltano fuori da soli: **40 thread contro 15 connessioni** (§O4), e
un **timeout di 60 secondi dentro una transazione che tiene un lock** (§O3).

---

## 3. Findings

### O1 — BLOCCANTE — Il backup non ha modo di accorgersi di non essere partito

`backend/scheduler.py:326-341,428-435,420-424` — `apscheduler/schedulers/base.py:911` —
`backend/services/backup_service.py:1-6`

**[VERIFICATO]** L'unico avviso sul backup si attiva quando
`esegui_backup_database` **restituisce** `False` (`scheduler.py:333-341`). Se il
job non viene eseguito, non restituisce nulla e non avvisa nessuno.

E non essere eseguito è facile. Il job è `cron day_of_week="sun", hour=4`, e
APScheduler usa `misfire_grace_time = 1` **secondo**: se allo scoccare
dell'orario lo scheduler non è in condizione di partire — un deploy, un riavvio
del container, un restart di Railway, il threadpool saturo di §O4 — l'esecuzione
viene **saltata del tutto**, non rimandata. APScheduler lo registra come
`Run time of job ... was missed by ...`, a livello WARNING, in un log che alle
04:00 di domenica non guarda nessuno.

La stessa proprietà vale per il controllo credenziali delle 03:30 di domenica
(`scheduler.py:393-400`), cioè per la sonda che dovrebbe avvisare *prima* che il
backup salti.

Il peso lo dà il modulo stesso (`backup_service.py:1-6`): *"Il piano di hosting
in uso non include backup né point-in-time recovery per il database: senza questo
modulo un guasto al volume significherebbe perdita totale dei dati."* Il commento
a `scheduler.py:420-424` dichiara che la finestra di perdita massima passa da 24
ore a 7 giorni, *"accettata consapevolmente, non subita"*. Quel calcolo assume
che il job parta. Senza rilevamento dell'assenza, la finestra reale non è di 7
giorni: è **indefinita, fino a quando qualcuno non apre a mano la cartella
Drive**.

**Intervento minimo.** Un allarme che scatta sull'**assenza** invece che sul
fallimento: un job giornaliero che legge la data del file più recente nella
cartella Drive (`files().list` con `orderBy="createdTime desc"`, il codice per
elencare esiste già a `backup_service.py:146-149`) e avvisa se è più vecchio di 8
giorni. In più `misfire_grace_time=3600` sui job cron, così un riavvio non fa
perdere l'esecuzione. **Costo: 3 ore.**

---

### O2 — ALTA — `reminder_sent` e `review_email_sent` registrano "ho provato", non "è arrivata"

`backend/scheduler.py:139-157,195-198` — `backend/services/email_service.py:186-190,335-339`

**[VERIFICATO — riprodotto]** Ho reso Gmail irraggiungibile e fatto girare il job:

```
prenotazioni elaborate: 1
email realmente inviata? NO  (ConnectionError inghiottito da email_service.py:189)
reminder_sent nel database -> True
```

`invia_promemoria_cliente` cattura ogni eccezione, la registra e **non restituisce
nulla**: il chiamante non ha modo di distinguere un invio riuscito da uno
fallito, e imposta `reminder_sent = True` in entrambi i casi
(`scheduler.py:156`). La prenotazione esce per sempre dal filtro
`Booking.reminder_sent == False` (`scheduler.py:125`): **non sarà mai ritentata**.

Il commento a `scheduler.py:154-155` motiva il commit dentro il ciclo con *"se
l'esecuzione si interrompe, i promemoria già inviati non vengono ripetuti"* —
l'intenzione è corretta e riguarda il crash. Ma la stessa riga assorbe anche il
caso ordinario e frequente: Gmail che risponde 503 per trenta secondi. In quella
finestra, **ogni promemoria del lotto viene perso in silenzio e marcato come
inviato**.

Conseguenza di business diretta: il cliente non riceve il promemoria, non si
presenta, e il coach registra un no-show. Identico per
`review_email_sent` (`scheduler.py:197`).

**Intervento minimo.** Le funzioni di invio restituiscono `True`/`False` — il
`try/except` che serve è già scritto (`email_service.py:148-152`), manca solo il
valore di ritorno — e il flag si imposta solo su `True`. **Costo: 2 ore** per
tutti i mittenti.

---

### O3 — ALTA — Una chiamata a Google che rallenta tiene un lock di riga InnoDB fino a 60 secondi

`backend/routers/booking.py:178-182,213,245` — `googleapiclient/http.py:75,1944-1948`

**[VERIFICATO nel codice; il comportamento InnoDB è [SOSPETTO], vedi conferma]**

L'ordine delle operazioni in `create_booking` è questo:

```
:178   db.execute(update(Slot).where(...is_available == True).values(is_available=False))
:213   event_id = crea_evento_calendario(...)        # rete, timeout 60 s
:245   db.commit()
```

L'`UPDATE` di riga 178 è eseguito **subito** — è una `db.execute` esplicita, non
un flush differito — quindi su InnoDB prende un lock esclusivo sulla riga di
`slots`, che resta tenuto fino al commit di riga 245. In mezzo c'è una chiamata
HTTP a Google con un timeout di **60 secondi** (`DEFAULT_HTTP_TIMEOUT_SEC = 60`,
e `socket.setdefaulttimeout` non è mai chiamato in questo progetto).

Se Google rallenta, quel lock resta appeso per un minuto. Le altre richieste
sullo stesso slot si mettono in attesa e, superato
`innodb_lock_wait_timeout` (default MySQL **50 secondi**), muoiono con
l'errore 1205 → 500 al cliente, su uno slot che è perfettamente sano.

**In locale è invisibile per costruzione.** SQLite con `StaticPool`
(`conftest.py:32-36`) serializza tutto su una sola connessione, e **non esiste
alcun test di concorrenza** in tutta la suite (nessuna occorrenza di
`thread`/`concurrent` nei test, a parte il conteggio thread di `test_avvio.py`).
Il claim atomico di riga 178 — la difesa più raffinata del progetto, quattordici
righe di commento — non è mai stato esercitato sotto concorrenza vera.

**[SOSPETTO — si conferma così:** su MySQL, aprire due sessioni; nella prima
eseguire `START TRANSACTION; UPDATE slots SET is_available=0 WHERE id=<x> AND
is_available=1;` **senza commit**; nella seconda ripetere lo stesso `UPDATE`.
Se la seconda resta appesa fino a `innodb_lock_wait_timeout`, è confermato. **]**

**Intervento minimo.** Spostare `crea_evento_calendario` **dopo** `db.commit()`,
accanto alle tre notifiche che stanno già lì (`booking.py:248-276`) e per lo
stesso motivo dichiarato a riga 248 (*"sono accessorie, e un loro fallimento non
deve invalidare una prenotazione già salvata"*), scrivendo poi
`calendar_event_id` con un secondo `UPDATE` breve. La transazione si chiude in
millisecondi. **Costo: 2 ore.**

---

### O4 — ALTA — 40 thread contro 15 connessioni: la saturazione arriva dal database, e porta giù anche `/health`

`backend/database.py:26,33-44` — `backend/main.py:172-185` — `backend/scheduler.py:117,169,212,228,245,311`

**[VERIFICATO — misurato a runtime]**

```
classe pool     : QueuePool        pool_size: 5     max_overflow: 10
connessioni max : 15               attesa max: 30.0 s     pool_recycle: -1
thread anyio    : 40
```

Nessun endpoint è `async def`: FastAPI li esegue tutti nel threadpool, quindi
fino a 40 richieste possono essere in volo insieme, ciascuna con una sessione
aperta da `get_db`. Dalla sedicesima in poi si attende fino a 30 secondi, poi
`TimeoutError: QueuePool limit of size 5 overflow 10 reached` → 500. Al pool
attinge anche il thread dello scheduler, che apre una propria sessione in sei job
diversi.

§O3 rende lo scenario raggiungibile senza traffico anomalo: ogni prenotazione
tiene la connessione per tutta la durata della chiamata a Google.

Il dettaglio che trasforma un rallentamento in un incidente è `/health`
(`main.py:172-185`): esegue `SELECT 1` e quindi **ha bisogno anch'esso di una
connessione dal pool**. Con il pool saturo l'health check fallisce insieme a
tutto il resto. La scelta di interrogare il database è motivata bene
(`main.py:176-179`) e la condivido; l'effetto collaterale non è stato considerato.

**[SOSPETTO — si conferma così:** verificare nelle impostazioni del servizio
Railway se è configurato un health check su `/health` e con quale soglia. Se c'è,
un pool saturo provoca il riavvio di un processo che è soltanto occupato,
azzerando le prenotazioni in corso e peggiorando la coda. **]**

**Intervento minimo.** Allineare i due numeri: `pool_size=20, max_overflow=10`
oppure limitare il threadpool. E separare le due domande in `/health`: `200` se il
processo vive, `503` con dettaglio solo se il database è irraggiungibile —
distinguendo "irraggiungibile" da "pool esaurito", che sono guasti diversi.
**Costo: 2 ore** più una prova di carico.

---

### O5 — ALTA — Divergenza SQLite/MySQL: le foreign key non sono applicate nei test

`tests/conftest.py:32-36,67` — `backend/routers/admin/clients.py:114-128` —
`backend/routers/admin/availability.py:92-97`

**[VERIFICATO — riprodotto]**

```
PRAGMA foreign_keys nella sessione di test -> 0   (disattivato)
INSERT booking con user_id=999999 e slot_id=888888 inesistenti -> ACCETTATO
```

SQLite non applica le foreign key se non si esegue `PRAGMA foreign_keys=ON` su
**ogni** connessione, e in questo progetto non lo fa nessuno. MySQL/InnoDB le
applica sempre (errno 1452).

Il punto dove la differenza morde è `elimina_cliente`
(`clients.py:95-133`), la cancellazione GDPR. L'ordine delle eliminazioni —
recensione, prenotazione, note, pacchetti, utente — **è un vincolo reale in
produzione e una formalità nei test**. Il commento a `clients.py:119-120` lo
spiega correttamente (*"La recensione referenzia la prenotazione: va eliminata
prima"*), ma nessun test può verificarlo: sotto SQLite qualunque ordine passa.

Se un domani quell'ordine cambia, la suite resta verde e il primo guasto arriva
su una richiesta di cancellazione di un cliente reale — cioè proprio
l'operazione che non si può ritentare con leggerezza, perché fallisce **a metà**:
prenotazioni già eliminate, utente ancora presente, e nessuna transazione che lo
annulli, dato che il `db.commit()` è uno solo alla fine (`clients.py:132`) ma
l'eccezione arriverebbe lì, lasciando la sessione da rollbackare senza che
nessuno lo dica all'amministratore.

Lo stesso vale per `elimina_slot` (`availability.py:75-107`): il commento a
`:92-94` indica esplicitamente il vincolo di chiave esterna come rete di
sicurezza dietro il controllo manuale. Quella rete, in locale, non c'è.

**Intervento minimo.** Quattro righe in `conftest.py`:

```python
from sqlalchemy import event
@event.listens_for(TEST_ENGINE, "connect")
def _abilita_fk(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

**Costo: 30 minuti.** È il miglior rapporto valore/costo del report: allinea la
semantica di test a quella di produzione su una classe intera di errori.

---

### O6 — MEDIA — [SOSPETTO] `created_at` è l'ora del server MySQL, non necessariamente UTC

`backend/models/users.py:32` — `booking.py:55` — `slots.py:36` — `package.py:34` —
`review.py:24` — `client_note.py:19` — `availability_rule.py:34` —
`availability_exception.py:23` — `backend/services/timezone_service.py:3-6,29-31`

**[VERIFICATO nel codice]** Tutti e otto i model dichiarano
`created_at = Column(DateTime, default=func.now())`. `func.now()` viene tradotto
in `CURRENT_TIMESTAMP` su SQLite — **sempre UTC** — e in `NOW()` su MySQL, che
restituisce l'ora **del fuso di sessione del server**.

La convenzione dichiarata del progetto è "nel database gli orari sono sempre UTC
naive" (`timezone_service.py:3-6`), e `utc_to_rome` etichetta senza verificare
qualunque valore naive come UTC (`timezone_service.py:29-31`). Se il MySQL di
Railway non è impostato su UTC, ogni `created_at` è salvato in un altro fuso e
poi spostato **una seconda volta** verso Roma in visualizzazione:
`admin/bookings.py:86`, `admin/clients.py:87`, `admin/reviews.py:48`
sarebbero tutti sfalsati di una costante. In locale lo stesso codice è corretto,
perché SQLite è UTC per definizione.

**[SOSPETTO — si conferma così:** sul database di produzione,
`SELECT @@global.time_zone, @@session.time_zone, NOW(), UTC_TIMESTAMP();`
Se `NOW()` differisce da `UTC_TIMESTAMP()`, è confermato. **]**

**Intervento minimo.** `default=ora_utc_naive` al posto di `func.now()`: la
funzione esiste già (`timezone_service.py:45-52`), calcola in Python ed è
identica sui due motori. Una migrazione di correzione dei dati storici serve solo
se la conferma è positiva. **Costo: 1 ora.**

---

### O7 — MEDIA — [SOSPETTO] Confronti fra stringhe: MySQL è case-insensitive, SQLite no

`backend/routers/users.py:111` — `backend/routers/discord_auth.py:150` —
`backend/models/users.py:17` — `backend/models/booking.py:52`

**[VERIFICATO nel codice]** La collation predefinita di MySQL 8 è
`utf8mb4_0900_ai_ci`: insensibile a maiuscole **e** accenti. Su SQLite il
confronto `=` fra TEXT è binario. Nessun `collate` esplicito compare nei model.

Ne conseguono comportamenti opposti nei due ambienti:

- `get_or_create_user` (`users.py:111`, `filter(User.email == user.email)`):
  `Mario@Example.com` e `mario@example.com` sono **lo stesso cliente** in
  produzione e **due clienti distinti** in locale;
- l'indice `unique` su `email` (`models/users.py:17`) rifiuta il secondo
  inserimento in produzione e lo accetta in locale — quindi un test che
  verificasse il comportamento "get or create" su email di case diverso darebbe
  esito opposto rispetto alla realtà;
- il fallback per email nel login Discord (`discord_auth.py:150`) è una
  **decisione di autorizzazione**, e dipende da questa semantica.

Il confronto del token di recensione **non** è coinvolto: l'indice `unique` su
`review_token` (`models/booking.py:52`) è anch'esso `ai_ci`, ma il confronto
effettivo è `secrets.compare_digest` in Python (`booking.py:354`), che è binario.
Nessuna conseguenza di autorizzazione, solo un indice semanticamente più stretto
del dovuto.

**[SOSPETTO — si conferma così:** sul database di produzione,
`SELECT @@collation_database;` e `SELECT 'A' = 'a';` — se il secondo restituisce
`1`, è confermato. **]**

**Intervento minimo.** Normalizzare l'email in minuscolo con un validator su
`UserCreate` (`schemas/users.py:18`), così il comportamento smette di dipendere
dal motore. **Costo: 1 ora.**

---

### O8 — MEDIA — L'unico codice MySQL puro del progetto è anche l'unico mai eseguito fuori dalla produzione

`backend/services/backup_service.py:73-124` — `tests/test_backup_service.py:31`

**[VERIFICATO]** `crea_dump_sql` usa `SHOW TABLES`, `SHOW CREATE TABLE`,
`SET FOREIGN_KEY_CHECKS` e `connessione.escape()`: nessuno dei quattro esiste su
SQLite, e `engine.raw_connection()` su SQLite non espone `.escape`. La funzione
**non può girare in locale**, e infatti non ci prova: il test la sostituisce con
`lambda engine: "-- dump finto"` (`test_backup_service.py:31`).

I tre test del file verificano il contorno — che il backup venga saltato senza
configurazione, che chiami upload e pulizia, che un fallimento restituisca
`False` senza sollevare — e sono test corretti. Ma **la funzione che produce il
backup non viene eseguita da nessun test**. Gira una volta a settimana, in
produzione, senza nessuno a guardare, e il suo prodotto non viene mai verificato:
nessuno ha mai provato a ripristinare un dump.

Sommato a §O1: un artefatto che nessuno produce sotto osservazione, nessuno
valida, e della cui assenza nessuno si accorge.

**Intervento minimo, in ordine di costo.** (a) Prima di caricare, verificare che
il dump contenga una `CREATE TABLE` per ciascuna tabella di `Base.metadata` e non
sia vuoto: trasforma il fallimento silenzioso in un `False`, che l'allarme già
gestisce — **1 ora**. (b) Un test in CI contro un MySQL vero (service container
in `.github/workflows/tests.yml`) che fa dump e ripristino su uno schema di
appoggio — **mezza giornata**, e chiude anche §O5, §O6 e §O7 in un colpo solo.

---

### O9 — MEDIA — Tre guasti silenziosi del calendario, con conseguenze visibili solo al coach il giorno della sessione

`backend/services/calendar_service.py:137-139,186-188,243-244,68-70` —
`backend/routers/admin/availability.py:62-73` — `frontend/js/admin.js:886`

**[VERIFICATO]** Nessuna funzione del modulo propaga eccezioni — scelta
dichiarata a `calendar_service.py:6-7` e sensata in sé. Il problema è che a valle
non resta **nessun** segnale:

1. `crea_evento_calendario` restituisce `None` (`:139`): la prenotazione viene
   salvata con `calendar_event_id = None` (`booking.py:234`) e **la sessione non
   compare sul calendario del coach**. Il cliente ha la sua conferma, il coach non
   ha nulla. Se ne accorge quando il cliente si presenta.
2. `elimina_evento_calendario` fallisce (`:243-244`): la prenotazione risulta
   cancellata, l'evento resta. Il coach blocca del tempo per una sessione che non
   ci sarà.
3. `leggi_eventi_calendario` restituisce `[]` in caso di errore (`:188`), quindi
   `sincronizza_slot_con_calendario` restituisce `0` sia quando non c'è nulla da
   bloccare **sia quando Google è irraggiungibile**. L'amministratore preme il
   pulsante e legge `Sincronizzazione completata: 0 slot bloccati`
   (`admin.js:886`) nei due casi. Un messaggio di successo per un guasto.

La sonda credenziali non copre niente di tutto questo, e lo dichiara:
`calendar_service.py:68-70` avverte che *"verifica l'identità, non il permesso"*
— un calendario che smettesse di essere condiviso darebbe credenziali valide e
sincronizzazione ferma.

**Intervento minimo.** Il primo caso è una condizione interrogabile:
`status = 'confirmed' AND calendar_event_id IS NULL`. Un job giornaliero che la
conta e avvisa se è maggiore di zero trasforma il guasto più costoso dei tre in
un allarme. Per il terzo, distinguere il valore di ritorno: `None` per errore, un
intero per successo. **Costo: 2 ore.**

---

### O10 — MEDIA — I log non permettono di ricostruire un incidente

`backend/main.py:21-23` — `backend/services/email_service.py:150-152,188-190` —
`backend/services/calendar_service.py:138` — `backend/services/discord_service.py:51`

**[VERIFICATO]** È il §1 di questo report, qui in forma di finding. Nessuna riga
di log del progetto contiene un identificativo di prenotazione, cliente o
richiesta. Le righe di errore delle tre integrazioni sono stringhe fisse; il
contesto compare solo nelle righe di successo.

**Intervento minimo.** Due passi indipendenti: (a) aggiungere l'identificativo
alle righe di errore — `logger.exception("Errore invio email a booking_id=%s", booking_id)`
— **30 minuti**, e copre la maggior parte dei casi reali; (b) un middleware che
genera un id di richiesta e lo mette in `LOG_FORMAT` via `contextvars` —
**2 ore**.

---

### O11 — MEDIA — Nessun retry, in nessun punto del progetto

`backend/services/discord_service.py:47` — `backend/services/email_service.py:98` —
`backend/services/calendar_service.py:129,154,239` — `backend/services/backup_service.py:135,152`

**[VERIFICATO]** Ogni chiamata esterna è un colpo solo. `requests.post` non
ritenta; `googleapiclient` ritenta solo se gli si passa `num_retries`, che qui
non viene mai passato (default `0`).

Un 503 di Gmail che dura dieci secondi perde definitivamente quell'email — e per
§O2 la marca come inviata. Un singolo errore di rete verso il webhook Discord
perde la notifica di una prenotazione.

La cura non è uniforme e va scelta operazione per operazione, perché **non tutte
sono idempotenti**: ritentare `events().insert` (`calendar_service.py:129`) senza
precauzioni crea un evento duplicato sul calendario del coach. Le letture
(`events().list`, `files().list`) e le notifiche sono invece ritentabili
liberamente.

**Intervento minimo.** `num_retries=3` sulle `.execute()` di sola lettura; tre
tentativi con attesa crescente dentro `_invia_embed` (`discord_service.py:33`) e
`_invia_via_gmail` (`email_service.py:81`), che sono già i punti unici di uscita.
Per l'inserimento sul calendario, o si lascia com'è o gli si assegna un id
deterministico derivato dal `booking_id`, che rende il ritentativo idempotente.
**Costo: 2 ore.**

---

### O12 — BASSA — L'avvio prosegue su uno schema potenzialmente sbagliato, e l'unico avviso può sparire in silenzio

`backend/main.py:86-108,121-122` — `backend/services/discord_service.py:39-51`

**[VERIFICATO]** La scelta di non bloccare l'avvio su una migrazione fallita è
deliberata e motivata (`main.py:80-84`), e il commento ne dichiara anche il
costo. Tre aspetti che il commento non copre:

1. **L'avviso può fallire a sua volta.** `invia_alert_sistema` finisce in
   `_invia_embed`, che cattura le proprie eccezioni (`discord_service.py:50-51`)
   e, se `DISCORD_WEBHOOK_URL` manca, si limita a un `warning` (`:39-41`). Se
   Discord è irraggiungibile nello stesso momento — eventualità tutt'altro che
   remota durante un deploy problematico — l'app parte con lo schema sbagliato e
   **nessun segnale raggiunge nessuno**.
2. **`command.upgrade` non ha timeout.** Su MySQL una migrazione può restare
   appesa su un metadata lock: l'app non diventa mai pronta e Railway la riavvia,
   in un ciclo il cui unico indizio nei log è l'assenza della riga
   `Migrazioni eseguite con successo`.
3. **Il DDL di MySQL non è transazionale**, quello di SQLite sì. Una migrazione
   che fallisce a metà lascia in produzione uno schema parzialmente applicato —
   stato che in locale non può verificarsi.

**Intervento minimo.** Registrare l'esito in una variabile di modulo che
`/health` sappia leggere, e rispondere `503` con `{"stato": "degradato",
"motivo": "migrazioni"}`: il monitoraggio esterno già configurato se ne accorge
senza dipendere da Discord. **Costo: 2 ore.**

---

### O13 — BASSA — [SOSPETTO] Con più di una replica, gli otto job girano in parallelo

`backend/scheduler.py:49-53,344-437` — `backend/main.py:121-122` —
`backend/services/availability_service.py:96-100`

**[VERIFICATO nel codice]** Lo scheduler parte dentro il processo web
(`main.py:122`), senza elezione di un leader né lock condiviso. Il progetto è già
consapevole del tema per un caso: `_ultimo_controllo_credenziali`
(`scheduler.py:49-53`) è documentato come stato per-processo.

Con due repliche, i punti che si rompono sono check-then-write:

- `controlla_e_invia_promemoria`: la finestra fra la lettura
  (`scheduler.py:122-127`) e il commit del flag (`:156`) è larga quanto un invio
  email — **due promemoria per lo stesso cliente**;
- `genera_slot_da_regola`: `esiste_gia = db.query(Slot)...` seguito da `db.add`
  (`availability_service.py:97-99`) — **slot duplicati**;
- `run_migrations`: due `alembic upgrade` simultanei all'avvio, senza lock;
- due backup contemporanei che leggono l'intero database (§O14).

**[SOSPETTO — si conferma così:** leggere il numero di repliche nelle
impostazioni del servizio su Railway; oppure verificare se per una singola
prenotazione compaiono due righe `Notifica Discord inviata` nei log. **]**

**Intervento minimo.** Se le repliche sono più di una, spostare lo scheduler in
un servizio Railway separato con una sola istanza. Risolve anche metà di §O4,
perché lo scheduler smette di competere per il pool del processo web.
**Costo: mezza giornata.**

---

### O14 — BASSA — Il dump legge l'intero database in memoria, e ne tiene tre copie

`backend/services/backup_service.py:104,110-118,122,129-131`

**[VERIFICATO]** `cursore.fetchall()` carica ogni tabella per intero (`:104`);
`righe_dump` accumula tutte le stringhe (`:110-118`); `"\n".join` ne crea una
copia unica (`:122`); `.encode("utf-8")` dentro `io.BytesIO` ne crea una terza
(`:129-131`). Il picco è dell'ordine di tre volte la dimensione del database.

Oggi il volume è piccolo e non è un problema. Il modo in cui smetterà di non
esserlo è un OOM kill alle 04:00 di domenica, la cui unica traccia è un riavvio
del container — e che §O1 rende invisibile, perché il job non arriva mai a
restituire `False`.

**Intervento minimo.** Scrivere il dump su file temporaneo e usare
`MediaFileUpload` invece di `MediaIoBaseUpload`. **Costo: 2 ore.** Non è urgente:
va scritto adesso perché quando servirà non ci sarà il tempo di scoprirlo.

---

### O15 — BASSA — La cache delle credenziali Google è condivisa fra thread senza sincronizzazione

`backend/services/google_oauth_service.py:23,33-47`

**[VERIFICATO — stato mutabile condiviso]** `_credenziali_cache` è un dizionario
di modulo, e gli oggetti `Credentials` che contiene vengono **mutati** da
`credenziali.refresh(Request())` (`:45`). Vi accedono fino a 40 thread di
richiesta e il thread dello scheduler, sullo stesso oggetto.

`google.auth.credentials.Credentials` non è documentata come thread-safe. Due
refresh simultanei sullo stesso oggetto — scenario concreto: il job promemoria
delle 03:00 mentre arriva una prenotazione — possono produrre uno stato
incoerente.

**[SOSPETTO — sulla manifestazione:** l'effetto sarebbe un fallimento di
autenticazione sporadico, che verrebbe inghiottito dai wrapper di §O9 e §O11 e
comparirebbe nei log come una email persa senza spiegazione. Confermabile solo
con una prova di carico che forzi refresh concorrenti. **]**

**Intervento minimo.** Un `threading.Lock` di modulo attorno alle righe 44-45.
**Costo: 20 minuti.**

---

### O16 — BASSA — Paginazione ordinata su una colonna non univoca

`backend/routers/admin/bookings.py:51` — `backend/routers/admin/packages.py:25` —
`backend/routers/admin/reviews.py:36` — a confronto con `backend/routers/slots.py:29-41`

**[VERIFICATO]** `order_by(Booking.created_at.desc())` combinato con
`offset`/`limit` (`bookings.py:51-54`), senza alcun criterio di spareggio.
`created_at` ha precisione al secondo su entrambi i motori: sei prenotazioni
create nello stesso secondo non hanno un ordine definito, e fra due richieste
consecutive una riga può comparire su due pagine o su nessuna.

È esattamente la classe di difetto già subita in produzione e documentata a
`slots.py:29-41` — *"8 salti all'indietro su 83 slot"*, con la spiegazione che
SQLite maschera perché sceglie un piano che restituisce le righe già ordinate.
Là la cura è stata aggiungere l'`ORDER BY`; qui l'`ORDER BY` c'è ma non è
deterministico, e il mascheramento locale è lo stesso.

**Intervento minimo.** `.order_by(Booking.created_at.desc(), Booking.id.desc())`
sui tre endpoint. **Costo: 15 minuti.**

---

## 4. Fuori mandato

- `POST /users/` restituisce l'id di un utente esistente, rendendo la coppia
  `user_id`+`email` richiesta da `POST /bookings/` ottenibile da chiunque.
- `note_admin` compare nel `response_model` di `POST /bookings/`, endpoint
  pubblico (`schemas/booking.py:56`).
- Il testo scritto dal pubblico entra negli embed Discord senza escape
  (`discord_service.py:72-78`), mentre per le email viene sanificato.
- `secrets.compare_digest` con un token non ASCII solleva `TypeError`
  (`booking.py:354`).
- Nessuno schema Pydantic dichiara `max_length`, mentre le colonne sono
  dimensionate.

---

## 5. Non verificato

- **La produzione, di nuovo.** Nessun accesso a Railway né al MySQL. Ne dipendono
  §O3 (lock InnoDB), §O4 (health check configurato), §O6 (fuso del server),
  §O7 (collation), §O13 (numero di repliche): tutti marcati [SOSPETTO], ciascuno
  con la propria procedura di conferma, tutte eseguibili in pochi minuti da chi
  ha le credenziali.
- **Il comportamento sotto concorrenza reale.** SQLite con `StaticPool` serializza
  tutto: né §O3 né §O13 né §O15 sono riproducibili in locale. Servirebbe una prova
  contro MySQL con connessioni multiple.
- **Una prova di carico.** I numeri di §O4 (40 thread, 15 connessioni) sono
  misurati sulla configurazione, non osservati sotto traffico: non so a quante
  richieste al secondo il pool si satura davvero, perché dipende dalla latenza di
  Google che non ho misurato.
- **Il ripristino di un backup.** Non ho provato a ricostruire un database da un
  dump prodotto da `crea_dump_sql`: non posso affermare che i backup esistenti
  siano ripristinabili, solo che nessuno lo ha verificato (§O8).
- **I log reali di Railway.** Tutte le affermazioni di §1 e §O10 riguardano cosa
  il codice **scrive**, non cosa si vede nella console di Railway: ritenzione,
  filtri e formato del piano in uso non li ho potuti guardare.
- **Il comportamento di APScheduler al riavvio del processo.** I default li ho
  letti nella libreria installata (`misfire_grace_time=1`); non ho simulato un
  riavvio a cavallo di un trigger cron per osservare lo skip.
- **`alembic/versions/`.** Non ho letto le singole migrazioni: §O12 riguarda il
  meccanismo, non il contenuto. Una migrazione lenta o bloccante andrebbe cercata
  lì.
- **`scripts/`.** Fuori dal processo servito, non esaminato.
- **Gli altri report in `audit/`.** Non letti, come da vincolo.
