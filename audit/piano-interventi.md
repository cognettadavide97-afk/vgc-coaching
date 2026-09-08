# Piano interventi — riconciliazione dei quattro report di audit

**Data:** 2026-09-07 · **Input:** `audit/r1-architettura.md`, `r2-security.md`, `r3-ops.md`, `r4-maintainer.md`

**Vincoli usati per decidere, che i revisori non avevano:** un manutentore solo, nessun ambiente di staging, produzione viva su Railway con monitoraggio esterno attivo dal 07/09, traffico di poche richieste al giorno, un unico amministratore, nessun pagamento online.

**Metodo.** Ho unificato i finding che descrivono lo stesso problema da angoli diversi, li ho classificati, e ho applicato a ciascuno i tre test (danno concreto / costo-beneficio / rischio di regressione). Dove la decisione dipendeva da un fatto sono andato a leggere il codice invece di fidarmi del report: i punti verificati sono marcati **[ricontrollato]**.

**Esito in una riga:** su 51 finding unificati, **7 diventano PULIZIA**, **4 diventano REFACTOR**, **40 restano fermi**.

---

## PARTE A — Riconciliazione e deduplicazione

### A.1 I finding unificati

Le passate che hanno visto lo stesso problema sono elencate insieme: la convergenza di più revisori indipendenti pesa, e dove pesa lo dico.

| # | Finding unificato | Visto da | Classe |
|---|---|---|---|
| **U01** | Uno slot bloccato non torna mai prenotabile: nessuna riga scrive `blocked_*=False` | r1 A1, r4 M8 | **CONFERMATO** |
| **U02** | La data di assegnazione del pacchetto è mostrata in UTC | r1 A3 | **DERIVA** |
| **U03** | Il frontend scarta il `detail` sulla creazione prenotazione | r1 A12 | **CONFERMATO** |
| **U04** | I log dicono chi quando funziona, niente quando fallisce | r3 O10+§1, r2 S12 | **CONFERMATO** |
| **U05** | `date.today()` nel generatore di slot | r4 M1 | **DERIVA** |
| **U06** | `reminder_sent` registra "ho provato", non "è arrivata" | r3 O2, r4 §5 | **CONFERMATO** |
| **U07** | Il banco di prova non vede ciò che la produzione applica | r3 O5, r4 M2+M3+§4.3, r1 A8 | **CONFERMATO** |
| **U08** | Importare un modulo carica le credenziali di produzione | r2 S15, r1 A5 | **CONFERMATO** |
| **U09** | Un a-capo nel nome sopprime la notifica al coach | r2 S2 | **CONFERMATO** |
| **U10** | Due credenziali vive e non più usate nel `.env` | r2 S10 | **CONFERMATO** |
| **U11** | Il backup non ha modo di accorgersi di non essere partito | r3 O1, r4 §5 | **CONFERMATO parziale** |
| **U12** | Google Calendar chiamato dentro la transazione che tiene il lock | r1 §3, r2 §3, r3 O3, r4 §5 | **CONFERMATO** |
| **U13** | Doppia spesa di un pacchetto (incremento non atomico) | r2 S3 | **CONFERMATO** |
| **U14** | Prenotazione a nome di terzi + oracolo email→`user_id` | r2 S1+D1, r3 §4, r4 §5 | **CONFERMATO** |
| **U15** | Il rate limit conta probabilmente per proxy, non per client | r2 S5, r4 M10 | **DA VERIFICARE** |
| **U16** | `note_admin` nel `response_model` di un endpoint pubblico | r2 S6, r3 §4 | **CONFERMATO (latente)** |
| **U17** | Nessuno schema dichiara `max_length` | r2 S4, r3 §4, r4 §4.3 | **CONFERMATO parziale** |
| **U18** | Il dominio della prenotazione vive dentro l'handler HTTP | r1 A2 | **DEBITO ACCETTATO** |
| **U19** | Il listino e il catalogo pacchetti in cinque copie | r1 A4, r4 M6 | **DEBITO ACCETTATO** |
| **U20** | Nessun client API nel frontend: 25 `fetch`, gestione errori a caso | r1 A7 | **DEBITO ACCETTATO** |
| **U21** | Dependency di autorizzazione dentro i router, import in fondo al file | r1 A6, r4 M5 | **DEBITO ACCETTATO** |
| **U22** | Il ventaglio di notifiche duplicato in tre router | r1 A5 | **DEBITO ACCETTATO** |
| **U23** | Divergenza SQLite/MySQL: collation, fuso di `NOW()`, `crea_dump_sql` | r3 O6+O7+O8, r4 §4.3, r1 §3, r2 §3 | **DA VERIFICARE** |
| **U24** | Nessun retry su nessuna chiamata esterna | r3 O11 | **DEBITO ACCETTATO** |
| **U25** | 40 thread contro 15 connessioni; `/health` attinge allo stesso pool | r3 O4 | **DEBITO ACCETTATO** |
| **U26** | Lo scheduler gira nel processo web senza elezione di un leader | r3 O13, r1 §3 | **DA VERIFICARE** |
| **U27** | Una migrazione fallita lascia partire l'app, e l'avviso può sparire | r3 O12, r2 §3, r1 §4 | **DEBITO ACCETTATO** |
| **U28** | Due commenti descrivono un'architettura che non esiste | r1 A10 | **CONFERMATO** |
| **U29** | `formatta_data_ora_rome` reimplementato nei due punti che fanno le email | r1 A9 | **DERIVA** |
| **U30** | Recensione lasciabile per una sessione mai svolta | r2 S9 | **DEBITO ACCETTATO** |
| **U31** | Testo pubblico negli embed Discord senza escape del markdown | r2 S8, r3 §4 | **CONFERMATO** |
| **U32** | Token recensione non ASCII → 500 | r2 S7, r3 §4 | **CONFERMATO** |
| **U33** | Il flag `Secure` dipende da una variabile non correlata | r2 S11 | **FALSO POSITIVO** + debito |
| **U34** | Il testo di un'eccezione di migrazione inoltrato su Discord | r2 S13 | **DA VERIFICARE** |
| **U35** | 39 endpoint su 45 senza rate limit; vetrina recensioni senza `LIMIT` | r2 S14 | **DEBITO ACCETTATO** |
| **U36** | L'app funziona solo con working directory alla radice | r4 M4 | **DEBITO ACCETTATO** |
| **U37** | 36 date fissate al 2030 nei test | r4 M9 | **DEBITO ACCETTATO** |
| **U38** | `AvailabilityRule.attiva` filtra un job e non è scrivibile | r4 M8 | **CONFERMATO** |
| **U39** | Paginazione ordinata su una colonna non univoca | r3 O16 | **CONFERMATO** |
| **U40** | Il margine di 6 ore accoppiato a una regola imposta altrove | r4 M11 | **DEBITO ACCETTATO** |
| **U41** | Il `README.md` non dice da dove si entra | r4 M12 | **CONFERMATO parziale** |
| **U42** | Il dump tiene tre copie del database in memoria | r3 O14 | **DEBITO ACCETTATO** |
| **U43** | Cache credenziali Google condivisa fra thread senza lock | r3 O15 | **DEBITO ACCETTATO** |
| **U44** | `libera_slot_prenotazione` fa una chiamata di rete | r4 M7 | **DEBITO ACCETTATO** |
| **U45** | `elimina_slot_obsoleti` carica tutto in memoria | r1 §3, r2 §3 | **DEBITO ACCETTATO** |
| **U46** | `elimina_cliente` è irreversibile e senza conferma lato server | r1 §3 | **DEBITO ACCETTATO** |
| **U47** | `renderPaginazione` interpola un nome di funzione in un `onclick` | r1 §3 | **CONFERMATO** |
| **U48** | `POST /slots/` è l'unica scrittura admin fuori da `/admin` | r1 A11 | **DEBITO ACCETTATO** |
| **U49** | Token admin da 8 ore, non revocabile | r2 D2 | **DEBITO** + prescrizione **FALSA** |
| **U50** | Il login admin distingue username giusto dal tempo di risposta | r2 D3 | **DEBITO ACCETTATO** |
| **U51** | "Backend senza web framework" nel contesto della committenza | r1 §0, r2 §0 | **FALSO POSITIVO** |

### A.2 Le tre riconciliazioni che cambiano qualcosa

**U04 — due revisori puntano alla stessa riga in direzioni opposte, e si risolvono con una modifica sola.** r3 (O10) chiede di aggiungere contesto alle righe di errore; r2 (S12) chiede di togliere le email dalle righe di successo, perché sono dati personali che restano nei log di Railway e **non rientrano né nel job di anonimizzazione (`retention_service.py:50-55`) né nella cancellazione GDPR (`admin/clients.py:95-133`)** — un cliente cancellato dal database resta identificabile nei log. `email_service.py:150-152` è la stessa coppia di righe. Sostituire l'indirizzo con il `booking_id` soddisfa i due finding insieme.

**U12 — quattro revisori su quattro, e resta fermo.** È l'unico punto su cui tutte le passate convergono, e la convergenza va detta. Ma tutte e quattro hanno visto lo *stesso odore di codice*, non un danno: nessuna ha prodotto uno scenario che si verifichi a questo traffico, perché servono due prenotazioni simultanee sullo stesso slot *più* Google lento. La convergenza di più revisori su un difetto strutturale non è una prova di danno; è una prova che il difetto è visibile.

**U07 — tre report e il tuo stesso backlog dicono la stessa cosa.** r3 (O5, foreign key non applicate), r4 (M2 notifiche mai osservate, M3 limite mai testato, §4.3 l'elenco completo delle divergenze), r1 (A8, due sorgenti di verità per lo schema) e la **voce 12 di §9.1** descrivono lo stesso confine. È l'unico caso in cui la convergenza corrisponde anche a un danno, e ha una forma precisa: non è che la produzione sia rotta, è che **la suite non può dirti se lo è**.

### A.3 Risposte ai `[DA GIUSTIFICARE]`

Regola applicata: una motivazione nelle note non chiude un finding. Deve reggere sul codice di oggi.

**A11 — `POST /slots/` fuori dal prefisso `/admin`.**
*Motivazione documentata:* `backend/routers/slots.py:1-5`, docstring del modulo — *"La lettura è pubblica (serve al form di prenotazione, che non richiede login), la scrittura è riservata all'amministratore."* Il modulo è organizzato **per risorsa**; il pacchetto `admin/` è organizzato **per audience**. Sono due convenzioni, entrambe dichiarate.
*Regge sul codice di oggi?* **Sì** [ricontrollato]: `create_slot` (`slots.py:50`) applica `Depends(get_admin)`, e la protezione non dipende dal prefisso. → **DEBITO ACCETTATO**.
*Cosa lo renderebbe non accettabile:* un secondo endpoint pubblico che scriva sugli slot, o un client esterno che consumi `/slots/`. Allora il prefisso diventa parte del contratto.

**A12 — messaggi d'errore in due lingue.**
*Motivazione documentata:* `README.md:177` — *"Il pannello admin non lo usa: essendo per il solo coach, resta in italiano."* Il lato admin è deliberato e regge.
*Regge sul lato pubblico?* **No, ma non per il motivo del revisore** [ricontrollato]. La domanda "in che lingua arriva il `detail` all'utente italiano" è accademica, perché `frontend/js/app.js:534` fa `if (!bookingResponse.ok) throw new Error(...)` e il `catch` mostra `t('generic_error')`: **il `detail` non arriva mai**. Il finding si scinde — la parte sulla lingua è debito accettato, la parte "il messaggio preciso non raggiunge il cliente" è un difetto vivo → **P3**.

**D1 — perché `POST /bookings/` accetta `user_id` dal client.**
*Motivazione documentata:* `booking.py:99-109` e `app.js:521-522`. Il commento è lungo e onesto: dichiara che `user_id` da solo non è una prova e che la verifica `user_id`↔`email` alza il costo *"da indovina un id a conosci già l'email della vittima"*.
*Regge?* **Il commento giustifica il controllo, non la presenza del campo.** `get_or_create_user` (`users.py:104`) esiste già ed è già condivisa con i form di contatto: il server sa risolvere un'email da solo. → **DERIVA parziale**, ma l'intervento è subordinato a U15; vedi §B.1(c).

**D2 — token admin da 8 ore.**
*Motivazione documentata:* `auth_service.py:42-43` — il JWT è stateless, la scadenza viaggia dentro il token, *"di conseguenza un token non può essere revocato prima della scadenza"*. Scelta consapevole e dichiarata. `admin.js:9-12` tiene il token solo in memoria.
*Regge?* Sì, **e la prescrizione del revisore è sbagliata** [ricontrollato]. `EXPIRE_MINUTES` (`auth_service.py:21`) è **condiviso**: alimenta `crea_token` (admin, riga 44), `crea_token_studente` (riga 60) e il `max_age` del cookie di sessione studente (`discord_auth.py:183`). Portarlo a 60 minuti come suggerito **scollegherebbe ogni studente ogni ora**, su un login pensato per durare. Il revisore vedeva solo il lato admin.
→ **DEBITO ACCETTATO**; la prescrizione è un **FALSO POSITIVO**.
*Cosa lo renderebbe non accettabile:* più di un amministratore, oppure il token che inizia a sopravvivere al ricaricamento della pagina. In quel caso l'intervento non è cambiare il numero, è **separare la costante admin da quella studente** — che è un intervento, non una riga.

**D3 — il login distingue lo username giusto dal tempo di risposta.**
*Motivazione documentata:* nessuna. Il finding è reale [ricontrollato]: `auth_service.py:29-30` esce prima di `bcrypt.checkpw`.
*Valutazione:* il canale rivela **lo username, non la password**, che resta protetta da bcrypt. Un solo amministratore, un solo username. → **DEBITO ACCETTATO**.
*Cosa lo renderebbe non accettabile:* più amministratori, o uno username che valga di per sé.

### A.4 I falsi positivi

**U51 — il contesto dice "backend senza web framework", ed è falso.** r1 e r2 aprono entrambi rettificandolo, e r1 suggerisce di risalire al documento che lo afferma, perché *"un documento di progetto che descrive un'architettura diversa da quella in essere è già di per sé un problema"*. **Non esiste quel documento** [ricontrollato]: in tutto il repository la frase "nessun framework" si riferisce sempre e solo al **frontend**, ed è corretta — `STATO_PROGETTO.md:11`, `README.md:43,177`, `ANALYSIS.md:15,54`, `CODICE_SPIEGATO.md:499`. L'errore stava nel briefing consegnato ai revisori. **Nessuna azione sul repository**; è una nota di processo per la prossima revisione che commissionerai — è costato a due passate su quattro la sezione di apertura.

**U33 — il flag `Secure` del cookie.** r2 lo marca `[SOSPETTO]` e indica come confermarlo. **È già stato verificato**: `STATO_PROGETTO.md:413` registra il login Discord provato end-to-end in produzione il 2026-09-02, *"con cookie `student_token` marcato `Secure` e `HttpOnly`, controllato da DevTools"*. Il sospetto è chiuso. Resta la fragilità strutturale (il flag dipende da `DISCORD_OAUTH_REDIRECT_URI`, che serve ad altro) → debito, §B.1(d).

**U49 — la prescrizione su D2**, vedi §A.3.

**U28 — mezzo falso positivo, mezzo confermato.** L'import locale in `calendar_service.py:198-200` è motivato da un ciclo che **non esiste** [ricontrollato]: nessun file di `backend/models/` importa alcunché da `backend/services/`. Il commento insegna una regola di dipendenza falsa. Confermato, ma cosmetico → §B.1(f).

---

## PARTE B — Serve intervenire?

## B.1 Cosa NON va toccato

Questa è la sezione principale del piano. **40 finding su 51 restano fermi.** Per ciascun gruppo indico il motivo e, dove esiste, il fatto che cambierebbe la risposta.

### (a) Rifatture che comprano manutenibilità che non stai pagando

| # | Finding | Costo proposto | Perché no |
|---|---|---|---|
| **U18** | `create_booking` è 230 righe e contiene il dominio | 1 giorno (r1) | Il beneficio dichiarato è *"fra sei mesi l'autore cerca il vincolo delle 2 ore in un service e non lo trova"*. Quell'autore sei tu, e lo cercherai in `booking.py`, perché ce l'hai messo tu. Il secondo punto d'ingresso che giustificherebbe l'estrazione non esiste e non è previsto. Fallisce il **test 3**: un giorno di lavoro sulla funzione che non deve rompersi, il cui percorso calendario è mockato nei test. |
| **U19** | Il listino in cinque copie, `GET /catalogo` | mezza giornata (r1) | Il prezzo cambia quasi mai. E la cura peggiora una cosa: costruire le card del listino da un endpoint aggiunge una dipendenza a runtime alla pagina di marketing, che oggi è statica e funziona anche con l'API giù. Fallisce il **test 1** e il **test 2**. |
| **U19b** | `Literal[tuple(CATALOGO_PACCHETTI)]` | 20 min (r4 M6) | Fallisce il **test 1**: il danno si materializza solo il giorno che aggiungi un pacchetto. **Trigger:** quel giorno, fai questo *prima* di aggiungerlo — ti risparmia un 500 da `KeyError` al posto di un 422. |
| **U20** | Client API nel frontend, 25 `fetch` | mezza giornata (r1) | Il sintomo reale (un errore mai mostrato) è isolato e costa 15 minuti → **P3**. La gestione centrale del 401 vale per un pannello usato da una persona che può ricaricare la pagina. |
| **U21** | `dependencies.py`, `user_service.py` | 2h (r1 A6) | Il revisore lo definisce *"meccanico e a rischio nullo"*. È vero, ed è anche **a beneficio nullo**: riordina un grafo di import che non dà fastidio a nessuno. Fallisce il **test 1**. |
| **U21b** | `# isort: skip_file` | 5 min (r4 M5) | Nel repository non esiste alcun linter o formatter [verificato da r4: niente `pyproject.toml`, `setup.cfg`, `.isort.cfg`, `.flake8`, `.pre-commit-config.yaml`]. Se un giorno premi "organize imports", l'app non parte e il commento sulla riga sopra ti dice perché in dieci secondi. **Trigger:** il giorno che aggiungi un formatter. |
| **U22** | `notifiche_service` per i tre eventi | mezza giornata (r1 A5) | Tre casi d'uso ci sono, quindi la regola delle tre istanze è soddisfatta — ma il beneficio è ordine, non correttezza. La metà che conta di questo finding è U08, che entra come **R4**. |
| **U44** | `libera_slot_prenotazione` fa rete, va rinominata o spezzata | 1h (r4 M7) | La docstring elenca onestamente tutte e quattro le cose che fa: il nome non mente, il commento lo dice. Preferenza di collocazione. |

### (b) Difese contro un carico che non hai

| # | Finding | Perché no | Trigger |
|---|---|---|---|
| **U12** | Google Calendar dentro la transazione con il lock | **Visto da tutte e quattro le passate**, e resta fermo: serve una seconda prenotazione simultanea *sullo stesso slot* mentre Google è lento. A questo traffico non accade. Fallisce il **test 2** (2h sulla funzione più critica) e il **test 3** | Il primo 500 con errore MySQL 1205, o il traffico che rende plausibili due prenotazioni nello stesso minuto |
| **U13** | Doppia spesa del pacchetto | Non è un incidente: richiede che un cliente con pacchetto spari due richieste **deliberatamente simultanee**. Il guadagno è una sessione. E la correzione tocca `create_booking` | `SELECT * FROM packages WHERE sessioni_usate > sessioni_totali` restituisce una riga — controllo da dieci secondi, se mai sospetti qualcosa |
| **U25** | 40 thread / 15 connessioni, `/health` nel pool | Il pool si satura alla sedicesima richiesta **simultanea**. Non ci arrivi | Un `TimeoutError: QueuePool limit` nei log |
| **U24** | Nessun retry | Reale, e la cura non è uniforme perché `events().insert` non è idempotente: ritentarlo crea eventi doppi sul tuo calendario. Va progettato operazione per operazione, per un guasto che non hai misurato | Email o notifiche perse in modo ricorrente, una volta che **P2** ti permette di contarle |
| **U26** | Scheduler senza leader election | Dipende dal numero di repliche → **§B.2**. Se è 1, il finding non esiste | Repliche > 1 |
| **U42** | Il dump tiene tre copie in memoria | Il revisore stesso scrive *"non è urgente"*. Il database è piccolo | Il primo riavvio del container la domenica alle 04:00 |
| **U43** | Cache credenziali non sincronizzata | La manifestazione è dichiarata non provata dal revisore stesso, e sarebbe un fallimento sporadico | Fallimenti di autenticazione Google intermittenti e inspiegati |
| **U45** | `elimina_slot_obsoleti` carica tutto in memoria | Segnalato da due passate, entrambe **fuori mandato** e senza approfondimento. Volumi da centinaia di righe | — |
| **U35** | 39 endpoint su 45 senza rate limit | **Non è solo "non adesso", è nell'ordine sbagliato**, e r2 lo dice: aggiungere rate limit prima di aver risolto U15 moltiplica gli endpoint che un singolo visitatore può spegnere per tutti | Dopo U15, e solo se U15 si conferma |

### (c) Sicurezza reale, ma subordinata a una verifica che costa zero

| # | Finding | Perché non entra adesso |
|---|---|---|
| **U14** | Prenotazione a nome di terzi (l'unico **BLOCCANTE** dell'audit) | I due interventi proposti sono entrambi sbagliati per te. Il **tampone** (togliere `user_id`, 2h) non chiude il problema: chiunque può ancora prenotare con un'email inventata, e l'unica conseguenza irreversibile — un'email spedita dal tuo Gmail a un indirizzo scelto da altri — resta identica. La **cura** (`pending` + link di conferma, 1-2 giorni) chiude tutto ma mette un click in più fra ogni cliente onesto e la sua prenotazione, sul flusso che è il prodotto: fallisce il **test 2** per un manutentore solo senza staging. Tutto il resto del danno è reversibile dal pannello in minuti (cancelli le prenotazioni false, `libera_slot_prenotazione` rilascia gli slot). Quello che tiene sotto controllo la parte irreversibile è il rate limit — cioè **U15**, che si verifica gratis. |
| **U15** | Il rate limit conta per proxy, non per client | Non è un intervento di codice: è una riga di log da leggere e una variabile d'ambiente → **§B.2** |
| **U17** | Nessun `max_length` | Metà del danno (`Data too long` → 500 con un evento Calendar orfano) dipende da `sql_mode` su MySQL, che nessuno ha verificato. Applicare `max_length` a tutti gli schemi tocca la validazione di **ogni** endpoint: un limite troppo stretto rifiuta input legittimi, e il frontend non ha test. Fallisce il **test 3** finché il danno non è confermato → verifica in **§B.2**, poi si riapre. La parte già dimostrata e isolata entra come **P5**. |

> **Se dovesse mai servire, la terza opzione su U14 che nessun revisore propone:** un tetto giornaliero assoluto sulle prenotazioni senza login (venti al giorno, un contatore, un alert Discord al superamento), circa un'ora. Non impedisce l'abuso, ma limita l'unico danno che non puoi annullare — la reputazione di invio del tuo Gmail. **Trigger:** la prima prenotazione falsa che vedi arrivare.

### (d) Reale, ma già coperto da un controllo che esiste

| # | Finding | Il controllo che c'è già |
|---|---|---|
| **U30** | Recensione per una sessione mai svolta | Nessuna recensione è pubblica prima della tua approvazione (`models/review.py:22`). Il controllo sei tu, ed è esattamente il caso — un no-show che valuta una sessione a cui non ha partecipato — in cui vuoi decidere a mano |
| **U33** | Cookie `Secure` | Verificato in produzione il 02/09 (§A.4). Resta la fragilità: 15 minuti per una variabile `COOKIE_SECURE` esplicita, quando passi di lì |
| **U46** | `elimina_cliente` irreversibile senza conferma lato server | Raggiungibile solo con il token admin, cioè da te. La conferma esiste dove serve, nel pannello |
| **U50** | Timing sul login admin | §A.3: rivela lo username, non la password. Un solo amministratore |
| **U11b** | Allarme sull'**assenza** del backup (3h) | Il backup **gira**: `STATO_PROGETTO.md:411` registra la cartella Drive interrogata il 04/09, con i dump del 2, 3 e 4 settembre. Tre ore per costruire un monitor su un job che hai osservato funzionare tre giorni fa, quando apri quella cartella periodicamente. La parte da cinque minuti entra come **P7**. **Trigger:** la prima domenica in cui apri Drive e non trovi il dump |

### (e) Problemi che non esistono ancora

| # | Finding | Quando esisterà |
|---|---|---|
| **U36** | Working directory alla radice | Solo se aggiungi un `Dockerfile` con un `WORKDIR` diverso, o lanci `uvicorn` da un'altra cartella. Non lo stai facendo, e il giorno che lo farai l'errore arriva subito, all'import, non in produzione a metà giornata |
| **U37** | 36 date fissate al 2030 | Fra quattro anni |
| **U39** | Paginazione senza tie-break | Servono due righe create nello **stesso secondo** in una lista che supera una pagina. Prenotazioni e pacchetti li crei uno alla volta. **Trigger:** una lista paginata popolata da un batch (generazione slot) |
| **U40** | Il margine di 6 ore accoppiato alla durata massima | Diventa vero solo se ammetti sessioni più lunghe di 2 ore — cambiamento che tocca già sei punti, e questo sarebbe il settimo che trovi mentre lo fai |
| **U38** | `attiva` non scrivibile da nessun endpoint | È una **funzione mancante**, non un difetto: il model lo dichiara onestamente (`availability_rule.py:30-31`). Un'ora, il giorno che ti serve sospendere il martedì per un mese |
| **U41** | Il `README.md` non dice da dove si entra | La premessa è in parte smentita dai revisori stessi: tutte e quattro le passate hanno trovato `STATO_PROGETTO.md` e nessuna si è fatta ingannare dai banner "DOCUMENTO STORICO". Il lettore che ne beneficerebbe non esiste: sei tu, e l'hai scritto tu tre mesi fa |

### (f) Costo bassissimo, ma falliscono il test del danno

Li tengo fuori **per disciplina, non perché siano sbagliati**. Se vuoi ribaltarne uno è una tua parola e sono dieci minuti a testa — ma nessuno produce un danno oggi né in uno scenario imminente, e includerli è il modo in cui un lotto da un'ora diventa un lotto da tre.

| # | Finding | Costo | Perché resta fuori |
|---|---|---|---|
| **U16** | `note_admin` nel `response_model` pubblico | 5 min | Il campo è **sempre `None`** su quell'endpoint: `POST /bookings/` crea una prenotazione nuova, e `note_admin` lo scrivi tu dopo. Perché trapeli, qualcuno dovrebbe far restituire a quell'endpoint una prenotazione esistente. *(È il più vicino al sì di tutta la tabella: lo schema corretto — `BookingResponseStudente` — esiste già ed è già usato due funzioni più sotto.)* |
| **U29** | `formatta_data_ora_rome` reimplementato | 10 min | Duplicazione letterale di tre righe, in un helper la cui docstring dice di esistere apposta. Il danno si materializza solo se cambi il formato delle date |
| **U28** | Due commenti che descrivono un'architettura inesistente | 15 min | Il ciclo di import non esiste; `alembic/env.py:14` elenca sei model su otto e funziona solo perché `models/__init__.py` li importa tutti. Nessuno dei due fa danno finché non ci si crede |
| **U31** | Escape del markdown negli embed Discord | 30 min | Serve qualcuno che scelga di scriverti un link mascherato nel campo note. Il canale è il tuo, e i messaggi li leggi tu |
| **U32** | 500 su token recensione non ASCII | 10 min | Il danno dichiarato è "sporca i log". Per il cliente, 403 e 500 sono la stessa cosa: il link non funziona |
| **U47** | `renderPaginazione` interpola un `onclick` | 20 min | Contraddice il commento in testa allo stesso file, che è un buon argomento estetico e non un danno: i valori interpolati sono nomi di funzione scelti dal codice, non input |

### (g) La risposta giusta costa mezza giornata, e il 10% del costo compra l'80% del beneficio

| # | Finding | La cura completa | Cosa faccio invece |
|---|---|---|---|
| **U23** | Parità SQLite/MySQL | Un MySQL come service container in CI (mezza giornata + una CI permanentemente più fragile, mantenuta da una persona) chiuderebbe collation, fuso, lunghezze colonne, `crea_dump_sql` e le foreign key in un colpo | `PRAGMA foreign_keys=ON` in `conftest.py`, dentro **R1**: trenta minuti, e compra la classe di errore che ti riguarda davvero — l'ordine di eliminazione nella cancellazione GDPR |
| **U27** | Migrazione fallita, avvio comunque | `/health` che risponde 503 `{"stato": "degradato"}` (2h) | Niente, per ora. È il completamento naturale del monitoraggio che hai appena finito, e ha senso come **prossima** sessione di monitoraggio, non dentro questo lotto |
| **U34** | Testo dell'eccezione inoltrato su Discord | 10 min | Subordinato: prima verifica se `DATABASE_URL` compaia davvero in un messaggio d'errore di Alembic (§B.2). Il canale Discord è tuo, quindi anche nel caso peggiore la password finisce in una chat che leggi solo tu |

---

## B.2 Prerequisiti — 30 minuti, nessun codice

Nove finding sono marcati `[SOSPETTO]` e dipendono tutti dalla produzione, a cui nessun revisore aveva accesso. Non ha senso pagare per difendersi da qualcosa che si conferma leggendo.

| Verifica | Dove | Cosa decide |
|---|---|---|
| **U15** — `request.client.host` nei log è sempre lo stesso indirizzo interno (`10.x`, `100.64.x`)? | log Railway | Se sì, **il rate limit non esiste**: è un limite globale condiviso, e chiunque con 5 richieste al minuto chiude fuori dal pannello **te** (`POST /admin/login`) e blocca il form di prenotazione per tutti. Non serve un attaccante: basta un annoiato. Rimedio: `FORWARDED_ALLOW_IPS` sull'intervallo del proxy — **mai `*`** |
| **U23a/b** — `SELECT @@global.time_zone, NOW(), UTC_TIMESTAMP(), @@collation_database, 'A'='a';` | MySQL | Se `NOW() = UTC_TIMESTAMP()` e `'A'='a'` vale `1`, **due finding si chiudono senza scrivere una riga** |
| **U17** — `SELECT @@sql_mode;` | MySQL | Se `STRICT_TRANS_TABLES` è attivo, U17 si riapre come intervento vero |
| **U25b** — c'è un health check configurato su `/health`, e con che soglia? | dashboard Railway | Se c'è, un pool saturo fa riavviare un processo che è soltanto occupato |
| **U26** — quante repliche? | dashboard Railway | Se è 1, quattro finding di concorrenza cadono in blocco |

---

## B.3 PULIZIA — interventi locali, a rischio nullo

Ordinati per rapporto beneficio/rischio.

---

### P1 · La data di assegnazione del pacchetto è in UTC

**Origine:** r1 §A3 (unica passata) — ma il peso non viene dal revisore, viene dal tuo diario.
**File:** `backend/schemas/package.py:28` · `backend/routers/admin/packages.py:19` · `frontend/js/admin.js:734`
**Classe:** DERIVA — la ragione è valida e recentissima, il codice non la applica dappertutto.

Il 2026-09-07 hai corretto `created_at` mostrato in UTC in **quattro** punti — lista prenotazioni, export CSV, lista clienti, lista recensioni — con due test costruiti apposta a cavallo della mezzanotte, e il coach ha confermato in produzione che le date sono in ora italiana (`STATO_PROGETTO.md` §22.2, righe 1603-1615). La lista pacchetti non è stata toccata: `PackageResponse.created_at` è un `datetime` naive grezzo e `admin.js:734` lo rende con `.replace('T',' ').slice(0,16)` [ricontrollato].

**Test 1 — danno concreto.** Oggi, nel pannello, la colonna "Assegnato il" dei pacchetti è sfalsata di **due ore** rispetto a ogni altra data della stessa interfaccia. È visibile adesso, ed è esattamente il difetto che hai dichiarato chiuso ieri.
**Test 2 — costo/beneficio.** Dieci minuti contro una correzione che risulta fatta e non lo è.
**Test 3 — regressione.** Un endpoint, una colonna di una tabella. Nessun'altra schermata legge `PackageResponse.created_at`.

**Intervento.** Allineare `/admin/pacchetti` ai quattro endpoint già corretti: preformattare `created_at` con `formatta_data_ora_rome` nel router e togliere il `.replace/.slice` in `admin.js:734`. *Nota:* r1 raccomanderebbe la convenzione opposta (ISO dal server, formattazione nel frontend). **Scelgo la coerenza con la decisione che hai già preso su quattro endpoint**: cambiare convenzione qui è §B.1(a), non è questo intervento.

**Verifica.** Un test uguale ai due di §22.2 — un pacchetto con `created_at` a cavallo della mezzanotte UTC, e la data resa deve essere quella del giorno dopo. Poi la lista pacchetti nel pannello, confrontata con la lista clienti a fianco.
**Costo: 10 minuti** + 10 per il test.

---

### P2 · I log: identificativo nell'errore, email fuori dal successo

**Origine:** r3 §O10 e §1 · r2 §S12 — **due passate, sulla stessa coppia di righe, in direzioni opposte**
**File:** `backend/services/email_service.py:150-152,188-190,244,288,337` · `calendar_service.py:138` · `discord_service.py:51`
**Classe:** CONFERMATO

**Test 1 — danno concreto.** Scenario che accadrà: un cliente scrive *"ho prenotato e non ho ricevuto niente"*. Nei log trovi `ERROR ... Errore invio email` senza alcun modo di stabilire se sia la sua, né quante altre prenotazioni della stessa finestra siano rimaste senza email. È anche il complemento necessario di **R3**: senza identificativo, sapere che un invio è fallito non ti dice *quale*. E il buco GDPR è reale in un progetto che ha fatto una sessione dedicata: un cliente cancellato resta identificabile nei log di Railway.
**Test 2 — costo/beneficio.** Mezz'ora, cinque righe di log, contro l'unico strumento forense che hai alle 3 di notte. È il rapporto migliore del piano.
**Test 3 — regressione.** Zero: nessuna riga di logging influenza il comportamento.

**Intervento.** Nelle cinque coppie successo/errore, sostituire `{email_cliente}` con `booking_id=%s` e aggiungere lo stesso identificativo alle righe di `logger.exception`, incluse quelle di `calendar_service.py:138` e `discord_service.py:51`. **Non** il middleware con `contextvars` proposto da r3 come passo (b): quello è §B.1(a).

**Verifica.** Far fallire un invio in locale (integrazione spenta da **R4**) e leggere che la riga di errore nomini la prenotazione. Poi `grep -rn "email_cliente" backend/ | grep logger` deve essere vuoto.
**Costo: 30 minuti.**

---

### P3 · Il messaggio d'errore preciso non arriva mai al cliente

**Origine:** r1 §A12 (parte confermata; la parte sulla lingua è §A.3)
**File:** `frontend/js/app.js:518-545` — in particolare `:534`
**Classe:** CONFERMATO

`if (!bookingResponse.ok) throw new Error('Error creating booking')` finisce nel `catch` che mostra `t('generic_error')` [ricontrollato]. Messaggi scritti con cura lato server — *"Slot not available"*, *"You already have 2 active bookings"*, *"The following hour isn't available"* — non raggiungono mai nessuno. Nella stessa pagina, la cancellazione (`app.js:201`) il `detail` lo mostra: è un'incoerenza interna, non una convenzione.

**Test 1 — danno concreto.** Non serve un attaccante né un caso limite: è la **corsa ordinaria** del form. Due persone scelgono lo stesso slot a distanza di secondi, la seconda riceve un "errore generico", non capisce che deve solo sceglierne un altro, e con ogni probabilità scrive a te. Succede oggi.
**Test 2 — costo/beneficio.** Un quarto d'ora contro una prenotazione persa e un messaggio a cui rispondere.
**Test 3 — regressione.** Il frontend non ha test — è il rischio di questo intervento e va detto. Ma la superficie è **tre righe in un solo handler**, e il comportamento da replicare è già scritto venti righe più su nello stesso file.

**Intervento.** Nel ramo `!ok`, leggere il corpo (`await res.json().catch(() => ({}))`) e mostrare `errore.detail || t('generic_error')`, esattamente come fa `app.js:201`. **Non** i codici d'errore stabili con testo scelto dal frontend: quello è §B.1(a).

**Verifica.** A mano: due schede, la stessa prenotazione, la seconda deve leggere il messaggio del server invece di quello generico. Poi un `POST /bookings/` con uno slot già occupato, per controllare che il `detail` esca davvero dalla risposta.
**Costo: 15 minuti.**

---

### P4 · `date.today()` nel generatore di slot

**Origine:** r4 §M1 · **File:** `backend/services/availability_service.py:65` (confrontare con `:66` e `:93`)
**Classe:** DERIVA — la convenzione esiste, è documentata, e questa è l'unica riga del backend che la viola.

`timezone_service.py:45-52` dichiara nella docstring che `ora_utc_naive()` va usata *"al posto di `datetime.now()`"*. La riga 66 la usa correttamente; la 65 no. La stessa funzione prende quindi **i giorni dal fuso del processo (UTC) e gli orari da Roma** [ricontrollato].

**Test 1 — danno concreto.** Ristretto ma reale e silenzioso: una regola creata dal pannello fra mezzanotte e le 2 di notte del primo del mese genera **zero slot** e restituisce `slot_creati: 0` senza alcun errore. Il trigger è stretto; il modo di fallire è il peggiore possibile — nessun messaggio, nessun log, e il coach che rifà l'operazione ottenendo di nuovo zero.
**Test 2 — costo/beneficio.** Una riga. E chiude una deriva su una convenzione che il progetto dichiara e rispetta ovunque: lasciarla è lasciare l'unica eccezione a una regola, che è il modo in cui la regola smette di valere.
**Test 3 — regressione.** `genera_slot_da_regola` è coperta (`test_availability.py`, i test aggiunti in §19). La modifica sposta `oggi` di al massimo un giorno, nella direzione corretta.

**Intervento.** `oggi = utc_to_rome(ora_utc_naive()).date()`, più un test sul confine di mese.

**Verifica.** Il test nuovo con `ora_utc_naive` fissata al 30 settembre 22:30 UTC (= 1° ottobre 00:30 a Roma): deve generare gli slot di ottobre, non zero. Suite completa.
**Costo: 20 minuti.**

---

### P5 · Un a-capo nel nome sopprime la notifica al coach

**Origine:** r2 §S2 (riprodotto end-to-end dal revisore) · **File:** `backend/schemas/users.py:17` — effetto in `email_service.py:220-224`
**Classe:** CONFERMATO

Il nome finisce nell'**oggetto** dell'email al coach (`email_service.py:221`); Python rifiuta gli a-capo negli header con `ValueError`; quella `ValueError` finisce nel `try/except Exception` che la registra e prosegue. Risultato: prenotazione confermata, slot consumato, conferma al cliente partita, **avviso a te no**.

**Test 1 — danno concreto.** Esiste una prenotazione confermata sulla tua agenda di cui non sei stato avvisato. Non serve malizia: basta un incolla da un altro modulo. La notifica Discord arriva, quindi non resti del tutto cieco — ma il canale che ti aspetti fallisce in silenzio.
**Test 2 — costo/beneficio.** Un `Field` su un campo.
**Test 3 — regressione.** Un solo campo, un solo schema. Il vincolo (`max_length=100`) è già quello della colonna, quindi non rifiuta nulla che il database accetterebbe.

**Intervento.** `nome: str = Field(min_length=1, max_length=100, pattern=r"^[^\r\n]+$")`. **Solo questo campo.** L'estensione a tutti gli schemi (U17) resta fuori: dipende da `sql_mode` e tocca la validazione di ogni endpoint → §B.1(c).

**Verifica.** Un test: `POST /users/` con `"nome": "Mario\nBcc: x@y.z"` deve dare 422. E la suite, per controllare che nessun test esistente usi nomi più lunghi di 100 caratteri.
**Costo: 15 minuti.**

---

### P6 · Due credenziali vive e inutili nel `.env`

**Origine:** r2 §S10 · **File:** `.env` (non versionato) · **Classe:** CONFERMATO — configurazione morta

`SECRET_KEY` (il codice usa `JWT_SECRET`) e `EMAIL_APP_PASSWORD` (l'invio è passato all'API Gmail) non sono lette da nessuna riga del progetto. La seconda ha il formato di una **app password di Google**, che resta valida finché non la revochi a mano e concede l'invio di posta come te.

**Test 1 — danno concreto.** Nessun danno in corso: `.env` è in `.gitignore` e non è mai stato committato (verificato dal revisore con `git log --all -- .env`). Ma è **rischio puro senza contropartita** — la definizione di codice morto, applicata a una credenziale.
**Test 2 — costo/beneficio.** Dieci minuti, di cui nove sulla console Google.
**Test 3 — regressione.** Nulla la legge: rimuoverla non può rompere niente.

**Intervento.** Revocare la app password dall'account Google, cancellare le due righe da `.env`, e controllare che non siano in `.env.example` né su Railway.

**Verifica.** `grep -rn "SECRET_KEY\|EMAIL_APP_PASSWORD" backend/ scripts/ alembic/` deve restare vuoto (lo è già), e l'invio email va riprovato una volta dopo la revoca — usa l'OAuth, non la app password, ma è la prova che chiude il dubbio.
**Costo: 10 minuti.**

---

### P7 · `misfire_grace_time` sui job cron

**Origine:** r3 §O1 (solo la parte da cinque minuti) · **File:** `backend/scheduler.py:393-400,428-435`
**Classe:** CONFERMATO parziale

APScheduler usa `misfire_grace_time = 1` **secondo**: se allo scoccare dell'orario lo scheduler non è in condizione di partire — un deploy, un riavvio del container — l'esecuzione viene **saltata**, non rimandata.

**Test 1 — danno concreto.** Il backup della domenica alle 04:00 e la sonda credenziali delle 03:30 saltano se in quel minuto Railway riavvia. La finestra di perdita che hai accettato consapevolmente (7 giorni, `scheduler.py:420-424`) diventa 14 senza che nessuno lo sappia. Il trigger è raro; il costo del rimedio è un argomento con nome.
**Test 2 — costo/beneficio.** Un parametro. E fa esattamente ciò che vuoi: il job parte in ritardo invece di non partire.
**Test 3 — regressione.** `max_instances=1` e `coalesce=True` restano, quindi un ritardo non può produrre esecuzioni sovrapposte o accumulate.

**Intervento.** `misfire_grace_time=3600` sui job cron. **Non** l'allarme sulla freschezza dei backup (3h) → §B.1(d).

**Verifica.** `test_scheduler.py` già ispeziona i job registrati: un assert sul parametro.
**Costo: 5 minuti.**

---

## B.4 REFACTOR — cambi strutturali

Ordinati per rapporto beneficio/rischio. **R1 va fatto per primo comunque**: è l'unico che rende verificabili gli altri.

---

### R1 · Il banco di prova vede ciò che la produzione applica

**Origine:** r3 §O5 · r4 §M2, §M3, §4.3 · r1 §A8 · **e la voce 12 del tuo `§9.1`** — quattro passate indipendenti più il tuo stesso backlog
**File:** `tests/conftest.py:32-36,67,85-100` · nuovi test in `tests/test_booking.py`
**Classe:** CONFERMATO

Tre buchi con la stessa radice — la suite non esercita ciò che la produzione applica:
1. `PRAGMA foreign_keys` vale `0`: un `INSERT` di prenotazione con `user_id` inesistente passa. L'ordine di eliminazione in `elimina_cliente` (`clients.py:114-128`), che è la cancellazione GDPR, è **un vincolo reale in produzione e una formalità nei test**.
2. Le funzioni di notifica sono sostituite da `lambda **kwargs: None` e **nessuno verifica che siano chiamate**: r4 ha rimosso le tre notifiche e l'evento Calendar e la suite è rimasta a `146 passed`.
3. `MAX_PRENOTAZIONI_ATTIVE` non compare in nessun test: portato da 2 a 999, `146 passed`.

**Test 1 — danno concreto.** Non è danno in produzione: è che **la suite non può dirti se ce n'è**. E diventa immediato adesso, perché **P2, R3 e R4 di questo piano toccano tutti il percorso delle notifiche**: senza il punto 2, quegli interventi non sono verificabili. Il punto 3 difende l'unica protezione contro una persona che occupa da sola tutta l'agenda, in un'applicazione senza pagamento anticipato. Il punto 1 può rivelare oggi una violazione che i test accettano.
**Test 2 — costo/beneficio.** Due ore, ed è il moltiplicatore di tutto il resto del piano.
**Test 3 — regressione.** **Strutturalmente zero in produzione**: nessuna riga di `backend/` viene toccata. Il rischio massimo è che la suite diventi rossa — che è l'esito utile.

**Regola delle tre istanze.** L'unica astrazione nuova è il registratore delle notifiche, e ha tre casi d'uso reali già presenti: `booking.py`, `consulenza.py`, `pacchetti_richieste.py` patchano lo stesso ventaglio (`conftest.py:85-100`, undici `monkeypatch`). Se ne avesse due, andrebbe scritto in linea nei test invece che come fixture.

**Intervento.**
- `@event.listens_for(TEST_ENGINE, "connect")` che esegue `PRAGMA foreign_keys=ON` (4 righe);
- le `lambda **k: None` diventano `lambda **k: chiamate["<evento>"].append(k)`, con `chiamate` esposto come fixture, e un assert nel test principale della prenotazione;
- un test: due prenotazioni confermate future, la terza dà 400.

**Verifica.** La suite. Se resta a 146 verdi dopo la PRAGMA, hai imparato che l'ordine di eliminazione è corretto oggi; se diventa rossa, hai trovato un difetto che era coperto. Poi rifare a mano la mutazione di r4 — commentare le tre notifiche — e controllare che **adesso** la suite se ne accorga.
**Costo: 2 ore.**

---

### R2 · Uno slot bloccato deve poter tornare libero

**Origine:** r1 §A1 · r4 §M8 (l'asimmetria crea/elimina)
**File:** `backend/models/slots.py:27,33-34` · `backend/services/calendar_service.py:205,225-226` · `backend/services/availability_service.py:167-168` · `backend/routers/admin/availability.py:213-230` · `frontend/js/admin.js:844-863`
**Classe:** CONFERMATO

**[ricontrollato — è peggio di come è scritto nel report.]** Ho cercato tutte le scritture su quei campi in `backend/`: `blocked_external = True` solo in `calendar_service.py:226`, `blocked_admin = True` solo in `availability_service.py:168`, e **`blocked_external = False` / `blocked_admin = False` in nessun punto del progetto**. L'unica occorrenza della parola "sblocc" in tutto il codice è il docstring di `availability.py:221` che dice che vanno sbloccati a mano.

r1 presenta il trigger come la cancellazione di un blocco ferie. Ce n'è uno molto più ordinario: **metti un impegno personale sul tuo Google Calendar, la sincronizzazione blocca lo slot sovrapposto, poi togli l'impegno — e quello slot non torna mai prenotabile.** `sincronizza_slot_con_calendario` non lo rivede nemmeno, perché `calendar_service.py:205` filtra `is_available == True` e quello slot non lo è più. Nel pannello, per uno slot non disponibile la colonna Azioni mostra `—` (`admin.js:857-862`): non è né sbloccabile né eliminabile.

**Test 1 — danno concreto.** È l'**unico finding dell'audit in cui il prodotto è già rotto nell'uso ordinario**, e l'unica uscita è una `UPDATE` a mano sul MySQL di produzione. Ogni volta che usi il tuo calendario come un calendario, perdi disponibilità in modo permanente e silenzioso.
**Test 2 — costo/beneficio.** Due ore contro una perdita di prodotto che si accumula.
**Test 3 — regressione.** Media, e va detto: si tocca la tabella `slots`, che è quella che il claim atomico protegge. Ma l'intervento **aggiunge** un percorso invece di modificarne uno: le scritture esistenti restano identiche, e `elimina_blocco_eccezionale` è oggi una funzione che rimuove una riga e basta.

**Regola delle tre istanze — e perché rifiuto la cura di r1.** r1 propone un `services/slot_state.py` con `occupa` / `libera` / `blocca(motivo)` / `sblocca` come uniche scritture ammesse. I casi d'uso numericamente ci sono (quattro punti di scrittura), quindi la regola sarebbe soddisfatta — **ma l'intervento fallisce il test 3**: riscrivere i percorsi di scrittura della tabella più critica, incluso quello del claim atomico che nessun test esercita sotto concorrenza, per mezza giornata, in un progetto con un manutentore e nessuno staging. Una macchina a stati è la risposta giusta a un problema di squadra. Faccio **il percorso mancante, non il proprietario dello stato**.

**Intervento.**
- `PATCH /admin/slots/{id}/sblocca` che azzera `blocked_admin`, `blocked_external` e riporta `is_available = True` — solo se lo slot non ha una prenotazione attiva;
- il bottone corrispondente in `admin.js`, nella colonna Azioni oggi vuota per gli slot bloccati;
- `elimina_blocco_eccezionale` sblocca gli slot che aveva bloccato, chiudendo l'asimmetria che r4 §M8 segnala (crea genera, elimina no).

**Verifica.** Tre test: uno slot bloccato da admin torna prenotabile e ricompare in `GET /slots/`; uno slot bloccato da calendario idem; uno slot **prenotato** non è sbloccabile (400). Poi, in produzione, la query di conteggio della sezione finale prima e dopo.
**Costo: 2 ore.**

---

### R3 · `reminder_sent` deve registrare "è arrivata", non "ho provato"

**Origine:** r3 §O2 (riprodotto end-to-end) · r4 §5
**File:** `backend/scheduler.py:139-157,195-198` · `backend/services/email_service.py:148-152,186-190,335-339`
**Classe:** CONFERMATO

`invia_promemoria_cliente` cattura ogni eccezione e **non restituisce nulla**: il chiamante non può distinguere un invio riuscito da uno fallito, e scrive `reminder_sent = True` in entrambi i casi. La prenotazione esce per sempre dal filtro `Booking.reminder_sent == False`: **non sarà mai ritentata**. Il revisore l'ha riprodotto rendendo Gmail irraggiungibile: email non inviata, `reminder_sent` a `True`. Identico per `review_email_sent`.

**Test 1 — danno concreto.** Un 503 di Gmail che dura trenta secondi perde **ogni promemoria del lotto**, in silenzio e per sempre. Il cliente non riceve il promemoria, non si presenta, e tu registri un no-show senza alcun modo di collegarlo alla causa. Non è uno scenario d'attacco: è il comportamento ordinario di un servizio esterno.
**Test 2 — costo/beneficio.** Due ore contro sessioni perse che oggi sono indistinguibili da clienti inaffidabili.
**Test 3 — regressione.** Contenuta: il `try/except` che serve è già scritto (`email_service.py:148-152`), manca solo il valore di ritorno. Ma tocca il percorso delle notifiche, ed è **la ragione per cui R1 va fatto prima**: senza gli assert sulle chiamate, non hai modo di verificare di non aver rotto l'invio nel renderlo osservabile.

**Regola delle tre istanze.** Nessuna astrazione nuova: si aggiunge un `return True` / `return False` alle funzioni che già esistono.

**Intervento.** I mittenti restituiscono `bool`; `scheduler.py:156` e `:197` impostano il flag solo su `True`. **Non** i retry (§B.1(b)): prima misurare quanto spesso fallisce, e P2 è ciò che permette di contarlo.

**Verifica.** Il test di r3, reso permanente: Gmail mockato per sollevare, il job gira, e `reminder_sent` deve restare `False` così che il giro successivo riprovi. Più il caso positivo.
**Costo: 2 ore.**

---

### R4 · Importare un modulo non deve poter parlare con la produzione

**Origine:** r2 §S15 · r1 §A5 · **File:** `backend/services/email_service.py:81` · `discord_service.py:33` · `calendar_service.py:48` · `tests/conftest.py:85-100`
**Classe:** CONFERMATO

Cinque moduli chiamano `load_dotenv()` a livello di modulo: importarne uno qualsiasi legge il `.env` e popola le costanti con le credenziali reali. La difesa attuale sono undici `monkeypatch` in `conftest.py`, cioè **una difesa per enumerazione**: copre le funzioni note oggi, e il prossimo router che notifica riapre il buco in silenzio — il commento a `conftest.py:92-95` racconta esattamente questo, avvenuto una volta e chiuso perché qualcuno se n'era accorto.

**Test 1 — danno concreto.** **È l'unico finding dell'audit con un incidente già avvenuto**: uno script di verifica di questa stessa revisione ha raggiunto il Google Calendar di produzione (404, nessun dato toccato — con un id evento valido avrebbe cancellato un appuntamento vero). Il danno non è ipotetico, è documentato nel preambolo di r2.
**Test 2 — costo/beneficio.** Un'ora, in tre punti di uscita che **esistono già** e sono ben fatti.
**Test 3 — regressione.** È il rischio più alto del piano e va nominato: un errore qui spegne le notifiche **in produzione**. Si neutralizza scegliendo la direzione del guasto — il default è **acceso**, e si spegne solo in presenza di `PYTEST_CURRENT_TEST`. Un bug può solo fallire verso "le notifiche partono", cioè il comportamento di oggi.

**Regola delle tre istanze.** L'interruttore ha tre punti di consumo reali e già esistenti: `_invia_via_gmail`, `_invia_embed`, e il costruttore del servizio Calendar. Esattamente tre, non due.

**Intervento.** Una costante `INTEGRAZIONI_ATTIVE`, letta una volta, controllata nei tre punti unici di uscita, con default acceso e spegnimento automatico sotto pytest. **Non** il `notifiche_service` con un nome unico importato dai router (§B.1(a)).

**Verifica.** Rimuovere **una** delle undici righe di `monkeypatch` da `conftest.py` e controllare che la suite continui a non spedire nulla — è la prova che la difesa non è più per enumerazione. Poi, in locale con `.env` reale, `python -c "import backend.main"` non deve produrre traffico in uscita. Infine un invio vero dopo il deploy, per accertare che in produzione l'interruttore sia acceso.
**Costo: 1 ora.**

---

## Riepilogo

| | Voci | Costo |
|---|---|---|
| **B.2** Prerequisiti (nessun codice) | 5 verifiche | 30 min |
| **B.3** PULIZIA | 7 | ~1h45 |
| **B.4** REFACTOR | 4 | ~7h |
| **B.1** Non si tocca | 40 | — |

---

## Se dovessi fare una sola cosa

**R2 — l'endpoint di sblocco degli slot.**

Non è il finding più grave dell'audit: il BLOCCANTE è U14, e il più votato è U12 con quattro passate su quattro. Ma è **l'unico in cui il prodotto è già rotto adesso, nell'uso normale, per opera tua e non di un attaccante**. Tutti gli altri descrivono cosa succederebbe: se arrivasse traffico, se qualcuno attaccasse, se Google rallentasse, se aggiungessi un pacchetto. Questo descrive cosa succede quando usi il tuo calendario come un calendario.

E ha la proprietà che nessun altro ha: **il danno si accumula in silenzio**. Uno slot perso non dà errori, non compare nei log, non fa fallire un test. Semplicemente non viene più offerto ai clienti, e tu non hai modo di distinguere "quel giovedì non ho disponibilità" da "quel giovedì l'ho perso tre mesi fa e non me ne sono accorto".

Prima ancora di scrivere l'endpoint, esegui la query: se restituisce zero, hai due ore di lavoro preventivo e nessuna fretta. Se restituisce un numero, quel numero è disponibilità che stai già regalando.

```sql
SELECT COUNT(*) FROM slots
WHERE (blocked_external = 1 OR blocked_admin = 1) AND start_time > NOW();
```

*(Le trenta gratuite di §B.2 vengono prima di tutto, ma non sono "una cosa da fare": sono mezz'ora di lettura che decide se altri cinque finding esistono.)*
