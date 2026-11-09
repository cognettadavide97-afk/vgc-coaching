# ANALISI 2026-11 — stato del progetto e potatura

2026-11-09 · analisi in sola lettura sul commit `55185d0` (unico file fuori da git: `POTATURA.md`).
Documento storico: si scrive una volta e non si aggiorna. Le voci di `PIANO.md` dalla 46 in poi rimandano qui.

**Metodo.** Cinque pezzi, ogni affermazione con `file:riga`, commit o comando:
A — documenti eliminati operativi; B — documenti eliminati di revisione e audit; C — coerenza fra `PIANO.md`,
`PIANO_ANALISI_2026-09.md`, `PROBLEMI.md`, `DRIFT.md`, `POTATURA.md` e codice; D — codice e configurazione;
E — documenti vivi, memoria, git, materiale fuori dal repository.
**Fonti eliminate.** `c8fc0ca` (2026-09-11) ha cancellato `_archivio_docs/`: si legge con
`git show 2f912d2:_archivio_docs/<file>` ed esiste identico byte per byte in `VGC/_archivio_docs/`.
Sigle: RD README.md · SP STATO_PROGETTO.md · RR RAILWAY_RIALLINEAMENTO_2026-09-02.md · RM ROADMAP.md ·
CS CODICE_SPIEGATO.md · r1-r4 audit/r1..r4 · PI audit/piano-interventi.md · REV REVISIONE_2026-09-01.md.
**Effetti esterni.** Nulla modificato. Letture con `gh` (deployments, workflow, run). Il pezzo A ha eseguito le
tre sonde di `scheduler.py` (scambio refresh token → access token, nessuna scrittura) con il `.env` locale.
**Dopo l'analisi.** L'utente ha archiviato a mano `PROTOCOLLO.md` e `PROMPT.txt` e tolto la nota sugli agenti
(`9b15154`): le proposte del §5 su quei file sono superate. La sessione di recupero e scarto che segue non tocca il
codice: le proposte su commenti, `.env.example`, `requirements.txt`, `alembic/README` e `.gitignore` passano alle
voci 29 e 54 di `PIANO.md`.

## 1. In breve

- Codice sano: 198 test verdi, copertura 91% (`pytest -q`, 26 s). Le voci NON TOCCARE di `CLAUDE.md` sono vere.
- Produzione ferma a `b348c30` (2026-09-16). Ogni push su master fa deploy su Railway (verificato): gli 11 commit
  locali, con i fix R17 (`aee536b`), R5 (`90062f9`), R7 (`132a5a2`), sono spuntati in `PIANO.md` ma non online.
- Il monitor GitHub è attivo ma gira ogni ~5 h, non ogni 15 min, e si spegne da solo intorno al 2026-11-15.
- `PIANO.md`: 35 voci aperte (non 31). Quattro premesse false (11, 13, 19, 41), una voce più larga del descritto (9),
  undici voci senza effetti, sei accorpabili. Sette difetti reali non sono tracciati da nessuna parte.
- Nulla è perso in modo irreversibile, ma un terzo del materiale didattico e una dozzina di fatti operativi
  esistono solo nella storia git e in `VGC/_archivio_docs/`.

## 2. Scadenze e operatività

**2.1 Monitor, regola dei 60 giorni.** Repo pubblico, `pushed_at` 2026-09-16T11:02:42Z (`gh api`): GitHub spegne
i workflow schedulati dopo 60 giorni senza attività, cioè intorno al 2026-11-15. Si riattiva da Actions → Enable
workflow; SP:1492-1515 sconsiglia i commit finti. Se il repo diventasse privato, 96 esecuzioni al giorno
sforerebbero i 2000 minuti gratuiti (SP:1429-1431). Oggi nessun file lo dice (grep "60 giorni" vuoto).
Cadenza reale: mediana 4,9 h fra un run e l'altro (min 1,9, max 10) contro `*/15`; `monitor.yml:18-22` parla di
"qualche minuto" di ritardo e `AUDIT.md:559` di "ogni 15 minuti". Ultimi 300 run: nessun fallimento.

**2.2 Push = deploy.** `gh api repos/cognettadavide97-afk/vgc-coaching/deployments`: un deployment
"vigilant-bravery / production" per ogni push (`b348c30`, `ca90771`, `8b7364d`, `8e654c9`), ultimo `success`
2026-09-16T11:03:38Z. `PROTOCOLLO.md:139` lo dà per incerto ("potrebbe"); la procedura stava in SP:452-461.
Il primo push porterà online i tre fix, mai passati dalla CI (ultimo run di `tests.yml`: 2026-09-16, `b348c30`).

**2.3 Railway, topologia delle variabili** (RR:40-46, RR:178-210, SP:341-344, REV fase 4b). Due servizi, app e
MySQL. Undici variabili applicative vivono sul servizio MySQL e l'app le legge con `${{MySQL.NOME}}` (13
riferimenti): ADMIN_USERNAME, DATABASE_URL, EMAIL_ADMIN, EMAIL_MITTENTE, GMAIL_CLIENT_ID, GOOGLE_CALENDAR_ID,
GOOGLE_PRIVATE_KEY, GOOGLE_SERVICE_ACCOUNT_EMAIL, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET. Chi ruota
JWT_SECRET o GOOGLE_PRIVATE_KEY le modifica sul servizio MySQL. Le `MYSQL*` non si toccano (le legge il
container). Ogni salvataggio di variabili riavvia il servizio e ogni avvio esegue le migrazioni (RR:64-77).
Contraddizione da sciogliere sulla dashboard: RR:171 ha tolto dal servizio MySQL la copia di
GMAIL_REFRESH_TOKEN ("trappola"), mentre SP:1027-1029, `scheduler.py:77,85` e la memoria dicono di aggiornare i
token "su entrambi i servizi". Oggi `AUDIT.md` §6 punto 6 dichiara la piattaforma "non determinabile".

**2.4 Railway, pulizia mai fatta.** Consolidare le variabili sul solo servizio app (SP:470, RR:291-309);
togliere GMAIL_HEALTHCHECK_INTERVAL_HOURS dai due servizi (SP:1349-1350; il codice non la legge più);
controllare che PUBLIC_BASE_URL abbia `https://` (link di recensione cliccabile, SP:465, RR:279-287, PI U9);
decidere su `MYSQL_PUBLIC_URL`, proxy TCP pubblico al database con la password root, "da valutare" e mai deciso.

**2.5 Misure gratuite in produzione** (PI §B.2), oggi la 40 ne copre una: IP visto dietro il proxy (vedi N3),
`@@time_zone` e `NOW()` (`created_at` usa `func.now()` in tutti gli 8 model, es. `models/booking.py:55`),
collation, `@@sql_mode` (vedi N4), healthcheck e numero di repliche (job duplicati, stato per processo a
`scheduler.py:53`).

**2.6 Token Google.** Verifica del 2026-09-11 mai registrata; eseguita il 2026-11-09 dal pezzo A: Gmail, Drive e
Calendar OK a 66 giorni dalla rigenerazione (in "Testing" sarebbero scaduti dopo 7). La pubblicazione della
schermata di consenso ha funzionato. Riserva: che il token locale coincida con quello di Railway non è verificato.

**2.7 Credenziali morte nel `.env` locale.** `EMAIL_APP_PASSWORD` (password per app Gmail del tentativo SMTP,
`0ca51c9`, abbandonato con `7a1d1cf` il 2026-08-18) e `SECRET_KEY` (vecchio nome di `JWT_SECRET`,
`auth_service.py:19`): nessun `getenv` le legge. Una password per app resta valida finché non la si revoca
nell'account Google (stato non verificato). Le variabili del codice (31) e di `.env.example` (31) coincidono.

**2.8 Backup.** Ripristino mai provato (RD:382-389; i test controllano solo la forma del dump con un engine finto,
`test_percorsi_critici_uscita.py:386-425`; `crea_dump_sql` mai eseguito, `test_backup_service.py:5,31`). È l'unica
copia dei dati: il piano Hobby non ha backup né PITR (`backup_service.py:3-6`). Il job settimanale
(`scheduler.py:429-436`) ha `misfire_grace_time=1` e jobstore in memoria: un ritardo oltre 1 s salta
l'esecuzione e un riavvio a cavallo della domenica alle 04:00 UTC la rimanda di una settimana; l'allarme scatta
solo se il job parte e fallisce (`scheduler.py:334-341`).

## 3. Difetti reali non tracciati in PIANO.md (candidati 46+)

**N1 — Cache del browser su tutti gli asset.** Nessun URL versionato (`admin.html:303`, `index.html:444-445`,
`about.html:109-110`, `recensione.html:59`, tutti i `<link>` CSS) e `StaticFiles` senza `cache-control`
(`main.py:162`). Dopo un rilascio coach e clienti possono eseguire JS vecchio contro il backend nuovo. Noto solo
alla memoria `project_cache_asset_statici_pannello` (2026-09-16); ogni "cache" nei documenti è la cache OAuth R17.

**N2 — Job schedulati che falliscono o saltano senza avviso.** `genera_slot_giornaliero` (`scheduler.py:219-236`),
pulizia slot (`:239-249`) e anonimizzazione (`:304-325`) usano `try/finally` senza `except`: nessun avviso
Discord. Se fallisce il primo il calendario smette di riempirsi. È la metà "silenziosa" di R16
(`PROBLEMI.md:528-530`), che la 10 non copre. Stesso tema per il backup saltato (2.8).

**N3 — Rate limit probabilmente globale dietro il proxy** (r2 S5, PI U15). `rate_limit.py:12` usa
`get_remote_address`; `nixpacks.toml:5` avvia uvicorn senza `--forwarded-allow-ips`; il default di uvicorn è
`127.0.0.1` (`venv/.../uvicorn/config.py:344`). Se il proxy di Railway non è 127.0.0.1, tutti condividono un
contatore e `rate_limit.py:10-11` ("vale per chiamante, non globalmente") è falso. Effetto: chiunque, anche un bot,
con 5 richieste al minuto blocca per tutti login admin, prenotazioni, consulenze, richieste pacchetto (429).
Da verificare negli access log di Railway; si corregge con `FORWARDED_ALLOW_IPS` sull'intervallo del proxy, mai `*`.

**N4 — Input pubblici non limitati** (A O6; r2 S2, S4, S7; PI U17, U32). Nessun `max_length` in `backend/schemas/`
(solo il voto, `review.py:10`) contro colonne a lunghezza fissa (`models/users.py:12-30`,
`models/booking.py:41-42`). Con MySQL in modalità strict un input troppo lungo fallisce all'INSERT dopo che
l'evento Calendar è già stato creato (`booking.py:213` prima di `:245`): 500 ed evento orfano; SQLite lo accetta,
la suite non lo vede. Un a-capo nel nome (`schemas/users.py:17`) finisce nell'oggetto dell'email al coach
(`email_service.py:221`): `ValueError` catturato a `:223-224`, l'email non parte e Discord sì. Un token di
recensione non ASCII fa sollevare `TypeError` a `compare_digest` (`review.py:9`): 500 su `booking.py:354`
(riprodotto). Markdown non neutralizzato negli embed Discord (`discord_service.py:72-78`, r2 S8).

**N5 — Email dei clienti nei log** (r2 S12, r3 O10, PI U04). Successi loggati con l'email
(`email_service.py:150,188,244,288,337`); errori senza identificativo (`:152,190,224,246,268,290,313,339`,
`calendar_service.py:139,188,271,274`, `discord_service.py:51`). Un cliente cancellato su richiesta
(`privacy.html:83`) resta identificabile nei log di Railway; davanti a "non mi è arrivata l'email" il log non dice
quale prenotazione. Cura: `booking_id=` al posto dell'email (~30 minuti).

**N6 — Isolamento dei test.** `load_dotenv()` carica il `.env` vero all'import in sei moduli (`database.py:13`,
`auth_service.py:17`, `backup_service.py:30`, `calendar_service.py:24`, `email_service.py:21`,
`discord_service.py:16`) e la fixture `integrazioni_esterne_finte` sostituisce i nomi solo nei tre router pubblici
(`conftest.py:107-122`). Restano fuori `elimina_evento_calendario` (`booking_service.py:28`) e lo sync admin
(`admin/availability.py:72`). Oggi nessuna chiamata reale parte; un test futuro che non sostituisca
`get_calendar_service` chiamerebbe Google Calendar con le credenziali del `.env`. È già successo una volta (r2 S15).

**N7 — Rimandi a documenti cancellati e commenti stantii.** Il tree vivo cita file che esistono solo nella storia:
`.env.example:19,86`; `scripts/reauth_gmail.py:21,50,62`, `reauth_drive.py:55`; `frontend/css/style.css:74`;
`tests/test_avvio.py:5`, `test_auth.py:2`, `test_admin.py:112,161,226,280`, `test_slots.py:28`,
`test_booking.py:210,235,471-472`, `test_users.py:3-4` ("la checklist di sicurezza del progetto", vedi 6.1 O9).
Commenti falsi non censiti in C4: `backup_service.py:1` "Backup giornaliero" (è settimanale,
`scheduler.py:421-436`); `reauth_drive.py:15-18` "nessun controllo schedulato" (falso da `37f1abf`,
`scheduler.py:71-81`); `reauth_gmail.py:19-21` (verifica ora fatta, 2.6); `monitor.yml:18-22` (2.1).

## 4. Correzioni al piano

**Copertura.** Ogni codice di `PROBLEMI.md` e di `DRIFT.md` ha una voce o una chiusura dichiarata
(B1→2, B2→4-5, B3→3, R1+R2→14, R3→24, R4→11-12, R5→7, R6→9, R7→8, R8→25, R9→22, R10→23, R11→13, R12→18,
R13→19, R14→20, R15→26, R16→10, R17→6, C1→30/31/32/36, C2→27, C3→28, C4→29+35, C5→33, C6→34, D1→15, D2→16,
D3→17; DRIFT §1→36, §6→38, §2-5 e §7-9 chiuse a PIANO_ANALISI:1359-1365). Senza destinazione: la metà silenziosa
di R16 (N2), la variante di R6 sul dominio (sotto, 9), la cache degli asset (N1).

**Riferimenti.** Le righe 152, 347, 352, 723, 845, 1328 sono giuste; la 88 è sbagliata (il 29/35 sta alla 89).
I rimandi di `CLAUDE.md` agli interventi tornano. `CLAUDE.md` cita `scheduler.py:35-47`, ma
`BackgroundScheduler()` sta a `:351`. Voci chiuse: hash e contenuti tornano; `dab88f5` ("punto 3") e `aee536b`
(messaggio di B1) contengono davvero il 4 e il 6, come attribuito (spiegato solo a PIANO_ANALISI:64-73 e in
`3fd9f9d`).

**Premesse false.**
- 11 — il timeout c'è: `googleapiclient` crea `httplib2.Http(timeout=60)` (`http.py:75,1944-1948`, via
  `_auth.authorized_http`; a runtime `http.timeout == 60`); nessun `setdefaulttimeout` nel progetto; r3 §2 l'aveva
  misurato. Il rischio resta ma è un altro: l'UPDATE di `booking.py:178` tiene il lock fino al commit di `:245`, in
  mezzo c'è `crea_evento_calendario` (`:213`), e 60 s superano i 50 s di `innodb_lock_wait_timeout`: chi prenota
  lo stesso slot in quel momento riceve 1205, cioè un 500. Falsi anche `CLAUDE.md:40` ("senza timeout"),
  `PROBLEMI.md:217`, PIANO_ANALISI:763, `POTATURA.md:3` ("attesa senza fine").
- 13 — il fatto è vero (`scheduler.py:351`), la conseguenza no: il job gira a `hour=3` UTC (`:378-383`), stessa
  data di Roma. Residuo: una regola creata dal pannello fra mezzanotte e l'1-2 di Roma del primo del mese
  (`admin/availability.py:194`, `date.today()` di `availability_service.py:65`) restituisce `slot_creati: 0`, e si
  autocorregge alle 03:00 UTC. L'opzione "scheduler a ROME_TZ" della P2 non tocca quel percorso.
- 19 — `hash_admin_password.py:70-82` agisce solo se esiste una riga `ADMIN_PASSWORD=`, assente da `.env` e
  `.env.example`; lo script scrive solo il `.env` locale (`:55-56`).
- 41 — `users.email` è UNIQUE (`models/users.py:17`, migrazione `1972ef07e768`:41): con collation `_ci` i
  duplicati per maiuscole non possono esistere (lo nota PIANO_ANALISI:726). La misura del 40 chiude anche il 41.

**Più largo del descritto — 9.** `UserCreate.email` è `EmailStr` (`schemas/users.py:18`), che mette in minuscolo
il dominio (`'mario@Example.com'` → `'mario@example.com'`, `'MARIO@EXAMPLE.COM'` → `'MARIO@example.com'`);
`BookingCreate.email` è `str` (`schemas/booking.py:25`); `app.js:496,522` manda lo stesso testo ai due endpoint;
`booking.py:125` confronta in Python con `!=`. Chi prenota senza login con una maiuscola nel dominio riceve 403
alla prima prenotazione, su qualunque motore. Verificato sul codice e su `EmailStr`, non con una richiesta HTTP.
L'unico test con dominio maiuscolo (`test_percorsi_critici_ingresso.py:118`) registra ma non prenota.

**Descrizioni sbagliate.** 18 — PIANO_ANALISI:968-969 dice che il server "parte lo stesso": `main.py:162` monta
`StaticFiles` all'import e Starlette solleva `RuntimeError` se la cartella manca (`staticfiles.py:55-56`); l'app non
parte e l'unico avviso è il monitor esterno. 24 — non "mai `res.ok`": 10 `fetch` su 26 lo controllano
(`admin.js:118,548,623,690,900,979,1073,1138,1168,1190`); le 16 scoperte sono a
`:247,308,345,432,454,469,591,709,752,801,816,917,999,1013,1094,1114`. 39 — il caso 1 (email e note nel
calendario) avviene a ogni prenotazione, non solo su guasto (PIANO_ANALISI:870).

**Conteggi.** `PROTOCOLLO.md` dice 31 aperte: sono 35 (il 31 viene da `3fd9f9d`, prima della chiusura dell'8 e
delle voci 40-45 di `edf96cf`). "P2–P6b bloccano 13, 14, 17, 21, 22, 23, 33, 36" è giusto. `CLAUDE.md` ha 60
righe, al limite (`c02ef1b` dice "sotto le 60"); `PIANO.md` 59.

**Ordine.** `PROTOCOLLO.md` mette prima le decisioni perché sbloccano 8 voci, ma di quelle 8 la 13 e la 17 non
hanno effetti, 21 e 36 pochi, 22/23/33 sono latenti. Per impatto: 40 (+41) → 9 → 24 → 26 (solo
`recensione.html`) → 25 → 20 → 39 (casi 1-2) → 14/P3 → P5 per la via minima, prima di qualunque cambio di prezzo.

**Ordine adottato in `PIANO.md`** (2026-11-09): 40 → 9 → 47 → 52 → 46 → 24 → 48 → 26 → 25 → 20 → 39 → 49 → 50 →
14 → 12 → 11 → 53 → 22 → 33 → 51 → 29 → 18 → 35 → 21 → 31 → 36. Prima le misure (40, 52), che non costano nulla e
sbloccano 9, 41, 48 e 49. Il 46 sta prima dei fix del frontend (24, 25, 26): senza, i browser continuano a
eseguire il JS vecchio e la correzione non arriva. La P2 esce dal piano perché 13 e 17 sono decadute.

**Tabella delle voci aperte.**

| Voce | Ancora reale? (prova) | Impatto | Proposta |
|---|---|---|---|
| 9 | sì, più largo: `booking.py:125`, `schemas/users.py:18` vs `schemas/booking.py:25` | 403, prenotazione persa | tieni, prima di tutto dopo il 40 |
| 10 | sì: `retention_service.py:40-45`, `availability_service.py:124-130` | volumi irrealistici | decade; la parte silenziosa va in N2 |
| 11 | in parte: 60 s di default | ≤60 s, poi 1205 sugli slot concorrenti | riformula: accorciare il timeout |
| 12 | sì: `booking.py:179`→`213`→`245` | lock fino a 60 s, raro | tieni, dopo l'11 |
| 13 | fatto sì, conseguenza no | residuo trascurabile | decade |
| 14 | sì: `users.py:104-137`, `booking.py:121-126,155-165` | abuso intenzionale | tieni (P3) |
| 39 | sì: uscita:183/202/265, trasformazione:182, `scheduler.py:156,195-198` | caso 1 sempre | tieni casi 1-2 |
| 15 | sì: `slots.py:12`, `users.py:20`, `admin/__init__.py:61` | nessuno | decade |
| 16 | sì: `booking.py:27`, `consulenza.py:14`, `pacchetti_richieste.py:14`, `discord_auth.py:23` | nessuno | decade |
| 17 | sì: `scheduler.py:35-47` | solo per i test | decade |
| 18 | sì: `main.py:89,162,190-202` | sito giù se cambia la cartella d'avvio | tieni, bassa |
| 19 | presupposto irraggiungibile | nessuno | decade |
| 20 | sì: `admin/clients.py:146,161`, `admin/packages.py:19,25`, `admin.js:601,735` | orari sfasati, sempre | tieni |
| 21 | sì: `main.py:129` | elenco endpoint pubblico | tieni, bassa (P4) |
| 22 | sì: `booking.py:38`, `index.html:198,201`, `app.js:25,380,405` | al primo cambio prezzo | tieni (P5) |
| 23 | sì: `booking.py:44`, `app.js:311` | latente | accorpa al 22 |
| 24 | sì, 16 su 26 | il coach decide su dati falsi | tieni, alta; correggi il titolo |
| 25 | sì: `app.js:152-160,412-437` | prezzo pieno o storico perso su errore | tieni |
| 26 | sì: `recensione.html` non carica `i18n.js`; `booking.py:301` | sempre | tieni, limitata a `recensione.html` |
| 27 | sì: `calendar_service.py:199-201` | nessuno | accorpa al 29 |
| 28 | sì: `google_oauth_service.py:63,99` | un token in più a settimana | decade |
| 29 | sì: `i18n.js:84,217`, `availability_service.py:29-31`, `scheduler.py:402` | chi legge il codice | tieni, assorbe 27, 32 e N7 |
| 30 | sì: `package_service.py:13,20,27` vs `index.html:368,380,392` | se qualcuno lo modifica | accorpa al 33 |
| 31 | sì: `users.py:59-61`, protetto da `get_admin` | solo con token admin rubato | tieni, bassa |
| 32 | sì: `alembic/env.py:14` (gli 8 model li registra `models/__init__.py`) | nessuno | accorpa al 29 |
| 33 | sì: `schemas/booking.py:9`, `admin.js:183,732`; due `Literal` dei pacchetti (`schemas/package.py:7`, `pacchetto_richiesta.py:10`) | KeyError e 500 al primo pacchetto nuovo | tieni (P5) |
| 34 | sì: `app.js:359`, `admin.js:160` | solo browser futuri | decade |
| 35 | sì: `calendar_service.py:26` | solo se le credenziali trapelano | tieni, bassa |
| 36 | sì: `app.js:499`, nessun `PATCH` sulle regole | raro | tieni (P6a/b) |
| 40 | misura non fatta | prerequisito del 9 | estendi alle misure di 2.5 |
| 41 | non fatta; email UNIQUE | probabilmente zero | accorpa al 40 |
| 42 | sì: `booking.py:298-299`, `test_booking.py:557` | nessuno | decade |
| 43 | sì: nessun test su `booking.py:300-301` | nessuno | decade |
| 44 | sì: `booking.py:99-109,153-155` | nessun utente | accorpa al 14 |
| 45 | voce sul piano, riga 88 invece di 89 | nessuno | decade, come il 37 |

**Terza opzione per la P3, assente dal piano** (PI): un tetto giornaliero alle prenotazioni senza login (~1 ora, con
avviso Discord), più l'argomento contro "pending + link di conferma" per chi mantiene il sito da solo.

## 5. Inventario e verdetto

**Nel repository**

| Oggetto | Verdetto | Motivo |
|---|---|---|
| `CLAUDE.md` (60 righe) | tieni, correggi | `:40` timeout; `scheduler.py:35-47` → anche `:351`; al limite |
| `PIANO.md` (59) | tieni, riorganizza | decadute e accorpate; voci nuove; 88→89; chiuse compattate per restare sotto 60 |
| `PROTOCOLLO.md` (139) | tieni, correggi | diagramma perso (6.5); `:139` deploy certo; "Stato e prossimi passi" è stato vecchio (31, ordine); "Fase 8" indefinita; rimando a `PROMPT.txt`; "prompt originale" dell'audit non salvato; manca la regola dei 60 giorni |
| `POTATURA.md` (non tracciato) | scarta dopo l'uso | completo (35 righe, una per voce), ma con errori (§8); il suo contenuto corretto è qui e nei messaggi di commit |
| `PROMPT.txt` (0 byte) | scarta, o riempi | i prompt stanno in `PROTOCOLLO.md`; l'unico contenuto utile sarebbe il prompt originale dell'audit, oggi non salvato |
| `AUDIT.md`, `PROBLEMI.md`, `DRIFT.md` | storici, non si toccano | errori noti (timeout, 18) si correggono nei commit delle voci |
| `_archivio_audit/PIANO_ANALISI_2026-09.md` | storico | idem |
| `_archivio_audit/Agenti… ha senso.md` | storico | copia del documento Claude Docs del 2026-11-06; regola utile: agenti sì per audit, test e spiegazioni, no per decidere o committare |
| `.env.example` | tieni, integra | topologia Railway (2.3), schema obbligatorio in FRONTEND_ORIGINS (RD:281, RR:120-125), rimandi morti `:19,86` |
| `requirements.txt` | togli `Werkzeug==3.1.8` | nessun import, "Required-by" vuoto, entrato col freeze di `eabc12f` |
| `alembic/README` | superfluo, innocuo | riga del template, nessuno la cita |
| `.gitignore` | togli `.env.backup-pre-test` | il file non esiste più |
| `alembic.ini`, `script.py.mako`, favicon, immagini, font | tieni | usati (D §3) |
| `monitor.yml` | correggi il commento `:18-22` | cadenza reale ~5 h; regola dei 60 giorni |

**Locale, fuori da git**

| Oggetto | Verdetto |
|---|---|
| `.env`: `EMAIL_APP_PASSWORD`, `SECRET_KEY` | togli; revoca la password per app nell'account Google se ancora valida |
| `.claude/settings.local.json` | pota: ~13 permessi usa e getta della sessione `3917a5bc` del 2026-09-16 (slot 7/8/9, fixture del 2026-10-05, `ispeziona.py` in uno scratchpad che non esiste più); `python -m pytest` col Python di sistema (fallisce); e tre permessi larghi che contraddicono il protocollo: `git commit *`, `git checkout *` (permette `git checkout -- .` senza conferma), `python -c '*'` |
| 87 `.pyc` `cpython-314` | superflui: qualcuno ha eseguito il codice col Python di sistema |
| `.coverage`, `.pytest_cache` | lascia, si rigenerano |

**Ref git**

| Ref | Verdetto |
|---|---|
| branch `audit/baseline` | elimina: è lo stesso commit del tag `pre-audit` (`e9ad5d5`) |
| branch `recupero-progetto` | elimina: è `origin/master` (`b348c30`), nessun commit unico |
| branch `salvataggio-punto-2` | trasforma in tag e elimina il branch: 3 commit unici (`bebe0bd`, `53496f0`, `8045cea`), tentativo del 2026-09-14 di B1/B3 rifatto in master; i suoi test esistono rinominati (`dab88f5`). Unico contenuto non altrove: 6.4 |
| tag `pre-audit`, `rete-di-sicurezza` | tieni: base del confronto dell'audit e della suite di regressione |

**Fuori dal repository (`Desktop/_DA_SMISTARE/VGC/`)**

| Oggetto | Verdetto |
|---|---|
| `coaching-app-BACKUP/` (235 MB) | scarta: copia del repo a `e9ad5d5`; tutti i ref presenti nel repo, nessuno stash; unici file non in git `.coverage` e `.env`, identico all'attuale (confronto per hash). Tiene una seconda copia dei segreti |
| `_archivio_docs/` (676 KB) | doppione di `2f912d2` byte per byte; scartabile dopo il recupero di §6 |
| `prenotazioni.csv` | export del pannello dell'11 giugno: 10 righe con nome ed email (colonna Showdown, poi rimossa). Se sono clienti veri, vanifica l'anonimizzazione dell'app |
| `coaching_booking_starter/` | prototipo di maggio, altra struttura: superfluo per il progetto |
| `Contenuti/`, `Pokemon/`, `Risorse/`, `Credenziali/`, `.docx`, generatore di schedule | fuori perimetro, non esaminati (`Credenziali/` di proposito) |

Spostare la cartella del progetto da `_DA_SMISTARE` slega la memoria di Claude Code (indicizzata per percorso) e i
percorsi assoluti del venv (`venv/pyvenv.cfg`).

**Artifact su claude.ai**

| Artifact | Verdetto |
|---|---|
| "Protocollo operativo — coaching-app" (doc, 2026-11-06) | originale di `PROTOCOLLO.md`, contiene il diagramma perso; con due copie serve scegliere quale vale |
| "Agenti al posto della revisione umana" (doc) | originale del file in `_archivio_audit/` |
| "VGC Coaching Platform" (pagina, 2026-08-31) | vetrina precedente all'audit: "62 test, 70%" (oggi 198, 91%); "cancellazione in un'unica operazione atomica" falsa per i clienti con pacchetto fino a B1; retention incompleta fino a R7, non ancora online. Da riallineare se la si mostra |

**Memoria di Claude Code**

| File | Correzione |
|---|---|
| `MEMORY.md`, voce Gmail | "verify after 2026-09-11" → verificato il 2026-11-09 (riserva 2.6) |
| `project_gmail_api_email_delivery` | togli i rimandi a SP §9.1; registra la prova; "aggiorna su entrambi i servizi" contraddice RR:171 (2.3) |
| `feedback_documenta_subito_con_ricontrollo` | SP §9.1, §13.1, §13.5 non esistono: oggi la lista è `PIANO.md`; esempio del 2026-09-11 chiuso |
| `feedback_preserve_didactic_comments` | il "documento di studio nel repo" non esiste dal 2026-09-11 (`c8fc0ca`); da riconciliare con `CLAUDE.md` (6.3) |
| `feedback_minimal_essential_codebase` | "keep print()s" superato: 0 `print(` nel backend da `a13f5c8` (2026-08-25), 7 file usano `logging`. La preferenza per un codice essenziale resta |
| `feedback_piano_unica_fonte_di_stato` | "la prossima è la 40" → 46 |
| `project_db_password_exposed` | rimando a STATO_PROGETTO; contraddizione interna ("MUST rotate" contro il declassamento del 2026-08-09); rotazione della password MySQL locale ancora da fare |
| `project_cache_asset_statici_pannello` | diventa N1 se la voce entra nel piano |

## 6. Informazione recuperata dai documenti eliminati

**6.1 Fatti operativi (pezzo A).** O1 push = deploy (2.2). O2 topologia Railway (2.3). O3 pulizia Railway (2.4).
O4 regola dei 60 giorni (2.1). O5 ripristino mai provato (2.8). O6 lunghezze delle colonne (N4). O7 nessun test
esegue le migrazioni: lo schema dei test nasce da `create_all` (`conftest.py:89-91`; anche r1 A8). O8 decisione:
nessun vincolo UNIQUE sullo slot di una prenotazione, incompatibile con cancella-e-riprenota (RM:57, CS:332-334,
SP:364); `booking.py:167-200` spiega la riserva atomica ma non questa scelta. O9 checklist identità per gli
endpoint nuovi (SP:578-592, CS:528-545): l'identità viene da `get_studente`/`get_admin`, mai dal corpo della
richiesta, e ogni endpoint ha un test "come un altro utente" che si aspetta 403/404. O10 FRONTEND_ORIGINS va scritta
con lo schema (RD:281, RR:120-125: senza `https://` fino al 2026-09-02, e rompeva il link di recensione).

**6.2 Decisioni e misure (pezzo B).** r3 §2: numeri misurati a runtime (0 endpoint async, 40 thread, pool 5+10,
attesa 30 s, Google 60 s, refresh OAuth 120 s, Discord 5/10 s, APScheduler misfire 1 s, coalesce attivo,
max_instances 1, nessun retry). PI §B.1: i 40 "non si tocca" con motivazione e segnale di riapertura (1205 per U12,
`QueuePool limit` per U25, query `sessioni_usate > sessioni_totali` per U13, `Literal` derivato dal catalogo prima
di aggiungere un pacchetto, isort quando arriva un formatter, Dockerfile per U36): oggi nessun documento dice che
quei debiti furono accettati consapevolmente. r2 §1: base di sicurezza verificata dinamicamente (401 sui 13
endpoint admin senza token, token studente rifiutato sull'admin, 403 sulle cancellazioni altrui, nessuna SQL
injection o XSS, `.env` mai in git). r4 §4.1: mutazioni, 6 rotture intercettate su 8 (oggi il limite di
prenotazioni è coperto, le notifiche no). Invarianti mai scritti: monolite FastAPI, frontend senza build, nessun
servizio a pagamento ricorrente, single-tenant, pagamento fuori app, prenotazione da ospite come percorso normale.

**6.3 Materiale didattico (`CS`, 582 righe).** Su 24 passaggi, 16 sopravvivono come commenti "perché": `yield` e
`finally` → `database.py:33-44`; JWT non revocabile → `auth_service.py:43`; filtro degli slot passati e trappola
SQLite → `routers/slots.py:26-41`, `test_slots.py:136-189`; get-or-create → `models/users.py:16`,
`routers/users.py:130-132`; orari delle sessioni da 2 h → `booking.py:41-45`; race condition → `booking.py:167-200`;
notifiche dopo il commit → `booking.py:248`; `lifespan` → `main.py:113-120`; `pool_pre_ping` → `database.py:16-26`;
`foreign_keys` → `models/booking.py:59-61`; `BookingResponseStudente` → `schemas/booking.py:77-82`; UTC naive →
`timezone_service.py:3-9,45-51`; import admin → `admin/__init__.py:58-60`; scheduler → `scheduler.py:14-15,154,373-375`;
XSS e delegazione → `admin.js:20-45`; costruzione della suite → `conftest.py:14,70,95-108`, `test_scheduler.py:4,24,172`.
Persi (~174 righe, lo strato concettuale): perché un monolite (CS:65-69); model contro schema (CS:82-86); il
decoratore (CS:94-107); `Depends` e la catena delle dependency (CS:109-127); ORM, N+1 e `joinedload`
(CS:145-160); Pydantic, async e migrazioni come concetti (CS:162-193); perché niente UNIQUE (CS:332-334); le 7
regole per chi modifica il codice (CS:528-545); doppione in RD:228-236. Commenti nel codice oggi: 3.940 righe su
16.277 (24%), quasi tutte "perché" operativo. `CLAUDE.md` dice che i commenti sono "il solo posto" delle ragioni;
la memoria dice che la didattica sta in un documento: le due regole vanno riconciliate.

**6.4 Branch `salvataggio-punto-2` (`bebe0bd`), commento di `elimina_cliente`.** Unica frase non altrove: "La flush
va DOPO il ciclo, non dentro: `libera_slot_prenotazione` chiama Google Calendar a ogni giro e anticiparla terrebbe
aperti lock di riga su bookings e slots per tutta la durata di quelle chiamate HTTP." Il commento di master
(`admin/clients.py:125-133`) spiega il flush ma non la sua posizione.

**6.5 Diagramma di `PROTOCOLLO.md`.** Il segnaposto `[embedded content: ciclo di intervento · 6 passi, 3
controlli]` è un widget del documento Claude Docs (`node/b37b7402-d211`). Titolo: "Ogni intervento passa da due
controlli prima del commit". Passi: 1 `/clear` in Claude Code → 2 chiedi il piano, non il codice → controllo
"Piano chiaro?" (no: chiedi un esempio prima/dopo, poi torna al 2) → 3 autorizza l'esecuzione → 4
`git diff --stat` → controllo "Solo i file attesi?" (no: FERMATI, chiedi perché) → 5 `pytest -q --tb=line` →
controllo "Suite verde?" (no: `git checkout -- .` e ripensa) → 6 commit + spunta in `PIANO.md` → prossimo intervento.

**6.6 Prompt originale dell'audit.** `PROTOCOLLO.md:116` chiede di rigenerare l'audit "con il prompt originale".
Non è salvato da nessuna parte: i commit `2bf2316`, `b537593`, `1f16684` hanno il corpo vuoto. L'intestazione di
`AUDIT.md` (perimetro e metodo) ne è l'unica traccia.

## 7. Orfani minori (pezzo B; il resto della stessa fonte è risolto o tracciato)

1. Doppia spesa di un pacchetto (r2 S3, U13): `booking.py:145` controlla, `:243` fa `+= 1`, nessun UPDATE condizionale né vincolo (`models/package.py:25-26`); debito accettato, ~1 ora.
2. `review_email_sent` marcato anche quando l'invio fallisce (r3 O2): `scheduler.py:195-198` — caso 2 del 39.
3. Notifiche di `create_booking` non osservate dai test (r4 M2, U07): `conftest.py:107-110` con lambda vuote — nel "test prima" di 11, 12, 39.
4. `/health` risponde ok dopo una migrazione fallita (ANALYSIS §6.16, r3 O12, U27): `main.py:86-110,184-185`.
5. Pool 5+10 contro 40 thread, `/health` nello stesso pool (O4, U25): `database.py:26`; segnale `QueuePool limit`.
6. Paginazione senza spareggio (O16, U39): `admin/bookings.py:51`.
7. Cache delle credenziali senza lock (O15, U43): `google_oauth_service.py:27,51,60`.
8. Dump con tre copie in memoria (O14, U42): `backup_service.py:104,122,128-129`.
9. `note_admin` nella risposta pubblica (S6, U16): `booking.py:47` usa `BookingResponse` (`schemas/booking.py:56`); latente.
10. Formato delle date nelle email reimplementato (A9): `booking.py:208`, `scheduler.py:136` — con la 20.
11. Rate limiter non testabile (M10): `conftest.py:77`.
12. La suite scade il 2030-01-07 (M9): 62 occorrenze di `2030` in `tests/*.py`.
13. Recensione per una sessione non svolta (S9, U30): `booking.py:339-369`; l'argine è l'approvazione manuale.
14. Flag `Secure` legato al redirect URI (S11, U33): `discord_auth.py:40,74,181`; verificato in produzione il 2026-09-02.
15. Token admin di 8 ore (D2, U49): `EXPIRE_MINUTES` (`auth_service.py:21`) vale anche per lo studente.
16. Timing del login (D3, U50): `auth_service.py:31-32`.
17. Vetrina recensioni senza LIMIT (S14, U35): `booking.py:324`; dopo N3.
18. Dominio nell'handler e ventaglio di notifiche duplicato (A2, A5; U18, U22): debito accettato.
19. Liste admin non paginate e di forma diversa (A3): `admin/packages.py:25`, `reviews.py:36`.
20. `renderPaginazione` interpola dentro `onclick` (U47): `admin.js:86,89`.
21. `elimina_cliente` irreversibile senza conferma lato server (U46).
22. `libera_slot_prenotazione` fa chiamate di rete, anche dentro un ciclo (M7, U44).
23. Nessun retry (O11, U24): l'insert su Calendar non è idempotente.
24. La media voti della dashboard include le recensioni non approvate (R8): `dashboard.py:59`.
25. La CI non ha soglia di copertura (r4 §4.2): `pytest.ini:17`.
26. `POST /admin/slots/sync-calendario` senza test (SP:476-478).
27. Suite su MySQL: costo e alternativa, una seconda corsia CI con `mysql:8` (SP:487).
28. Decisioni minori: dominio personalizzato non acquistato (SP:472); prove d'abuso mai fatte in produzione (SP:466); `categoria` non anonimizzata perché non identifica (SP:689, `retention_service.py:55-59`); coach 1:1 dal proprio Discord (RM:110); niente librerie di grafici (RM:179).
29. Setup da zero (RD:240-272): venv, `pip install -r requirements-dev.txt`, copia di `.env.example`, pannello su `/admin-panel`, `alembic downgrade`/`revision`.
30. Falsi già allora: S13 (password nell'avviso Discord: non compare), U34, U51, python-jose (opinione).

Avvertenze del pezzo D: `StarletteDeprecationWarning` (TestClient su `httpx`) e 17 `DeprecationWarning` sui cookie per
richiesta possono rompere la suite al prossimo aggiornamento; `google.api_core` abbandona Python 3.11 dopo il
2027-10-24, mentre `nixpacks.toml` fissa `python311`. Copertura sotto l'80%: `email_service` 66%, `database` 69%,
`main` 69% (avvio e migrazioni, `:86-103`), `discord_service` 71%.

## 8. Correzioni a POTATURA.md

Giusto contro l'analisi: 13 ("oggi nulla"), 18 ("il sito non parte"), 31 (protetto da `get_admin`).
Sbagliato o incompleto: 9 ("solo in produzione": falso, e manca la variante sul dominio); 10 (i job non "si
fermano", falliscono a ogni esecuzione senza avviso); 11 ("senza fine": il limite è 60 s, poi 1205); 13 (residuo
del pannello, §4); 19 ("se ne accorge il coach": lo script è solo locale e il ramo non scatta); 39 (il caso 1
avviene sempre; il caso 3 "non è un lavoro da fare", :872; il caso 4 "non va fatto per sé", :875-880).

## 9. Appendice — POTATURA.md originale

Scritto il 2026-11-09 dalla sessione "valuta-impatto-voci-piano" e mai committato: una riga per voce aperta,
nel formato "cosa succede; chi se ne accorge; quando". Riportato senza modifiche; le correzioni sono al §8.

- 9 · R6 — un cliente registrato come `mario@example.com` che prenota scrivendo `Mario@Example.com` riceve un 403 e non riesce a prenotare; se ne accorge il cliente (il coach solo se il cliente glielo scrive); solo in produzione, solo quando le maiuscole cambiano.
- 10 · R16 — i due job notturni falliscono per memoria e si fermano in silenzio (anonimizzazione GDPR e pulizia slot comprese); non se ne accorge nessuno; solo quando utenti e slot passati saranno moltissimi.
- 11 · R4a — la prenotazione resta in attesa senza fine; se ne accorge il cliente, che vede la pagina caricare all'infinito; il giorno in cui Google Calendar si blocca senza rispondere.
- 12 · R4b — le prenotazioni concorrenti sullo stesso slot si accodano e le connessioni al database possono esaurirsi, rallentando tutto il sito; se ne accorgono i clienti che prenotano in quel momento; solo con Google lento, con il volume attuale quasi mai.
- 13 · R11 — oggi nulla, perché alle 03:00/04:00 in UTC la data coincide con quella italiana; nessuno; uno slot in più o in meno a fine mese solo se il job venisse spostato verso mezzanotte o il container cambiasse fuso.
- 14 · R1+R2 — chi conosce l'email di un cliente prenota a suo nome (slot veri, limite consumato, email di conferma) e chiunque supera il limite di 2 con email diverse; se ne accorge il cliente colpito o il coach (prenotazioni fantasma); solo se qualcuno lo fa apposta.
- 39 — email e note in chiaro sul calendario (lo vede chi ha accesso al calendario), promemoria non partito ma segnato come inviato (il cliente che salta la sessione), prenotazione senza evento (il coach, se si basa sul calendario), sync fallita che dice "0 slot bloccati" (il coach, dopo un clic manuale); ciascuno solo quando il servizio esterno fallisce.
- 15 · D1 — nulla cambia nel comportamento; nessuno; pesa solo su chi lavora sul codice.
- 16 · D2 — nulla cambia nel comportamento; nessuno; pesa solo su chi lavora sul codice.
- 17 · D3 — nulla, al riavvio le variabili vengono rilette; nessuno; ostacola solo chi scrive test.
- 18 · R12 — il sito non parte più; se ne accorgono tutti subito, e il coach riceve l'avviso su Discord; solo se un giorno il server venisse avviato da una directory diversa dalla radice.
- 19 · R13 — la nuova password admin non funziona e resta valida la vecchia, senza messaggi; se ne accorge il coach; solo se cambia password con lo script partendo da un `.env` locale con entrambe le righe.
- 20 · R14 — date di note e pacchetti indietro di 1-2 ore e in formato diverso dal resto del pannello; se ne accorge il coach; ogni volta che legge quando è stata creata una nota o un pacchetto.
- 21 — l'elenco degli endpoint, admin compresi (senza dati), resta pubblico; solo chi va a curiosare; sempre.
- 22 · R9 — il cliente vede un importo nel riepilogo e riceve l'email con un altro; se ne accorge il cliente; al primo cambio di prezzo fatto nel backend e non nell'HTML.
- 23 · R10 — il cliente vede orari che danno errore, oppure non vede orari prenotabili (e nel secondo caso nessuno se ne accorge e la vendita si perde); solo se le ore valide da 2h cambiano in un posto e non nell'altro.
- 24 · R3 — il pannello sembra vuoto o sembra aver salvato, senza errori; se ne accorge il coach (o non se ne accorge affatto); quando il token scade dopo 8 ore col pannello aperto o un'operazione viene rifiutata.
- 25 · R8 — lo studente con pacchetto pagato paga a prezzo pieno, oppure perde lo storico e il tasto "Cancella"; se ne accorge lo studente, se ci fa caso, o il coach in seguito; durante un errore di rete o un 500.
- 26 · R15 — errori in inglese e pagina recensione tutta in inglese; se ne accorge il cliente italiano; ogni volta che riceve un errore o apre il link della recensione.
- 27 · C2 — nulla; nessuno; mai.
- 28 · C3 — una richiesta di token in più; nessuno; una volta alla settimana dopo ogni riavvio.
- 29 · C4 — tre commenti o nomi che dicono altro dal codice; nessun utente, solo chi legge il codice; quando ci lavora.
- 30 · C1a — cambiare quei numeri non cambia i prezzi barrati sul sito; chi li modifica; solo se qualcuno ci prova.
- 31 · C1b — un modo in più per scaricare tutti i clienti; nessuno, perché l'endpoint è protetto da `get_admin`; solo se il token admin finisse in mani sbagliate.
- 32 · C1c — nulla; al massimo uno sviluppatore la crede la lista dei model da tenere aggiornata; quando aggiunge un model.
- 33 · C5 — codice grezzo al posto dell'etichetta nel pannello o etichetta non tradotta sul sito; se ne accorge il coach o il cliente; solo se un tipo di servizio o pacchetto cambia in un posto e non negli altri.
- 34 · C6 — un errore JS negli handler; tutti gli utenti; solo se un browser futuro eliminasse `window.event`.
- 35 — le credenziali del calendario danno accesso completo invece che ai soli eventi; nessuno; solo se trapelassero.
- 36 · C1d — il telefono resta sempre vuoto e le regole di disponibilità si sospendono solo da database; se ne accorge il coach; il giorno in cui vuole sospendere una regola dal pannello.
- 40 — si rischia di fare il 9 partendo da un'idea sbagliata sulla collation di produzione; nessuno direttamente; quando si fa il 9.
- 41 — lo stesso cliente resta con due account, storico e pacchetti divisi; se ne accorge il coach scorrendo i clienti; solo se i duplicati esistono già.
- 42 — nulla, il frontend mostra il messaggio senza leggere il codice 400/409; nessuno; mai.
- 43 — una modifica futura a quel ramo può romperlo senza che i test lo segnalino; nessuno; quando qualcuno lo tocca.
- 44 — chi legge il codice crede a una protezione che non c'è (vedi 14); nessun utente; quando qualcuno ci lavora.
- 45 — una voce resta classificata male nel piano; nessuno; mai.
