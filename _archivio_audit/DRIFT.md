# DRIFT

Confronto fra i documenti archiviati in `_archivio_docs/` e il comportamento verificato in
`AUDIT.md` (audit ricavato dal solo codice eseguito). Ogni voce cita il documento testualmente,
descrive cosa fa il codice con `file:riga`, classifica la divergenza e dice quale delle due parti
sembra l'intenzione corretta.

**Perimetro.** Sono trattati come documenti che *descrivono il presente*: `README.md`,
`CODICE_SPIEGATO.md` e le sezioni **1–9** di `STATO_PROGETTO.md`. `ANALYSIS.md`, `ROADMAP.md`,
`ANALISI_2026-08-31.md`, `REVISIONE_2026-09-01.md`, `RAILWAY_RIALLINEAMENTO_2026-09-02.md` e le
sezioni **10 in poi** di `STATO_PROGETTO.md` portano un'intestazione esplicita che li dichiara
storici e non aggiornabili: la loro distanza dal codice è voluta e non è contata qui (vedi la nota
finale). Non è stato modificato alcun file di codice.

I riferimenti ai markdown sono per **titolo di sezione**, non per numero di riga, secondo la regola
che `STATO_PROGETTO.md` §7.11 si è data dopo essersi rotta da sola.

---

## Divergenze sul comportamento centrale

### 1. `AvailabilityRule.attiva` — interruttore documentato come funzionante, ma nessun endpoint lo scrive

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §2, tabella `availability_rules`:

> attiva | Boolean | NOT NULL, default True — **ora usata davvero**: `genera_slot_giornaliero` (job notturno) filtra solo le regole attive

e §7, punto 5:

> **`AvailabilityRule.attiva` ora è davvero usato**: prima esisteva come colonna inerte, ora `genera_slot_giornaliero` (job notturno) filtra solo le regole attive.

**Cosa fa il codice** — la colonna è **letta** e mai **scritta**. La lettura c'è davvero
(`backend/scheduler.py:230`, `filter(AvailabilityRule.attiva == True)`), ma non esiste alcun modo di
portarla a `False` passando dall'applicazione: lo schema di creazione non contiene il campo
(`backend/schemas/availability.py:8-12`) e il router non lo valorizza
(`backend/routers/admin/availability.py:134-139`), né esiste un endpoint di modifica della regola —
l'unico altro verbo è `DELETE /admin/disponibilita/regole/{id}`
(`backend/routers/admin/availability.py:155`). Il commento nel model lo dice per esteso,
`backend/models/availability_rule.py:29-31`: *"Nessun endpoint espone oggi la modifica di questo
campo: una regola nasce attiva e per sospenderla serve intervenire sul database."*

**Tipo di divergenza** — funzionalità implementata a metà e documentata come completa. Il documento
è letteralmente vero ("il job filtra sulle regole attive") ma induce a credere che dall'app si possa
sospendere una regola, cosa che non si può fare.

**Quale sembra l'intenzione corretta** — il **codice**, e per una ragione scritta nel codice stesso:
il commento del model dichiara la limitazione come nota, non come dimenticanza. È il documento a
dover dire che sospendere una regola oggi richiede un `UPDATE` a mano sul database. La lettura
opposta — aggiungere `attiva` a `AvailabilityRuleCreate` e un `PATCH` sulla regola — è lavoro di
prodotto, non un riallineamento, e va deciso a parte.

---

### 2. La richiesta di recensione non è un job notturno: gira a intervallo

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §4 *Logica di business*:

> **Recensioni**: dopo ogni sessione conclusa, un job notturno manda un'email con un link contenente un token monouso (`review_token`)

**Cosa fa il codice** — il job è registrato con trigger `interval`, non `cron`:
`backend/scheduler.py:357-362` (`"interval", minutes=REVIEW_CHECK_INTERVAL_MINUTES`), con default
**60 minuti** (`backend/scheduler.py:38`). L'email parte quindi entro un'ora dalla fine della
sessione, non la notte successiva. La verifica della fine sessione è puntuale
(`backend/scheduler.py:190-192`) e `review_email_sent` viene marcato subito dopo l'invio
(`backend/scheduler.py:196-198`).

**Tipo di divergenza** — funzionalità implementata diversamente da come è documentata.

**Quale sembra l'intenzione corretta** — il **codice**. Una richiesta di recensione che arriva entro
un'ora dalla sessione ha più probabilità di risposta di una che arriva la notte dopo, e
`README.md` descrive già `REVIEW_CHECK_INTERVAL_MINUTES` come intervallo ("Ogni quanti minuti lo
scheduler controlla se ci sono richieste di recensione da inviare"). È `STATO_PROGETTO.md` §4 a
essere rimasto indietro rispetto a una scelta già presa e già documentata altrove.

---

### 3. Il backup è settimanale, ma §6 e §7.9 lo descrivono ancora come notturno

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §6 *Servizi esterni*:

> **Google Drive (nuovo)** — backup automatico notturno del database (dump SQL scritto a mano via PyMySQL, non `mysqldump`)

e §7, punto 9:

> `BackgroundScheduler()` è costruito senza `timezone=`, quindi gli orari dei job notturni (03:00, 03:01, 03:02, 04:00) sono ore locali del processo.

**Cosa fa il codice** — il backup gira **una volta a settimana**, la domenica:
`backend/scheduler.py:428-435` (`"cron", day_of_week="sun", hour=4, minute=0`), con il motivo scritto
nel commento immediatamente sopra (`backend/scheduler.py:421-427`: *"il volume di dati è basso e
cambia poco... La finestra di perdita massima passa da 24 ore a 7 giorni — accettata
consapevolmente, non subita"*). L'elenco degli orari di §7.9 è inoltre incompleto: manca il job
delle **03:30 della domenica** (`backend/scheduler.py:393-400`), che non esisteva quando quella riga
fu scritta.

**Tipo di divergenza** — comportamento cambiato nel codice ma ancora documentato all'antica, con
**contraddizione interna allo stesso file**: `STATO_PROGETTO.md` §9.1 voce 2 e `README.md`
riportano correttamente la cadenza settimanale e le 03:30. L'intestazione del documento dichiara le
sezioni 1–9 come "il presente", quindi è proprio dove la contraddizione pesa di più.

**Quale sembra l'intenzione corretta** — il **codice**: la cadenza settimanale è una decisione
argomentata nel commento e ripresa in altri due punti della documentazione. Da correggere sono §6
("notturno" → "settimanale, la domenica alle 04:00") e l'elenco di §7.9 (aggiungere le 03:30).

---

### 4. "Sei girano ogni giorno" — in realtà tre sono a intervallo, non giornalieri

**Cosa dice il documento** — `_archivio_docs/README.md`, sezione *File diretti in `backend/`*:

> Sei girano ogni giorno; **controllo delle credenziali e backup girano una volta a settimana, la domenica alle 03:30 e alle 04:00**

e, quasi identica, `_archivio_docs/CODICE_SPIEGATO.md`, §4 *`backend/scheduler.py` — le cose che
accadono da sole*:

> Sei girano ogni giorno. **Controllo delle credenziali e backup girano una volta a settimana**

**Cosa fa il codice** — degli otto job registrati in `backend/scheduler.py:344-437`, solo **tre**
hanno cadenza giornaliera (`cron` alle 03:00, 03:01, 03:02 — `:377-383`, `:403-409`, `:413-419`).
Altri **tre** sono a intervallo e girano molte volte al giorno: promemoria ogni
`REMINDER_CHECK_INTERVAL_MINUTES` (default **5 minuti**, `:351-356` e `:36`), recensioni ogni
`REVIEW_CHECK_INTERVAL_MINUTES` (default 60, `:357-362`), sync calendario ogni
`CALENDAR_SYNC_INTERVAL_MINUTES` (default 60, `:363-368`). I due settimanali sono descritti
correttamente da entrambi i documenti.

**Tipo di divergenza** — documentata in modo ambiguo. "Ogni giorno" non è falso per un job che gira
ogni 5 minuti, ma è la formulazione che fa credere a chi legge di dover aspettare fino a 24 ore
perché parta un promemoria.

**Quale sembra l'intenzione corretta** — il **codice**. La distinzione `interval` / `cron` è
esplicitata da un commento nel sorgente (`backend/scheduler.py:369-370`: *"I job notturni usano
trigger cron, non interval: contano gli orari e non il tempo trascorso dall'avvio"*), quindi è una
scelta consapevole che i due documenti appiattiscono. La formulazione fedele è "tre girano a
intervallo di pochi minuti o di un'ora, tre ogni notte, due una volta a settimana".

---

### 5. L'healthcheck non è più solo di Gmail: i nomi citati non esistono più nel codice

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §1, riga di `scheduler.py`
nell'albero del progetto:

> 8 job periodici APScheduler (promemoria, recensioni, sync calendario, generazione slot, healthcheck Gmail, retention, pulizia slot, backup)

e §6 *Servizi esterni*, voce Gmail API:

> Un job (`controlla_credenziali_gmail`) verifica il token e avvisa su Discord solo alla transizione ok→rotto

e `_archivio_docs/CODICE_SPIEGATO.md`, §5 *Come verificare di non aver rotto niente*:

> **Lo stato globale sopravvive da un test all'altro.** `_ultimo_controllo_gmail_ok`, che ricorda se il token Gmail era valido al giro precedente, è una variabile di modulo

**Cosa fa il codice** — nessuno dei due nomi esiste più (ricerca sull'intero repository: zero
occorrenze). Il job si chiama `controlla_credenziali` (`backend/scheduler.py:252`), itera su tre
credenziali sorvegliate — Gmail, Drive e Calendar — dichiarate in `CREDENZIALI_SORVEGLIATE`
(`backend/scheduler.py:71-95`) e delega a `controlla_una_credenziale`
(`backend/scheduler.py:272`). Lo stato non è un booleano ma un dizionario indicizzato per nome
della credenziale: `_ultimo_controllo_credenziali: dict[str, bool]` (`backend/scheduler.py:53`),
letto a `:280` e scritto a `:300`. La suite usa già i nomi nuovi
(`tests/test_scheduler.py:190,207,245,258,288`).

**Tipo di divergenza** — funzionalità sostituita nel codice ma ancora documentata con il nome
vecchio. È drift da propagazione mancata, non da disaccordo: la generalizzazione è raccontata nello
**stesso file** (`STATO_PROGETTO.md` §21, "una sonda per tre credenziali, e la cadenza settimanale")
ma non è stata riportata all'indietro nelle sezioni di stato §1 e §6, né in `CODICE_SPIEGATO.md`.

**Quale sembra l'intenzione corretta** — il **codice**, senza dubbio: §21 spiega perché la sonda è
stata estesa a tre credenziali (il guasto di Calendar era completamente muto, perché
`sincronizza_slot_con_calendario` cattura ogni errore) e perché gira alle 03:30, mezz'ora prima del
backup. `CODICE_SPIEGATO.md` è il caso più concreto: chi seguisse quel paragrafo per scrivere un
test farebbe `monkeypatch.setattr` su un nome che non esiste.

---

### 6. L'orizzonte di generazione degli slot ("fino a fine mese corrente") non compare in nessun documento corrente

**Cosa dice il documento** — `_archivio_docs/README.md`, sezione *File diretti in `backend/`*, dice
solo:

> generazione notturna degli slot dalle regole ricorrenti

e `_archivio_docs/CODICE_SPIEGATO.md`, §4, solo *"generazione slot notturna"*. Nessuno dei due dice
**fino a quando** genera; `STATO_PROGETTO.md` §4 e §7 nemmeno. L'unico punto dell'archivio che lo
nomina è l'intestazione storica di `_archivio_docs/ROADMAP.md`, che lo cita come cosa già superata:

> la generazione slot non è più "8 settimane in avanti" ma fino a fine mese corrente

**Cosa fa il codice** — `genera_slot_da_regola` si ferma all'ultimo giorno del **mese corrente**:
`backend/services/availability_service.py:69` calcola `ultimo_giorno_mese` con `calendar.monthrange`,
e il ciclo esce a `:79-81` appena lo supera. Il job notturno rilancia la funzione ogni giorno
(`backend/scheduler.py:233`), quindi la finestra si riapre da sola il primo del mese. La conseguenza
osservabile è che l'orizzonte prenotabile mostrato dal sito pubblico oscilla: circa trenta giorni a
inizio mese, quasi zero negli ultimi giorni, poi di colpo di nuovo trenta.

**Tipo di divergenza** — comportamento centrale documentato in modo ambiguo, per omissione. Decide
quanto in là arriva il calendario che lo studente vede, cioè cosa si può prenotare.

**Quale sembra l'intenzione corretta** — il **codice**: la scelta è deliberata e spiegata nel
docstring della funzione (`backend/services/availability_service.py:46-52`, *"la finestra 'fine mese'
si allarga da sola all'inizio di ogni mese"*). Manca però la sua conseguenza — l'orizzonte
oscillante — che è esattamente il tipo di fatto che una sezione di stato deve riportare. Se
l'oscillazione fosse giudicata un difetto di prodotto la correzione starebbe nel codice (finestra
scorrevole a N giorni), ma sarebbe una decisione nuova, non un riallineamento.

---

## Divergenze periferiche

### 7. `.github/workflows/monitor.yml` esiste ma non è nell'albero del progetto

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §1 *Struttura del progetto*, elenca
un solo workflow:

> `.github/workflows/tests.yml  # CI: pytest su ogni push/PR, verde`

**Cosa fa il codice** — i workflow sono due. `.github/workflows/monitor.yml` interroga
`https://vgc-coaching-production.up.railway.app/health` (`.github/workflows/monitor.yml:48`) ogni 15
minuti (`:23`), con tre tentativi (`:60-67`), avvisa su Discord solo alle transizioni di stato
(`:93-97`) ed esce con codice di errore quando il sito è giù (`:116`).

**Tipo di divergenza** — funzionalità implementata ma non documentata nella sezione di stato. Come
la voce 5, è propagazione mancata: lo stesso file la descrive in §21.2 e in §9.1 voce 3, e
`README.md` la cita nella sezione *Deploy*.

**Quale sembra l'intenzione corretta** — il **codice**. All'albero di §1 va aggiunta la seconda riga.

---

### 8. L'albero di §1 colloca i documenti nella root, dove non stanno più

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §1, elenca fra i file di root:

> `ANALISI_2026-08-31.md`, `ANALYSIS.md`, `CODICE_SPIEGATO.md`, `RAILWAY_RIALLINEAMENTO_2026-09-02.md`, `README.md`, `ROADMAP.md`, `REVISIONE_2026-09-01.md`, `STATO_PROGETTO.md`

**Cosa fa il codice** — la root contiene oggi `AUDIT.md` e questo `DRIFT.md`; tutti e otto i markdown
citati vivono in `_archivio_docs/`, insieme alla sottocartella `_archivio_docs/audit/`
(`piano-interventi.md`, `r1-architettura.md`, `r2-security.md`, `r3-ops.md`, `r4-maintainer.md`),
che l'albero non menziona affatto.

**Tipo di divergenza** — struttura spostata ma ancora documentata al vecchio posto. È la conseguenza
diretta del commit di archiviazione `2f912d2`, non un disallineamento anteriore.

**Quale sembra l'intenzione corretta** — il **filesystem**: l'archiviazione è stata un atto
deliberato. Va aggiornato l'albero, e va deciso esplicitamente se `_archivio_docs/audit/` sia
materiale di lavoro ancora vivo o materiale chiuso.

---

### 9. "Tutte e 32 le variabili": la tabella del README ne elenca 31

**Cosa dice il documento** — `_archivio_docs/STATO_PROGETTO.md`, §5 *Variabili d'ambiente*:

> **L'elenco completo sta in un posto solo: la tabella di `README.md`**, che riporta tutte e 32 le variabili lette dal codice con obbligatorietà, default e descrizione.

**Cosa fa il codice** — l'inventario di `AUDIT.md` §4.3 conta 32 nomi, ma il trentaduesimo è `PORT`,
che **non è letta da codice Python**: compare solo nel comando di avvio (`nixpacks.toml:5`,
`--port $PORT`) ed è fornita dalla piattaforma di esecuzione. La tabella del `README.md` elenca gli
altri 31 e non la nomina mai.

**Tipo di divergenza** — documentata in modo ambiguo: il conteggio torna solo includendo una
variabile che la tabella referenziata, per una ragione difendibile, non contiene.

**Quale sembra l'intenzione corretta** — il **documento**, con una precisazione. La scelta di tenere
l'elenco in un posto solo è argomentata bene in §5 e va conservata; basta scrivere "tutte le 31
variabili lette dal codice applicativo — `PORT` è fornita dalla piattaforma e vive in
`nixpacks.toml`", che è anche il modo in cui `AUDIT.md` §4.3 la riporta.

---

## Nota finale — due punti in cui è `AUDIT.md` a essere incompleto, non il documento

Il confronto ha prodotto anche il caso opposto: due affermazioni dei documenti che l'audit non
riporta e che il codice conferma. Sono elencate qui perché la correzione va fatta su `AUDIT.md`,
non su `_archivio_docs/`.

- **`/docs`, `/redoc`, `/openapi.json`.** `STATO_PROGETTO.md` §3 li elenca come pubblici e come
  scelta consapevole ("disattivabile con `docs_url=None` in `backend/main.py` se un domani non la si
  vuole più"). L'inventario degli endpoint di `AUDIT.md` §2.9 non li contiene. Il codice dà ragione
  al documento: `backend/main.py:129` costruisce `FastAPI(title=..., version=..., lifespan=...)`
  senza `docs_url`/`redoc_url`/`openapi_url`, quindi le tre rotte di default sono attive e senza
  autenticazione. È l'unica superficie HTTP pubblica che l'inventario dell'audit non copre.
- **Cosa fa `tests/conftest.py`.** `AUDIT.md` §5 lo descrive come "sostituisce `get_db` con un SQLite
  in memoria (`:32-48`) e disattiva il rate limiter (`:55`)", mentre `README.md` e
  `CODICE_SPIEGATO.md` §5 dicono anche che spegne le integrazioni esterne. Hanno ragione i documenti:
  la fixture autouse `integrazioni_esterne_finte` (`tests/conftest.py:72-100`) sostituisce con no-op
  dieci funzioni di Calendar, email e Discord nei tre router che le chiamano. L'audit aveva
  dichiarato `tests/` fuori perimetro e ha letto `conftest.py` solo per la sezione Comandi, quindi
  l'omissione è coerente con il perimetro dichiarato — ma la riga, come è scritta, si legge come una
  lista completa.

**Sui documenti storici.** `ANALYSIS.md`, `ROADMAP.md`, `ANALISI_2026-08-31.md`,
`REVISIONE_2026-09-01.md` e `RAILWAY_RIALLINEAMENTO_2026-09-02.md` divergono dal codice in
moltissimi punti — endpoint pubblici oggi chiusi, SendGrid al posto dell'API Gmail, la tabella
`payments`, i prezzi 35/60/80€, lo scheduler dato per inesistente. Nessuno di questi è drift: tutti
e cinque portano in testa un'intestazione che dichiara la data della fotografia, elenca i punti
superati e vieta l'aggiornamento. Sono verbali, e un verbale corretto a posteriori smette di essere
una prova. L'unica cosa che li tiene sani è che nessun documento di stato li citi come fonte sul
presente — condizione oggi rispettata.
