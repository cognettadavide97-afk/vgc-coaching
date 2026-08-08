# ROADMAP — VGC Coaching App

> Da leggere insieme a `ANALYSIS.md`. Ogni step indica: cosa si costruisce, file coinvolti, come si verifica, da cosa dipende, stato. Stato aggiornabile a `in corso` / `fatto` man mano che si procede.

Legenda priorità:
- **P0 — Core funzionante**: minimo perché uno studente prenoti uno slot e il coach lo veda, correttamente e in sicurezza. Include i correttivi bloccanti emersi in Fase 2 (vanno prima di tutto il resto).
- **P1 — Integrazioni**: Discord, Google Calendar in lettura, email definitive.
- **P2 — Gestione**: mini-CRM, no-show, upload risorse, ricorrenza slot.
- **P3 — Rifiniture**: analytics, edge case, UI, Discord OAuth2.

---

## P0 — Core funzionante

### P0-1 — Rotazione credenziali database
**Cosa**: cambiare la password dell'utente MySQL `Desuzakiddo` sul server, dato che è esposta in chiaro nella storia git. Azione di infrastruttura, non di codice.
**File**: nessuno (azione esterna a questa sessione/repo).
**Verifica**: login al DB con la vecchia password fallisce; l'app funziona con la nuova password impostata solo via variabile d'ambiente.
**Dipende da**: nessuno — può partire subito, in parallelo a tutto il resto.
**Stato**: todo

### P0-2 — Rimuovere credenziali hardcoded dal codice
**Cosa**: eliminare il fallback con URL MySQL in chiaro; `DATABASE_URL` diventa obbligatoria (l'app deve fallire in modo esplicito all'avvio se manca, non silenziosamente).
**File**: `backend/database.py`, `alembic.ini` (rimuovere `sqlalchemy.url` in chiaro, lasciarlo popolato solo da `env.py` a runtime).
**Verifica**: avviare l'app senza `DATABASE_URL` nell'ambiente → errore chiaro all'avvio, non un fallback silenzioso a un DB sbagliato.
**Dipende da**: P0-1 (consigliato farlo dopo la rotazione, per non lasciare la vecchia password ancora valida visibile più a lungo del necessario).
**Stato**: fatto

### P0-3 — Rimuovere il flusso di pagamento e ridisegnare la conferma immediata
**Cosa**: eliminare il model `Payment`, l'endpoint `/config/paypal-email`, ogni riferimento a PayPal in email e frontend. La prenotazione passa a stato `confirmed` direttamente al submit (nessuno stato "in attesa di pagamento" iniziale).
**File**: `backend/models/payment.py` (rimuovere), `backend/models/booking.py` (colonna `calendar_event_id` resta, valutare se semplificare gli stati a `confirmed`/`cancelled`), `backend/routers/booking.py`, `backend/routers/admin.py`, `backend/services/email_service.py`, `backend/main.py`, `frontend/index.html`, `frontend/js/app.js`. Serve anche una migrazione Alembic per droppare la tabella `payments`.
**Verifica**: creare una prenotazione end-to-end → risulta subito `confirmed`, nessun testo/riferimento a PayPal in UI o email ricevuta.
**Dipende da**: nessuno.
**Stato**: fatto — 4/4 sotto-step completati: 1) rimosso model `Payment` + migrazione drop `payments`; 2) prenotazione nasce `confirmed`, stati ridotti a `confirmed`/`cancelled`, pannello admin ripulito dai residui "pending"; 3) `email_service.py` senza più riferimenti PayPal; 4) rimosso box PayPal e fetch `/config/paypal-email` dal frontend pubblico. Verificato end-to-end: prenotazione confermata subito, email ricevute senza menzioni pagamento, nessun riferimento PayPal in tutto il codebase.

### P0-4 — Spostare la creazione evento Google Calendar alla prenotazione, fix duplicazione
**Cosa**: dato che non c'è più un passaggio "admin conferma dopo pagamento", l'evento Calendar va creato direttamente in `create_booking`. Rimuovere la chiamata doppia debug rimasta in `aggiorna_stato`.
**File**: `backend/routers/booking.py`, `backend/routers/admin.py`, `backend/services/calendar_service.py`.
**Verifica**: una prenotazione crea esattamente **un** evento sul calendario Google (non due); cancellare la prenotazione dal pannello admin rimuove l'evento.
**Dipende da**: P0-3.
**Stato**: fatto — `create_booking` in `booking.py` ora crea l'evento Calendar direttamente alla prenotazione (salvandone l'id su `calendar_event_id`); rimossa da `admin.py` la chiamata doppia/debug in `aggiorna_stato` insieme a tutta la logica di creazione ormai spostata (resta solo la logica di cancellazione: elimina evento + riapre slot). Verificato end-to-end sul calendario Google reale del coach: una prenotazione crea esattamente 1 evento (confermato contando gli eventi nel calendario reale), la cancellazione lo rimuove, svuota `calendar_event_id` e riapre lo slot.

### P0-5 — Fix race condition su doppia prenotazione
**Cosa**: rendere atomico il "claim" dello slot — update condizionale (`UPDATE slots SET is_available=0 WHERE id=X AND is_available=1`, controllo rowcount) dentro la stessa transazione della creazione booking, oppure `SELECT ... FOR UPDATE`.
**File**: `backend/routers/booking.py`, eventualmente `backend/models/slots.py`.
**Verifica**: test con due richieste concorrenti sullo stesso `slot_id` (es. script con `asyncio`/thread paralleli) → una sola prenotazione creata, l'altra riceve 400 "Slot non disponibile".
**Dipende da**: nessuno (indipendente da P0-3/P0-4, può procedere in parallelo).
**Stato**: fatto — `create_booking` in `booking.py` ora fa un `UPDATE ... WHERE is_available=true` atomico (controllo `rowcount`) prima di creare la prenotazione, invece del pattern read-then-write. Verificato con 2 richieste realmente concorrenti (1 successo, 1 rifiutata) e con uno stress test a 10 richieste parallele sullo stesso slot (esattamente 1 prenotazione creata, 9 rifiutate con 400). Deciso con l'utente di non aggiungere un vincolo UNIQUE a schema, perché incompatibile con il flusso cancella/riprenota (uno slot cancellato torna disponibile per una nuova prenotazione).

### P0-6 — Fix gestione fusi orari
**Cosa**: salvare `start_time` in UTC nel DB; l'API deve restituire ISO8601 con offset esplicito (`Z`); il form admin di creazione slot deve trattare l'input come Europe/Rome e convertirlo in UTC prima di salvarlo; il frontend pubblico deve mostrare l'orario nel fuso locale del browser dello studente (via `Intl`/`toLocaleString` su una stringa con offset corretto, non su una naive).
**File**: `backend/models/slots.py`, `backend/schemas/slots.py`, `backend/routers/slots.py`, `frontend/js/app.js` (`formatDate`/`formatTime`), `frontend/admin.html` + `frontend/js/admin.js` (creazione slot).
**Verifica**: creare uno slot dall'admin alle "18:00" (fuso Europe/Rome); con il browser impostato su un fuso diverso (es. `America/New_York`, DevTools → sensors, o cambiando il fuso di sistema) l'orario mostrato nello step 1 del booking deve corrispondere correttamente (es. 12:00 se Roma è in CEST/UTC+2).
**Dipende da**: nessuno.
**Stato**: fatto — 4/4 sotto-step completati. 1) `models/slots.py` + `schemas/slots.py`: input admin interpretato come Europe/Rome e convertito in UTC prima del salvataggio (`zoneinfo`, nuova dipendenza `tzdata` aggiunta a `requirements.txt`), risposte API con offset UTC esplicito. 2) `admin.py` + `booking.py`: nuovo `backend/services/timezone_service.py` con `utc_to_rome()`, usato ovunque si formattava `start_time` per la visualizzazione (dashboard, lista prenotazioni, lista slot, export CSV, email); corretto anche il confronto `Slot.start_time >= datetime.now()` e il calcolo di "prenotazioni oggi" (confini del giorno in ora di Roma). 3) `formatDate`/`formatTime` in `app.js` non necessitavano modifiche — già corrette una volta sistemato il backend; verificato con DevTools Sensors (Roma → San Francisco, differenza di 9h confermata esatta con test reale dell'utente). 4) Nota esplicativa nel pannello admin ("orario sempre riferito al fuso italiano") accanto al form di creazione slot. Verificato end-to-end su server reale in tutti i sotto-step. **Nota**: gli slot creati prima di questo fix mostreranno ora un orario spostato dell'offset DST nel pannello admin, perché il valore naive salvato in precedenza andava interpretato come ora di Roma e ora viene invece letto come UTC — coerente con la decisione già presa che il progetto è in sviluppo/test e non ha dati reali da preservare (§5.3 di ANALYSIS.md).

### P0-7 — Fix migrazione `calendar_event_id`
**Cosa**: scrivere `upgrade()`/`downgrade()` reali nella migrazione `a4568987d2e7` (`op.add_column` / `op.drop_column`), così che uno schema creato da zero corrisponda al model.
**File**: `alembic/versions/a4568987d2e7_aggiungi_calendar_event_id_a_bookings.py`.
**Verifica**: su un DB MySQL vuoto, `alembic upgrade head` crea la colonna `calendar_event_id` su `bookings`; `alembic downgrade -1` la rimuove correttamente.
**Dipende da**: nessuno.
**Stato**: fatto — migrazione corretta con `op.add_column`/`op.drop_column` reali. Sul DB dev esistente (già avanzato oltre questa revisione in `alembic_version`) la colonna è stata aggiunta manualmente con lo stesso DDL, dato che rieseguire la migrazione da capo non era possibile senza droppare dati. Verificato: creazione prenotazione end-to-end ora riesce (prima falliva con `Unknown column 'calendar_event_id'`).

### P0-8 — Chiudere gli endpoint pubblici non protetti
**Cosa**: aggiungere `Depends(get_admin)` a `GET /users/`, `GET /bookings/`, `POST /slots/` (o rimuoverli/ridurne l'esposizione se non servono lato pubblico). Uniformare anche l'export CSV a usare `Depends(get_admin)` invece del controllo manuale via query param.
**File**: `backend/routers/users.py`, `backend/routers/booking.py`, `backend/routers/slots.py`, `backend/routers/admin.py` (export CSV).
**Verifica**: `GET /users/`, `GET /bookings/`, `POST /slots/` senza token → `401`; con token admin valido → funzionano come prima.
**Dipende da**: nessuno.
**Stato**: fatto — `Depends(get_admin)` aggiunto a `GET /users/`, `GET /bookings/`, `POST /slots/` (rimasti pubblici: `POST /users/`, `POST /bookings/`, `GET /slots/`, indispensabili al guest checkout). Export CSV uniformato a `Depends(get_admin)` al posto del token via query param; di conseguenza `exportCSV()` in `admin.js` ora scarica il file via `fetch()` con header Authorization invece di `window.open()` (che non può inviare header custom) — file non nell'elenco originale della roadmap, aggiunto dopo conferma esplicita. Verificato end-to-end: tutti gli endpoint protetti → 401 senza token, 200 con token valido; endpoint pubblici invariati.

### P0-9 — Menu servizi VGC (prezzo/durata fissi)
**Cosa**: aggiungere un campo `service_type` (VOD Review / Team Building / Bo3 Sparring / Mentality Prep) alla prenotazione. Prezzo e durata restano fissi e uguali per tutti i servizi (confermato) — quindi nessuna tabella `Services` dedicata, solo un enum/stringa + i valori fissi esistenti.
**File**: `backend/models/booking.py`, `backend/schemas/booking.py`, `backend/routers/booking.py`, `frontend/index.html` (aggiungere selezione servizio allo step 1 o 2), `frontend/js/app.js`.
**Verifica**: le 4 opzioni di servizio sono selezionabili nel form, il valore scelto è salvato e visibile nel pannello admin (lista prenotazioni).
**Dipende da**: P0-3 (stessa area di codice del booking form — evita di rifare il form due volte).
**Stato**: fatto — 2/2 sotto-step completati. 1) Campo `service_type` (`vod_review`/`team_building`/`bo3_sparring`/`mentality_prep`) su `models/booking.py`, validato con `Literal` in `schemas/booking.py`, salvato in `routers/booking.py`, migrazione con backfill per le righe esistenti. 2) Selettore servizio nello step 1 di `index.html`/`app.js` (stessa logica dei bottoni durata, CSS condiviso tra `.duration-btn`/`.service-btn`), riepilogo step 3 aggiornato; `admin.py` (lista prenotazioni + export CSV) e `admin.js` mostrano il servizio scelto. Verificato end-to-end su server reale: creazione, validazione (mancante/non ammesso → 422), visualizzazione in lista admin e CSV.

### P0-10 — Mitigazioni anti-abuso di base
**Cosa**: rate limiting per IP su `POST /bookings/` e `POST /users/` (es. libreria `slowapi`); limite di prenotazioni attive per email (es. max 2 booking `confirmed` con `start_time` futuro per stessa email).
**File**: `backend/routers/booking.py`, `backend/routers/users.py`, `requirements.txt` (nuova dipendenza rate-limiting).
**Verifica**: superare la soglia di richieste/minuto dallo stesso IP → `429`; tentare di creare una terza prenotazione attiva con la stessa email → rifiutata con messaggio chiaro.
**Dipende da**: P0-8 (chiudere prima gli endpoint pubblici riduce la superficie su cui applicare il rate limit).
**Stato**: fatto — aggiunta dipendenza `slowapi` (+ `limits`, `deprecated`, `packaging`, `wrapt`) a `requirements.txt`; nuovo `backend/rate_limit.py` con l'istanza condivisa del `Limiter`, registrata su `app` in `main.py`. Rate limit di 5/minuto per IP su `POST /users/` e `POST /bookings/`. Limite di 2 prenotazioni attive (`confirmed`, slot futuro) per utente in `create_booking`, controllato prima del claim dello slot. Verificato con richieste reali: 7 richieste consecutive su `POST /users/` → le prime 5 passano (200), le successive 2 → `429`; 3 tentativi di prenotazione con lo stesso utente → le prime 2 riescono, la terza → `400` con messaggio chiaro, e lo slot della terza resta libero (il controllo avviene prima di toccarlo).

---

## P1 — Integrazioni

### P1-1 — Campo Discord Tag testuale
**Cosa**: aggiungere un campo `discord_tag` al form di prenotazione, salvato su `User` (o `Booking`), visibile nel pannello admin. Nessun OAuth2 in questa fase (confermato).
**File**: `backend/models/users.py`, `backend/schemas/users.py`, `frontend/index.html`, `frontend/js/app.js`, `frontend/js/admin.js` (visualizzazione).
**Verifica**: il tag Discord inserito compare nella lista clienti/prenotazioni del pannello admin.
**Dipende da**: nessuno.
**Stato**: fatto — campo `discord_tag` su `User` (`models/users.py`, `schemas/users.py`, migrazione), input nel form pubblico (step 2 di `index.html`, inviato da `app.js`). Aggiunto anche a `admin.py` (`get_clienti`, `get_prenotazioni`) e `admin.js` (colonna "Discord" nella tabella clienti, riga extra nella cella cliente della tabella prenotazioni) — file fuori dall'elenco originale ma necessari per il criterio di verifica, stesso pattern delle volte precedenti. Verificato end-to-end: tag salvato alla creazione utente, visibile correttamente in entrambe le liste admin.

### P1-2 — Email definitive (senza PayPal, con contatti diretti)
**Cosa**: aggiornare `email_service.py` per rimuovere ogni residuo di pagamento e aggiungere link alla call e contatti diretti (Discord + Telegram).
**File**: `backend/services/email_service.py`.
**Verifica**: l'email di conferma ricevuta da un test booking contiene link/contatti corretti e zero menzioni di pagamento.
**Dipende da**: P0-3.
**Stato**: fatto — aggiunta sezione "Come contattarci" (Discord + Telegram) in `invia_conferma_cliente` (`email_service.py`), letta da due nuove variabili d'ambiente `COACH_DISCORD_TAG`/`COACH_TELEGRAM_CONTACT` (niente link a un server Discord dedicato, il coach opera 1:1 dal proprio profilo — deciso con l'utente). Creato anche `.env.example` (non esisteva ancora nel repo) allineato a tutte le chiavi attualmente usate, escluso `PAYPAL_EMAIL` ormai morto. Verificato con un'email reale ricevuta dall'utente: contenuto corretto, zero menzioni di pagamento.

### P1-3 — Webhook Discord per notifiche prenotazione
**Cosa**: creare un webhook Discord (azione esterna, da fare da zero come confermato) e un servizio che invia un messaggio al canale del coach a ogni nuova prenotazione.
**File**: nuovo `backend/services/discord_service.py`, `backend/routers/booking.py`.
**Verifica**: una nuova prenotazione produce un messaggio nel canale Discord configurato entro pochi secondi.
**Dipende da**: creazione del webhook Discord (azione utente, prerequisito esterno).
**Stato**: fatto — webhook creato dall'utente sul canale "Prenotazioni-Coaching", salvato come `DISCORD_WEBHOOK_URL` in `.env`/`.env.example`. Nuovo `backend/services/discord_service.py` (`invia_notifica_discord`, embed con cliente/tag Discord/servizio/data/ora/durata/note), chiamato da `create_booking` in `booking.py` insieme alle altre notifiche. Non blocca la prenotazione in caso di errore o webhook mancante. Verificato con una prenotazione reale: messaggio ricevuto correttamente sul canale Discord.

### P1-4 — Sync Google Calendar in lettura
**Cosa**: leggere periodicamente il calendario del coach; se esistono eventi esterni (tornei, stream) che si sovrappongono a uno slot libero, marcarlo non disponibile automaticamente.
**File**: `backend/services/calendar_service.py` (nuova funzione di lettura), nuovo endpoint/job di sync, `backend/models/slots.py`.
**Verifica**: creare manualmente un evento su Google Calendar che si sovrappone a uno slot libero → dopo il sync, lo slot risulta non disponibile nel booking pubblico.
**Dipende da**: P0-6 (fusi orari corretti — indispensabile per confrontare correttamente gli orari), P0-4.
**Stato**: fatto — trigger manuale (bottone "Sincronizza calendario" nel pannello admin), non automatico/periodico: introdurremo uno scheduler vero quando servirà per P2-3, invece di farlo due volte (deciso con l'utente). Nuova funzione `leggi_eventi_calendario()` in `calendar_service.py` (gestisce sia eventi con orario sia eventi "tutto il giorno"); nuovo campo `blocked_external` su `Slot` per distinguere nel pannello admin uno slot bloccato dal calendario da uno realmente prenotato; nuovo endpoint `POST /admin/slots/sync-calendario` che confronta gli slot liberi futuri con gli eventi e blocca quelli sovrapposti. Verificato end-to-end su calendario Google reale: creato un evento "Torneo TEST" sovrapposto a uno slot libero → dopo la sync lo slot risulta bloccato e sparisce dal booking pubblico; uno slot non sovrapposto resta libero (test negativo).

---

## P2 — Gestione

### P2-1 — Upload risorse pre-lezione
**Cosa**: permettere allo studente di allegare un link VOD o un codice replay Showdown alla prenotazione.
**File**: `backend/models/booking.py` (nuovo campo o tabella collegata), `backend/schemas/booking.py`, `frontend/index.html`, `frontend/js/app.js`.
**Verifica**: il link/codice inserito è visibile nel dettaglio prenotazione lato admin.
**Dipende da**: P0-9 (stessa area del form booking).
**Stato**: fatto — interpretato come da roadmap: due campi di testo (`vod_link`, `replay_code`), non un vero upload di file (nessun binario da gestire, quindi non si applica il vincolo tecnico su limite dimensione/whitelist formati/storage esterno, pensato per file veri). Aggiunti a `Booking` (model, schema, router, migrazione), input nel form pubblico (step 2). Visibili in una nuova colonna "Risorse" nella lista prenotazioni admin (`admin.py` + `admin.js`, fuori dall'elenco originale ma necessari per il criterio di verifica). Colto anche l'occasione per introdurre `escapeHtml()` in `admin.js` e applicarlo ai nuovi campi + a nome/email/discord cliente nella stessa tabella, evitando XSS via campi inseriti dal pubblico — la stessa lacuna resta però nelle altre tabelle admin (clienti, slot), non toccate in questo step. Verificato end-to-end, incluso un tentativo di iniezione `<script>` nel campo replay code: salvato correttamente lato backend (nessuna sanitizzazione necessaria in scrittura), reso innocuo lato rendering admin grazie all'escaping.

### P2-2 — Stato no-show
**Cosa**: aggiungere `no_show` come stato valido oltre a `confirmed`/`cancelled`, con azione dedicata nel pannello admin.
**File**: `backend/routers/admin.py` (`stati_validi`), `backend/models/booking.py` (se si formalizza come enum), `frontend/js/admin.js`.
**Verifica**: una prenotazione passata può essere marcata `no_show` dal pannello admin e appare correttamente nella lista/filtro.
**Dipende da**: P0-3.
**Stato**: fatto — `no_show` aggiunto a `stati_validi` in `admin.py` (nessun effetto su calendario/slot, a differenza di `cancelled`: la sessione è già passata, non ha senso liberare lo slot né cancellare l'evento). Bottone "🚫 No-show" dedicato in `admin.js` (visibile solo per prenotazioni `confirmed`, insieme a "Cancella"), badge grigio distinto, opzione nel filtro stato in `admin.html`. Verificato end-to-end: stato non valido → 400; transizione a `no_show` → 200, compare correttamente nel filtro; calendar_event_id e slot restano invariati come da comportamento voluto.

### P2-3 — Promemoria automatici pre-sessione
**Cosa**: job schedulato (cron o task periodico) che invia un promemoria email/Discord un tot di tempo prima della sessione.
**File**: nuovo modulo scheduler, `backend/services/email_service.py`, `backend/services/discord_service.py`.
**Verifica**: una prenotazione con orario nel prossimo futuro genera un promemoria all'orario atteso (verificabile con uno slot di test a pochi minuti di distanza).
**Dipende da**: P1-2, P1-3, P0-6 (i promemoria devono scattare nel fuso corretto).
**Stato**: fatto — nuova dipendenza `apscheduler`, nuovo modulo `backend/scheduler.py` con `BackgroundScheduler` avviato da `main.py`, job periodico (`REMINDER_CHECK_INTERVAL_MINUTES`, default 5 min) che cerca prenotazioni confermate non ancora avvisate con slot entro `REMINDER_HOURS_BEFORE` ore (default 24, entrambe configurabili via env, non hardcoded). Nuovo campo `reminder_sent` su `Booking` per evitare invii duplicati. Nuove funzioni `invia_promemoria_cliente` (email) e `invia_promemoria_discord` (avviso al coach). Verificato: prenotazione con slot a 10 minuti → promemoria inviato (email accettata da SendGrid, notifica Discord ricevuta) e marcato come inviato; prenotazione con slot a 40 giorni → nessun promemoria (fuori dalla finestra); richiamando la funzione una seconda volta → 0 invii (idempotenza, nessun doppio promemoria); server verificato stabile con lo scheduler attivo.

### P2-4 — Mini-CRM esteso
**Cosa**: storico interazioni/note più strutturato oltre al singolo campo `note_admin` libero attuale.
**File**: eventuale nuova tabella `client_notes` o simile, `backend/routers/admin.py`, `frontend/js/admin.js`.
**Verifica**: è possibile aggiungere più note nel tempo per lo stesso cliente e vederle in ordine cronologico.
**Dipende da**: nessuno.
**Stato**: fatto — nuova tabella `client_notes` (model, schema, migrazione) collegata a `User`, separata dal `note_admin` esistente (quello resta per-prenotazione, questo è per-cliente e si accumula nel tempo). Nuovi endpoint `GET`/`POST /admin/clienti/{user_id}/note`. Pannello admin: bottone "📋 Note (N)" per cliente che apre un modale con lo storico in ordine cronologico e un campo per aggiungerne di nuove, aggiornamento in tempo reale del conteggio. Verificato end-to-end: note salvate e restituite in ordine cronologico corretto, nota vuota → 400, cliente inesistente → 404, endpoint protetto da admin, conteggio note corretto nella lista clienti.

### P2-5 — Orari ricorrenti + blocchi eccezionali
**Cosa**: permettere all'admin di definire una disponibilità ricorrente (es. "ogni martedì 18-20") invece di creare ogni slot singolarmente, più la possibilità di bloccare eccezioni.
**File**: `backend/models/slots.py` (o nuovo model di regola ricorrente + generazione slot), `backend/routers/slots.py`, `frontend/admin.html`/`admin.js`.
**Verifica**: definire una regola ricorrente genera automaticamente gli slot futuri corrispondenti; un blocco eccezionale rimuove/nasconde gli slot nel periodo indicato.
**Dipende da**: P0-6 (fusi orari).
**Stato**: fatto — due nuove tabelle: `availability_rules` (regola ricorrente: giorno settimana, ora inizio/fine in ora italiana, durata slot) e `availability_exceptions` (blocco eccezionale: intervallo date + motivo), nuovo `blocked_admin` su `Slot` per distinguerlo da `blocked_external` (calendario). Nuovo `backend/services/availability_service.py` con la logica di generazione (8 settimane in avanti, idempotente — salta orari passati e slot già esistenti) e di applicazione blocco (marca non disponibili solo gli slot liberi nel periodo, non tocca quelli già prenotati). Endpoint CRUD sotto `/admin/disponibilita/...` (in `admin.py`, non `slots.py` come da elenco roadmap originale — stessa scelta di P1-4, azione admin-only). UI nel pannello Slot: form regola ricorrente + lista con eliminazione, form blocco eccezionale + lista con eliminazione, terzo badge "Bloccato (ferie)" distinto da "Bloccato (calendario)". Verificato end-to-end in modo estensivo: regola "ogni martedì 18-20, slot 1h" → 16 slot generati su 8 settimane, tutti negli orari/giorni corretti; rieseguendo la generazione sulla stessa regola → 0 duplicati; blocco eccezionale su un intervallo → bloccati esattamente i 4 slot nel periodo, gli altri 12 invariati; slot bloccati spariscono da `/slots/` pubblico; validazione su range orari/date invertiti → 400; eliminazione regola/blocco → 200, non tocca gli slot già generati.

---

## P3 — Rifiniture

### P3-1 — Discord OAuth2 login opzionale studenti
**Cosa**: aggiungere login opzionale via Discord OAuth2, rimandato rispetto al semplice campo testuale di P1-1 (confermato).
**File**: nuovo flusso OAuth2 backend, `frontend/index.html`/`app.js`.
**Dipende da**: P1-1, creazione dell'app OAuth2 su Discord Developer Portal (azione esterna).
**Stato**: fatto — app OAuth2 creata dall'utente sul Discord Developer Portal, credenziali in `.env`/`.env.example` (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_OAUTH_REDIRECT_URI`). Nuovo campo `discord_id` su `User` (id Discord permanente, distinto dal `discord_tag` testuale di P1-1). Nuovo router `backend/routers/discord_auth.py` (`GET /auth/discord/login` → redirect a Discord, `GET /auth/discord/callback` → scambia il code, trova/crea l'utente per `discord_id` poi per email, emette un token studente). **Importante per la sicurezza**: `auth_service.py` ora distingue token admin e token studente con un claim `"type"` — senza questo, un token studente avrebbe potuto essere usato per accedere al pannello admin; verificato esplicitamente che non sia così (e viceversa). Nuovi endpoint `GET /users/me` e `GET /users/me/prenotazioni` protetti dal token studente. Frontend: bottone "Accedi con Discord (opzionale)" in `index.html`/`app.js`, precompila nome/email/showdown/discord tag, mostra storico prenotazioni, sempre facoltativo (guest checkout invariato). Verificato via API: redirect OAuth corretto, login admin non compromesso (test di regressione), separazione dei token verificata in entrambe le direzioni, storico prenotazioni funzionante. **Il flusso completo di consenso Discord non è testabile da me** (richiede l'interazione reale dell'utente nella schermata di autorizzazione Discord) — verifica manuale richiesta.

### P3-2 — Dashboard analytics avanzata
**Cosa**: grafici/trend oltre ai 3 numeri attuali (es. andamento prenotazioni nel tempo, servizi più richiesti).
**File**: `backend/routers/admin.py`, `frontend/js/admin.js`.
**Dipende da**: P0-9 (serve `service_type` per analizzare i servizi più richiesti).
**Stato**: fatto — nuovo endpoint `GET /admin/analytics`: sessioni e incasso per mese (ultimi 6 mesi, calendario italiano, calcolato in Python sui valori già convertiti in ora di Roma — non in SQL, per evitare errori di fuso sui confini di mese), servizi più richiesti, tasso di no-show (`no_show / (confirmed passate + no_show)`), clienti nuovi vs ricorrenti. Niente librerie di charting (coerente con "niente grafici decorativi" delle specifiche e con l'assenza di bundler nel progetto): barre proporzionali fatte con semplice CSS/JS in `admin.js`/`admin.css`, aggiunte alla sezione Dashboard esistente. Verificato end-to-end: i numeri restituiti dall'endpoint incrociano esattamente con query dirette sul database (totale prenotazioni, distribuzione per stato, clienti nuovi/ricorrenti).

### P3-3 — Paginazione liste admin + fix N+1 clienti
**Cosa**: paginare `GET /admin/prenotazioni`, `GET /admin/clienti`, `GET /admin/slots`; sostituire il loop N+1 in `get_clienti` con un'unica query aggregata (`GROUP BY`).
**File**: `backend/routers/admin.py`, `frontend/js/admin.js`.
**Dipende da**: nessuno.
**Stato**: fatto — i tre endpoint accettano `pagina`/`per_pagina` (default 20, max 100) e restituiscono `{items, totale, pagina, per_pagina, pagine_totali}`. `get_clienti` non fa più 2-3 query per cliente in un ciclo Python (era diventato N+1 triplo dopo P1-1/P2-4): ora un'unica query `GROUP BY` per sessioni+incasso e una per il conteggio note, indipendentemente dal numero di clienti. Frontend: helper `renderPaginazione()` condiviso, controlli Precedente/Successiva sotto ciascuna tabella; stato della pagina corrente tracciato per evitare che le azioni (nota, cambio stato, elimina, sync...) riportino sempre a pagina 1. Export CSV lasciato non paginato di proposito (deve restare un export completo). Verificato end-to-end: paginazione con offset corretto (pagine diverse → id diversi), clamp `per_pagina` a 100, numeri del fix N+1 verificati identici a query dirette sul database (17 sessioni, €665 per il cliente di test).

### P3-4 — Pulizia configurazione
**Cosa**: restringere CORS all'origine reale del frontend invece di `"*"`; consolidare `nixpacks.toml`/`procfile` in un'unica fonte di verità per il comando di avvio.
**File**: `backend/main.py`, `nixpacks.toml`, `procfile`.
**Dipende da**: nessuno.
**Stato**: fatto — CORS ristretto a origini esplicite via nuova variabile `FRONTEND_ORIGINS` (comma-separated, default locale `127.0.0.1:8000,localhost:8000`), invece di `allow_origins=["*"]`; ristretti anche `allow_methods`/`allow_headers` (erano `"*"` pure quelli, stesso problema segnalato in ANALYSIS.md). `procfile` rimosso: duplicava esattamente lo stesso comando di avvio già in `nixpacks.toml`, che resta l'unica fonte di verità dato che Railway usa Nixpacks come builder (nessun `railway.json` che dica diversamente). Verificato: richiesta preflight da origine consentita → header CORS presente; da origine non consentita (simulato un dominio esterno) → header assente, quindi bloccata dal browser; nessuna regressione sulle funzionalità esistenti.

### P3-5 — Validazione durata booking vs slot / overlap check
**Cosa**: validare che `booking.duration_hours` sia compatibile con `slot.duration_hours`; controllare sovrapposizioni tra slot adiacenti.
**File**: `backend/routers/booking.py`, `backend/models/slots.py`.
**Dipende da**: P0-5 (stessa area di codice, atomicità del claim).
**Stato**: fatto — `create_booking` ora rifiuta (400) se `booking.duration_hours` non coincide con `slot.duration_hours`. Per evitare che questo rompesse il flusso reale (il selettore "Durata sessione" era indipendente dagli slot mostrati, quindi il mismatch era facile da ottenere per un utente reale), `app.js` ora filtra gli slot mostrati in base alla durata selezionata — non è più possibile arrivare a un mismatch dall'interfaccia normale.

Controllo sovrapposizione: nuovo `slot_si_sovrappone()` in `availability_service.py` (non `models/slots.py` come da elenco roadmap originale — un modello SQLAlchemy non è il posto giusto per questa logica; segnalato per coerenza con le deviazioni precedenti). Il claim atomico di P0-5 impedisce solo la doppia prenotazione dello *stesso* slot, non di due slot diversi che si sovrappongono nel tempo: usato sia in `POST /slots/` (rifiuta con 400 la creazione manuale di uno slot sovrapposto) sia in `genera_slot_da_regola` (salta silenziosamente le occorrenze che si sovrapporrebbero, senza far fallire l'intera generazione). Verificato end-to-end: mismatch durata → 400, match corretto → prenotazione creata; creazione slot sovrapposto → 400, slot adiacente che tocca il bordo esatto → consentito (nessun falso positivo), slot chiaramente separato → consentito; generazione da regola con uno slot manuale preesistente nel mezzo → le occorrenze sovrapposte vengono saltate correttamente, le altre create normalmente.

---

## Note per chi riprende il lavoro

- Il progetto è ancora in fase di sviluppo/test: nessun dato reale da preservare, i P0 possono includere modifiche di schema senza preoccuparsi di migrazioni "a caldo" su produzione.
- Priorità assoluta prima di scrivere qualsiasi altra riga: **P0-1** (rotazione credenziali) — è un'azione dell'utente, indipendente dal resto, e non ha senso rimandarla.
- Tutti i P0 sono considerati bloccanti per il resto della roadmap: senza conferma immediata, fusi orari corretti e claim atomico dello slot, ogni integrazione costruita sopra (Discord, Calendar in lettura, promemoria) erediterebbe gli stessi bug.
