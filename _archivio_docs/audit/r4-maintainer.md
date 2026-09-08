# Revisione 4 — Nuovo maintainer, entrato oggi

**Mandato:** comprensibilità e trappole, non eleganza. Parti che non si capiscono
senza contesto esterno, nomi che mentono, effetti collaterali non evidenti,
configurazione implicita, punti in cui una modifica ragionevole rompe qualcosa in
silenzio. Sui test: quali percorsi critici non sono coperti, e quali test
passerebbero anche con la logica rotta.
**Perimetro:** tutto il repository, dal punto di vista di chi lo apre oggi.
**Metodo:** lettura, più **un esperimento di mutazione**: ho rotto otto regole di
business una alla volta e rieseguito la suite, per misurare cosa i test
difendono davvero invece di dedurlo dalla copertura. Nessun altro documento di
`audit/` è stato letto.
**Domanda guida:** dov'è la trappola per chi non conosce il codice?

> **Nota di metodo.** L'esperimento ha modificato temporaneamente quattro file
> sorgente, ripristinati subito dopo ciascuna prova. Ho verificato al termine che
> l'albero di lavoro sia pulito (`git status` mostra solo `audit/` non tracciato)
> e che la suite torni a **146 passed**.

---

## 1. Risposta alla domanda guida

Le trappole in ordine di quanto è facile caderci senza accorgersene.

| # | Trappola | Cosa succede a chi non lo sa |
|---|---|---|
| 1 | Le notifiche e l'evento Calendar non sono coperti da nessun test (§M2) | Le cancelli in un refactor e **la suite resta verde**: 146 passed |
| 2 | `date.today()` in `availability_service.py:65` (§M1) | Una regola creata dal pannello fra mezzanotte e le 2 del 1° del mese genera **zero slot**, senza errori |
| 3 | Il limite anti-abuso non è testato (§M3) | Lo porti da 2 a 999 e **la suite resta verde** |
| 4 | L'app funziona solo con working directory alla radice (§M4) | `RuntimeError: Directory 'frontend' does not exist` **all'import**, e il messaggio non dice perché |
| 5 | L'import in fondo a `admin/__init__.py` (§M5) | Un "organize imports" dell'IDE e l'app non parte più |
| 6 | Tre liste di tipi pacchetto da allineare a mano (§M6) | Ne aggiorni due su tre e ottieni un **500 da `KeyError`** invece di un 422 |
| 7 | `libera_slot_prenotazione` fa una chiamata di rete (§M7) | La leggi come un `UPDATE` locale; è dentro una richiesta HTTP |
| 8 | 36 date fissate al 2030 nei test (§M9) | Nel 2030 metà suite diventa rossa per motivi che non c'entrano col codice |

---

## 2. Quello che ho trovato solido, e che va detto prima

Una revisione che non lo dicesse sarebbe imprecisa, e mi porterebbe a proporre
cose che qui esistono già.

**I commenti spiegano il *perché*, non il *cosa*.** Non è la norma. Il claim
atomico sullo slot (`booking.py:167-200`), il motivo del `samesite="lax"`
(`discord_auth.py:68-71`), la scelta dell'API Gmail al posto di SMTP
(`email_service.py:3-6`), il `misfire` delle 03:30 collocato mezz'ora prima del
backup (`scheduler.py:384-392`): ogni volta la domanda a cui rispondono è quella
giusta.

**Diversi commenti registrano l'incidente che li ha generati.** `slots.py:29-41`
racconta l'`ORDER BY` mancante visto in produzione, con i numeri
("8 salti all'indietro su 83 slot") e il motivo per cui i test non l'avevano
preso. `pytest.ini:2-8` spiega perché serve `pythonpath = .` e come il problema
si era mascherato in locale. Per un nuovo arrivato valgono più di qualunque
documentazione: dicono dove il progetto ha già sbagliato.

**La suite regge alla mutazione, quasi ovunque.** Sei rotture su otto sono state
intercettate (§4). Non è scontato per una suite di 146 test.

**C'è già la tecnica che risolve il problema SQLite/MySQL.**
`test_query_degli_slot_ordina_esplicitamente` (`test_slots.py:162-191`) non
guarda il risultato — che su SQLite sarebbe ordinato comunque — ma **l'SQL
realmente emesso**, intercettandolo con un listener. È l'unico modo di difendere
su SQLite un comportamento che si rompe solo su MySQL, ed è applicato una volta
sola. §4.3 dice dove altro serve.

**La documentazione storica è etichettata.** `ANALYSIS.md:3`, `ANALISI_2026-08-31.md:3`
e `ROADMAP.md:3` aprono con un banner "DOCUMENTO STORICO"; `STATO_PROGETTO.md:3-5`
dichiara le proprie regole di manutenzione e chi ha la precedenza in caso di
conflitto. È più di quanto faccia la maggior parte dei progetti. Il problema
residuo è diverso, ed è §M12.

---

## 3. Trappole

### M1 — ALTA — L'unica riga del backend che usa l'ora locale del processo sta nel generatore di slot

`backend/services/availability_service.py:65,93` — `backend/services/timezone_service.py:45-52`

**[VERIFICATO — dimostrato]** Il progetto ha una convenzione stretta e
documentata: nel database gli orari sono UTC naive, e per qualunque confronto si
usa `ora_utc_naive()`, la cui docstring dice testualmente *"Da usare al posto di
`datetime.now()`"* (`timezone_service.py:45-52`). La convenzione è rispettata
ovunque tranne in un punto:

```python
# availability_service.py:65
oggi = date.today()          # data LOCALE del processo
...
# availability_service.py:93
inizio_rome = cursore.replace(tzinfo=ROME_TZ)   # ora ITALIANA
```

La stessa funzione prende **i giorni dal fuso del processo e gli orari da Roma**.
In produzione il processo gira in UTC, quindi i due fusi sono diversi.

Dimostrazione, con i valori reali:

```
il coach guarda l'orologio e vede:      2026-10-01 00:30 (Roma)
il processo in produzione (UTC) vede:   2026-09-30 22:30
date.today() in produzione restituisce: 2026-09-30      <- mese PRECEDENTE

percepito dal coach   oggi=2026-10-01  ultimo_giorno_mese=2026-10-31
visto dal processo    oggi=2026-09-30  ultimo_giorno_mese=2026-09-30
```

`genera_slot_da_regola` genera "fino alla fine del mese corrente"
(`availability_service.py:68,81`). In quella finestra il mese corrente per il
processo è già finito: il ciclo esce al primo giro e la funzione restituisce
`0`. Il coach crea una regola dal pannello, legge `slot_creati: 0`, e non c'è
nulla che spieghi perché.

**Perché è una trappola e non solo un difetto.** Chi legge
`availability_service.py` vede in cima `from ...timezone_service import ROME_TZ,
ora_utc_naive, ...` e conclude ragionevolmente che il modulo è a posto sui fusi.
La riga 66 usa `ora_utc_naive()` correttamente. La 65 no, ed è l'unica del
backend.

**Intervento minimo.** `oggi = utc_to_rome(ora_utc_naive()).date()`. **Costo: 15
minuti**, più un test sul confine di mese che oggi non esiste.

---

### M2 — ALTA — Le notifiche e l'evento Calendar possono sparire e la suite resta verde

`tests/conftest.py:85-88` — `backend/routers/booking.py:213,250-276`

**[VERIFICATO — mutazione eseguita]** Ho sostituito con no-op le quattro chiamate
finali di `create_booking` — creazione dell'evento su Google Calendar, email di
conferma al cliente, email al coach, notifica Discord — e rieseguito la suite:

```
booking: rimuove le 3 notifiche e l'evento calendario  ->  146 passed
```

Nessun test cambia colore. Il motivo è in `conftest.py:85-88`: le funzioni sono
sostituite con `lambda **kwargs: None`, e **nessuno verifica poi che siano state
chiamate**. Sono finte, non osservate.

Il risultato è che le quattro cose che rendono una prenotazione *utile* — il
cliente sa di aver prenotato, il coach lo sa, l'appuntamento esiste su un
calendario — non sono difese da niente. Un refactor che ne perde una produce una
suite verde e un cliente che si presenta a una sessione di cui il coach non sa
nulla.

**Intervento minimo.** Sostituire le lambda con registratori e verificare:

```python
chiamate = {"conferma": [], "admin": [], "discord": [], "calendario": []}
monkeypatch.setattr(booking_router, "invia_conferma_cliente",
                    lambda **k: chiamate["conferma"].append(k))
...
```

esposti come fixture, e un assert nel test principale della prenotazione.
**Costo: 1 ora**, ed è il singolo intervento che alza di più il valore della
suite.

---

### M3 — ALTA — Il limite anti-abuso non è testato: portarlo a 999 non rompe nulla

`backend/routers/booking.py:31,156-165` — `tests/`

**[VERIFICATO — mutazione eseguita]**

```
booking: alza il limite prenotazioni attive da 2 a 999  ->  146 passed
```

`MAX_PRENOTAZIONI_ATTIVE` non compare in nessun file di `tests/`, e la copertura
conferma che `booking.py:162` — la riga che solleva l'errore — **non è mai stata
eseguita da un test**.

È l'unica difesa contro una persona che occupa da sola tutta l'agenda, in
un'applicazione dove non c'è pagamento anticipato: il commento a
`booking.py:153-155` lo dice esplicitamente. Ed è anche codice fragile in modo
non ovvio — dipende da un `join` sulla relationship e da tre filtri, incluso
`Slot.start_time >= ora_utc_naive()`: chi cambiasse quella query per errore non
avrebbe alcun segnale.

**Intervento minimo.** Un test: due prenotazioni confermate, la terza deve dare
400. **Costo: 20 minuti.**

---

### M4 — MEDIA — L'app funziona solo se la working directory è la radice del repo, e fallisce all'import

`backend/main.py:89,162,190,194,198,202`

**[VERIFICATO — riprodotto]** Sei percorsi relativi, di cui uno eseguito a livello
di modulo:

```
StaticFiles(directory='frontend') eseguito da backend/  ->  RuntimeError
messaggio: Directory 'frontend' does not exist
```

`app.mount(...)` è a `main.py:162`, quindi non è un 404 a runtime: **è l'import di
`backend.main` che fallisce**. Lo stesso vale per `Config("alembic.ini")`
(`:89`) e per le quattro `FileResponse` delle pagine.

Oggi funziona perché `nixpacks.toml:5` avvia il processo dalla radice e
`pytest.ini:2` aggiunge la radice a `sys.path`. Nessuno dei due dichiara che si
tratta di un **requisito**. Chi aggiungesse un `Dockerfile` con un `WORKDIR`
diverso, o lanciasse `uvicorn` da un'altra cartella, riceve un errore che nomina
una directory e non la causa.

**Intervento minimo.**

```python
RADICE = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=RADICE / "frontend"), name="static")
```

**Costo: 30 minuti** per i sei punti.

---

### M5 — MEDIA — L'import in fondo a `admin/__init__.py` è a un "organize imports" dalla rottura

`backend/routers/admin/__init__.py:58-61`

**[VERIFICATO]** L'import dei sei sotto-router è deliberatamente in fondo al file,
con un commento che spiega che spostarlo in cima produce un import circolare. La
spiegazione c'è ed è corretta.

Quello che manca è il **marcatore che lo protegge**. Non c'è
`# isort: skip_file`, non c'è `# noqa`, e nel repository non esiste alcuna
configurazione di formattazione o linting: ho verificato l'assenza di
`pyproject.toml`, `setup.cfg`, `.isort.cfg`, `.flake8` e `.pre-commit-config.yaml`.
Il comportamento non è quindi fissato da nulla: dipende solo dal fatto che
nessuno, finora, abbia premuto "organize imports" nel proprio editor.

Un commento in italiano difende dal lettore umano, non da uno strumento.

**Intervento minimo.** `# isort: skip_file` in cima al file — **5 minuti** — e in
prospettiva la ristrutturazione che elimina il ciclo.

---

### M6 — MEDIA — Tre liste di tipi pacchetto da allineare a mano, con due modi opposti di rompersi

`backend/services/package_service.py:7` — `backend/schemas/package.py:7` —
`backend/schemas/pacchetto_richiesta.py:10` — `backend/routers/pacchetti_richieste.py:32` —
`backend/routers/admin/packages.py:43`

**[VERIFICATO — confrontate a runtime]**

```
schemas/package.py            : ['intro', 'team', 'tour']
schemas/pacchetto_richiesta.py: ['intro', 'team', 'tour']
services/package_service.py   : ['intro', 'team', 'tour']
allineati oggi? True     nessun test confronta le tre liste
```

Chi aggiunge un pacchetto deve toccare tre punti, e i due modi di sbagliare non
si assomigliano:

- aggiorna solo il catalogo → il nuovo tipo viene respinto con **422**, errore
  visibile e comprensibile;
- aggiorna solo i due `Literal` → `CATALOGO_PACCHETTI[richiesta.tipo]`
  (`pacchetti_richieste.py:32`) e `CATALOGO_PACCHETTI[pacchetto.tipo]`
  (`admin/packages.py:43`) sollevano `KeyError` → **500**, senza indicazione di
  cosa manchi.

Il progetto conosce già questo rischio: il commento a `test_richieste.py:63-66` lo
nomina per esteso (*"che userebbe CATALOGO_PACCHETTI[tipo] e solleverebbe un
KeyError"*). Ma il test copre solo la direzione che dà 422.

**Intervento minimo.** `TipoPacchetto = Literal[tuple(CATALOGO_PACCHETTI)]`,
importato dal catalogo nei due schemi. Restano tre file, ma una sola verità.
**Costo: 20 minuti.**

---

### M7 — MEDIA — `libera_slot_prenotazione` fa quattro cose, e una è una chiamata di rete

`backend/services/booking_service.py:13-31` — chiamata da
`backend/routers/booking.py:304`, `backend/routers/admin/bookings.py:117`,
`backend/routers/admin/clients.py:118`

**[VERIFICATO]** La funzione (a) chiama Google Calendar per eliminare l'evento,
(b) azzera `calendar_event_id`, (c) libera fino a due slot, (d) **non fa commit**.

La docstring le elenca tutte e quattro, e questo la salva dall'essere un nome che
mente. La trappola non è nella definizione, è nei **tre punti di chiamata**: là
la riga si legge come un aggiornamento locale al database, ed è invece una
richiesta HTTP verso un servizio esterno eseguita dentro una richiesta web. Il
caso peggiore è `clients.py:118`, dove la chiamata sta **dentro un ciclo** sulle
prenotazioni del cliente: una cancellazione GDPR di un cliente con dieci
prenotazioni confermate fa dieci chiamate di rete in sequenza, in un endpoint
sincrono.

Da notare: `booking_service.py:21-22`, cioè proprio il ramo che parla con Google,
è l'unica parte non coperta di quel modulo — **nessun test la esegue**.

**Intervento minimo.** Rinominare in
`annulla_effetti_collaterali_prenotazione`, oppure separare la parte database
dalla parte calendario e lasciare al chiamante la seconda. **Costo: 1 ora.**

---

### M8 — MEDIA — `AvailabilityRule.attiva` filtra un job e non è scrivibile da nessun endpoint

`backend/models/availability_rule.py:28-32` — `backend/scheduler.py:230` —
`backend/routers/admin/availability.py:110-171`

**[VERIFICATO]** Il campo esiste, il job notturno ci filtra sopra
(`scheduler.py:230`, `AvailabilityRule.attiva == True`), e nessuno dei tre
endpoint sulle regole lo modifica. Il model lo dichiara onestamente
(`:30-31`: *"Nessun endpoint espone oggi la modifica di questo campo"*), ma quel
commento lo legge chi apre il model — non chi cerca la funzione dal pannello.

Un nuovo maintainer a cui viene chiesto *"sospendi la disponibilità del martedì
per un mese"* trova il campo, trova il filtro, e non trova il modo di scriverlo.
Le uniche alternative sono eliminare la regola — cosa che il pannello offre, e
che **non tocca gli slot già generati** (`availability.py:161-164`) — o una
`UPDATE` a mano sul database di produzione.

Nello stesso file la simmetria manca due volte: `crea_regola_disponibilita`
(`:120-153`) crea la regola **e genera subito gli slot**, mentre
`elimina_regola_disponibilita` elimina solo la regola;
`crea_blocco_eccezionale` (`:184-211`) blocca subito gli slot, mentre
`elimina_blocco_eccezionale` non li sblocca. Ogni singolo endpoint lo documenta;
nessun punto documenta l'insieme, che è quello che un nuovo arrivato deve
tenere a mente tutto insieme.

**Intervento minimo.** `PATCH /admin/disponibilita/regole/{id}` con il solo campo
`attiva`, e il selettore corrispondente nel pannello. **Costo: 1 ora.**

---

### M9 — MEDIA — La suite ha una data di scadenza: 36 letterali fissati al 2030

`tests/test_booking.py:42-49` e altri — 36 occorrenze di `2030` in `tests/`

**[VERIFICATO]** `INIZIO = rome_naive_utc(2030, 1, 7, 15)`, con il commento
*"ben nel futuro — non importa la data esatta, solo che sia sempre dopo
'adesso'"*. L'intenzione è giusta; il codice non implementa "sempre".

Dal 7 gennaio 2030 quello slot è nel passato, `create_booking` lo rifiuta con 400
(`booking.py:65-66`) e una parte consistente della suite diventa rossa in blocco,
per un motivo che non ha niente a che vedere con il codice. Chi si trovasse
davanti quel giorno vedrebbe decine di test falliti e nessun cambiamento recente
a cui attribuirli.

C'è anche un accoppiamento implicito da preservare: quella data deve essere un
**lunedì alle 15:00 ora italiana**, perché i test sulle sessioni da 2 ore
dipendono da `ORE_INIZIO_VALIDE_2H` (`booking.py:44`). Il commento lo dice, il
valore no.

**Intervento minimo.** Calcolare `INIZIO` da `ora_utc_naive()` — il prossimo
lunedì alle 15:00 di Roma — invece che da un letterale. Rende esplicito anche
l'accoppiamento. **Costo: 1 ora.**

---

### M10 — BASSA — `limiter.enabled = False` è una mutazione globale, e rende il rate limiting non testabile

`tests/conftest.py:50-55` — `backend/rate_limit.py:12` — `backend/routers/users.py:133-137`

**[VERIFICATO]** La riga è a livello di modulo, non dentro una fixture: disattiva
il rate limiting per l'intera sessione di test e non è riattivabile per un
singolo caso. La motivazione (evitare fallimenti intermittenti) è corretta; la
collocazione fa sì che **nessun test possa coprire il rate limiting**, che è
l'unica protezione su sei endpoint pubblici.

Il rischio concreto è specifico di slowapi: il decoratore richiede che
l'endpoint dichiari un parametro `request: Request`, anche se non lo usa — il
commento a `users.py:135` lo spiega proprio perché è controintuitivo. Chi
"pulisse" quel parametro apparentemente inutile romperebbe il limite, e nessun
test glielo direbbe.

**Intervento minimo.** Una fixture che spegne e riaccende, più un test che
verifica che la sesta richiesta in un minuto riceva 429. **Costo: 1 ora.**

---

### M11 — BASSA — Il margine di 6 ore in `slot_si_sovrappone` è accoppiato a una regola imposta in un altro file

`backend/services/availability_service.py:28-36` — `backend/schemas/booking.py:34`

**[VERIFICATO]** La finestra di ricerca dei conflitti è limitata da
`margine = timedelta(hours=6)`, con il commento *"nessuna sessione dura più di 6
ore, quindi uno slot che inizia prima di questo margine non può sovrapporsi"*.

L'assunzione è vera oggi — la durata massima è 2 ore, imposta da
`Literal[1, 2]` in `schemas/booking.py:34` — ma è imposta **in un altro file**, e
il legame fra i due non è dichiarato da nessuna parte. Se un domani si ammettono
sessioni più lunghe (§A del listino: è una modifica che tocca già sei punti), il
controllo di sovrapposizione smette silenziosamente di trovare i conflitti più
lontani: nessun errore, solo doppie prenotazioni reali sull'agenda del coach.

**Intervento minimo.** Derivare il margine dalla durata massima ammessa, invece
di riaffermarla. **Costo: 20 minuti.**

---

### M12 — BASSA — La documentazione è ottima e non dice da dove si entra

radice del repository: 8 file `.md`, **486 KB** — nessun `CLAUDE.md`, nessun
`CONTRIBUTING.md`, nessuna cartella `docs/`

**[VERIFICATO]** Il merito va riconosciuto per primo: ogni documento storico
porta un banner in testa (`ANALYSIS.md:3`, `ANALISI_2026-08-31.md:3`,
`ROADMAP.md:3`), e `STATO_PROGETTO.md:3-5` dichiara le proprie regole di
aggiornamento, quali sezioni sono "presente" e quali "diario", e chi vince in
caso di conflitto. Il problema non è che i documenti mentano.

Il problema è l'ordine di lettura. Un nuovo maintainer apre `README.md`, perché
è la convenzione. Trova *"VGC Coaching App — Guida di Studio"*, e poco sotto
*"Perché ti conviene studiare questo progetto"*: 47 KB di materiale didattico
rivolto a chi sta imparando a programmare, non a chi deve modificare il codice.
Lo stesso vale per `CODICE_SPIEGATO.md` (30 KB). Il documento autorevole è
`STATO_PROGETTO.md`, sezioni 1-9 — ma **quel fatto è scritto dentro
`STATO_PROGETTO.md`**, cioè lo legge solo chi lo ha già trovato.

Mancano inoltre, in qualunque documento, tre cose che servono nella prima ora:
il requisito sulla working directory (§M4), il comando per far girare la suite,
e l'avvertenza che i test girano su SQLite mentre la produzione è MySQL.

**Intervento minimo.** Quindici righe in cima a `README.md`: cosa leggere e in
che ordine, quale file è autorevole, come si lancia la suite, da dove si lancia
il server. **Costo: 30 minuti.**

---

## 4. I test

### 4.1 L'esperimento di mutazione

Otto regole rotte una alla volta, suite rieseguita ogni volta.
Baseline: `146 passed`.

| Mutazione | Esito |
|---|---|
| Rimuove le 3 notifiche e l'evento calendario | **146 passed — non intercettata** |
| `MAX_PRENOTAZIONI_ATTIVE` da 2 a 999 | **146 passed — non intercettata** |
| Il claim atomico non controlla più `is_available` | 1 failed — intercettata |
| Toglie l'`ORDER BY` dalla lista pubblica degli slot | 1 failed — intercettata |
| `compare_digest` sul token recensione sostituito da "sempre vero" | 1 failed — intercettata |
| L'anonimizzazione non cancella più `discord_id` | 1 failed — intercettata |
| Sparisce il clamp di `per_pagina` | 2 failed — intercettata |
| `utc_to_rome` non converte più nulla | 11 failed — intercettata |

Sei su otto. Le due che sopravvivono sono §M2 e §M3, e non sono casuali: sono
esattamente i due punti dove il test avrebbe dovuto verificare un **effetto**
(una notifica prodotta, un limite applicato) invece di un valore restituito.

### 4.2 Percorsi critici senza copertura

Dalla copertura, filtrando ciò che conta davvero:

| Non coperto | Cosa significa |
|---|---|
| `admin/dashboard.py:29-65` | Il corpo intero di `dashboard()`: la schermata iniziale del coach, mai eseguita da un test |
| `scheduler.py:333-341` | `controlla_e_esegui_backup_database`, cioè **la funzione che genera l'allarme quando il backup fallisce** |
| `scheduler.py:212-216,228-236,245-249` | I wrapper di sync calendario, generazione slot e pulizia slot |
| `booking_service.py:21-22` | Il ramo che elimina l'evento su Google Calendar (§M7) |
| `main.py:86-103` | `run_migrations` |
| `admin/availability.py:38-60` | Il corpo di `get_slots_admin` |
| `calendar_service` 28%, `discord_service` 41%, `email_service` 54% | Le tre integrazioni esterne |

La CI (`.github/workflows/tests.yml:47`) esegue `pytest` con `--cov` attivo da
`pytest.ini:22`, ma **senza soglia minima**: la copertura viene misurata e
stampata, e nessun valore la fa fallire. Può scendere senza che nessuno se ne
accorga.

### 4.3 Cosa i test su SQLite non possono provare — e la tecnica che il progetto ha già

Questa è la parte che un nuovo maintainer rischia di fraintendere di più: **una
suite verde qui non dice quasi nulla su MySQL**, e il progetto lo sa in un punto
solo.

`test_query_degli_slot_ordina_esplicitamente` (`test_slots.py:162-191`) intercetta
con un listener l'SQL realmente inviato e verifica che contenga
`ORDER BY ... start_time`, invece di guardare l'ordine delle righe restituite. La
docstring spiega il perché: *"Il test sopra confronta il risultato, e su SQLite
passerebbe comunque perché quel database restituisce già le righe ordinate. Qui
si guarda l'SQL realmente inviato, che è lo stesso su qualunque database."*

È la tecnica giusta, ed è applicata una volta. Le altre differenze restano
scoperte:

- **Foreign key.** SQLite non le applica se non si esegue
  `PRAGMA foreign_keys=ON`, e in `conftest.py` non lo fa nessuno (verificato: la
  pragma vale `0`, e un `INSERT` di una prenotazione con `user_id` inesistente
  viene accettato). L'ordine di eliminazione in `elimina_cliente`
  (`clients.py:114-128`), che è la cancellazione GDPR, è un vincolo reale in
  produzione e una formalità nei test.
- **Lunghezza delle colonne.** SQLite ignora `String(500)`; MySQL in modalità
  strict no. Un valore troppo lungo passa nei test e fallisce in produzione.
- **Collation.** MySQL confronta le stringhe senza distinguere maiuscole,
  SQLite sì: `filter(User.email == ...)` (`users.py:111`,
  `discord_auth.py:150`) ha semantica diversa nei due ambienti.
- **Concorrenza.** `StaticPool` (`conftest.py:32-36`) serializza tutto su una
  connessione: la race che il claim atomico difende non è riproducibile, e
  infatti nessun test di concorrenza esiste nella suite.
- **`crea_dump_sql`.** Usa `SHOW TABLES` e `connessione.escape()`, che su SQLite
  non esistono: `test_backup_service.py:31` la sostituisce con
  `lambda engine: "-- dump finto"`. La funzione che produce il backup **non è
  eseguita da nessun test**.

**Intervento minimo, in ordine di resa.** (a) `PRAGMA foreign_keys=ON` in
`conftest.py` — quattro righe, allinea una classe intera di errori; (b) estendere
la tecnica del listener SQL agli altri punti dove la differenza è nel testo della
query (il tie-break sull'ordinamento delle liste paginate); (c) un MySQL come
service container in CI, che chiude tutto il resto in un colpo solo.

---

## 5. Fuori mandato

- `POST /users/` restituisce l'id di un utente esistente a chiunque conosca
  l'email (`users.py:104-137`).
- `MAX_PRENOTAZIONI_ATTIVE` è aggirabile creando prenotazioni a nome di email
  altrui, e la vittima resta bloccata.
- `reminder_sent` viene impostato a `True` anche quando l'email non è partita
  (`scheduler.py:156`).
- L'evento Google Calendar è creato mentre è aperta la transazione che tiene il
  lock sullo slot (`booking.py:178-213`).
- Il backup settimanale non ha modo di accorgersi di non essere partito
  (`scheduler.py:428-435`).

---

## 6. Non verificato

- **La produzione.** Nessun accesso a Railway né al MySQL: §M1 (l'effetto reale
  del fuso del processo), §M4 (la working directory effettiva del container) e
  tutto §4.3 sono argomentati sul codice e sui default, non osservati.
- **Il comportamento reale su MySQL.** L'intera §4.3 descrive differenze
  documentate fra i due motori e verificate sul lato SQLite (dove ho eseguito le
  prove); il lato MySQL non l'ho potuto eseguire.
- **La mutazione è un campione, non una misura.** Otto rotture scelte da me sulle
  regole che mi sembravano più importanti. Non è `mutmut` su tutto il codice: dice
  che quei due buchi esistono, non che siano gli unici.
- **Il frontend.** `admin.js` (1169 righe) e `app.js` (668) non hanno alcun test,
  e non li ho valutati come codice: fuori dal perimetro delle sessioni precedenti
  e non richiesto qui.
- **Il contenuto dei documenti.** Ho verificato che i file storici siano
  etichettati come tali e ho letto le intestazioni; **non ho verificato che
  `STATO_PROGETTO.md` §1-9 descriva accuratamente il codice di oggi**. È il
  documento dichiarato autorevole, e una sua deriva sarebbe la trappola peggiore
  di tutte: andrebbe verificato a parte.
- **`alembic/versions/`.** Le singole migrazioni non le ho lette.
- **`scripts/`.** Quattro file fuori dal processo servito, non esaminati.
- **Gli altri report in `audit/`.** Non letti, come da vincolo.
