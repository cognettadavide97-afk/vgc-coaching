# PIANO

Lista ordinata degli interventi, ricavata dalla fusione di `PROBLEMI.md` (gravità dei difetti) e
`DRIFT.md` (divergenze fra documenti e codice). Ogni voce è pensata per stare in **un solo commit**.

Per ogni intervento: **cosa si corregge**, **quali file tocca**, **quali test esistenti lo coprono**,
**da cosa dipende**. Dove serve una decisione prima di aprire l'editor, è scritto in chiaro.

## Come leggere la copertura

I tre file `tests/test_percorsi_critici_*.py` (commit `c8fc0ca`) non proteggono il comportamento
corretto: **fotografano quello attuale, difetti compresi**. Le loro `assert` sono accompagnate da un
commento `COMPORTAMENTO SOSPETTO`. Distinguo quindi tre casi, perché comportano lavoro diverso:

- 🛡 **Protettivo** — il test asserisce il comportamento *giusto*: la correzione deve lasciarlo verde.
  È una rete di sicurezza.
- 📷 **Fotografia** — il test asserisce il comportamento *sbagliato*: la correzione **deve invertire
  quelle `assert`** nello stesso commit, e il commento `COMPORTAMENTO SOSPETTO` va rimosso. Non è una
  rete di sicurezza, ma il difetto è già osservabile e pinzato: non serve costruire lo scenario da zero.
- ⚠️ **Scoperto** — nessun test tocca il punto. **Il test va scritto prima** della correzione, in un
  commit separato che deve fallire (o passare fotografando l'errore) prima della modifica.

**Baseline verificata** — `pytest` al 2026-09-15: `186 passed`, copertura di `backend/` al 90%.
Ogni intervento riparte da qui.

## Dove si verifica: tre ambienti, non due

Verificato il 2026-09-15. La distinzione non è "locale contro produzione" ma **suite contro tutto il
resto**:

| Ambiente | Motore | Come ci si arriva |
|---|---|---|
| Suite di test | SQLite in memoria | `tests/conftest.py:33`, `tests/test_avvio.py:58` — le **uniche due** occorrenze di `sqlite` in tutto il codice Python del progetto |
| Sviluppo locale | **MySQL 9.7.0** su `localhost`, database `vgc_coaching` | `DATABASE_URL` del `.env`; il server è attivo (porta 3306) e contiene tutte e 8 le tabelle più `alembic_version` |
| Produzione | MySQL su Railway | `DATABASE_URL` della piattaforma |

SQLite **non** è il database dello sviluppo locale: è confinato alla suite. Fra il codice e la
produzione c'è quindi un MySQL vero, e questo cambia il costo della verifica di diversi interventi.
Due proprietà del MySQL locale, misurate:

- **collation `utf8mb4_unicode_ci`** — case-insensitive. È esattamente la condizione che produce il
  difetto **R6** (intervento 9) e che SQLite non può riprodurre: il difetto è **riproducibile in
  locale, oggi**.
- **`fk_bookings_package_id` esiste** sulla tabella `bookings`, insieme alle altre tre chiavi esterne.
  Anche **B1** (intervento 2) è quindi riproducibile in locale con l'errore 1451 vero, non solo
  dedotto dall'ordine degli statement.

Ne segue una regola operativa per gli interventi che toccano il database: **suite verde non basta**.
Gli interventi **1, 2, 9, 10, 13** e ogni migrazione nuova vanno provati anche contro il MySQL locale
prima di considerarli chiusi — è una prova a costo quasi nullo che oggi il piano non sfruttava.

> **Da verificare** — la versione e la collation del MySQL di Railway non sono state misurate e
> potrebbero non coincidere con il 9.7.0 / `utf8mb4_unicode_ci` locale. La collation in particolare
> decide il comportamento di R6: se la produzione fosse su una collation diversa, il difetto
> cambierebbe forma. Da controllare prima dell'intervento 9.

## Ordinamento

Applicati nell'ordine dichiarato: **① BLOCCA**, **② coperto da test esistenti**, **③ sblocca altri
interventi**, **④ cosmetico**. L'intervento 1 precede tutto pur non essendo BLOCCA: è il prerequisito
di osservabilità del primo BLOCCA, e costa una riga.

Un **✅** davanti al nome segna un intervento **chiuso**: codice applicato, test aggiornati nello
stesso commit e — dove il piano la richiede — verifica su MySQL eseguita. Senza tutte e tre le cose
l'intervento resta aperto, anche se il codice è già scritto: la sezione corrispondente dice cosa manca.

| # | Intervento | Gravità | Copertura | Dipende da |
|---|---|---|---|---|
| 1 | ✅ Chiavi esterne attive nella suite | prereq | 🛡 intera suite | — |
| 2 | ✅ B1 — cancellazione cliente con pacchetto | BLOCCA | 📷 + 🛡 | 1 |
| 3 | ✅ B3 — macchina a stati sulla prenotazione | BLOCCA | 📷 + 🛡 | — |
| 4 | B2a — sblocco degli slot, lato backend | BLOCCA | 📷 + 🛡 | decisione P1 |
| 5 | B2b — sblocco degli slot, lato pannello | BLOCCA | ⚠️ | 4 |
| 6 | R17 — chiave della cache OAuth | RISCHIOSO | 🛡 | — |
| 7 | R5 — esito della cancellazione dell'evento | RISCHIOSO | 📷 + 🛡 | — |
| 8 | R7 — anonimizzazione di note e prenotazioni | RISCHIOSO | 📷 + 🛡 | — |
| 9 | R6 — normalizzazione dell'email | RISCHIOSO | 📷 + 🛡 | — |
| 10 | R16 — job che caricano l'intera tabella | RISCHIOSO | 🛡 | — |
| 11 | R4a — timeout sul client Google | RISCHIOSO | 🛡 | — |
| 12 | R4b — evento creato dopo il commit | RISCHIOSO | 🛡 | 7, 11 |
| 13 | R11 — fuso orario dello scheduler | RISCHIOSO | 🛡 | decisione P2 |
| 14 | R1+R2 — identità dell'ospite | RISCHIOSO | 📷 + 🛡 | decisione P3 |
| 15 | D1 — `get_admin` fuori da `routers/admin` | struttura | 🛡 intera suite | — |
| 16 | D2 — dependency degli studenti fuori da `routers` | struttura | 🛡 intera suite | 15 |
| 17 | D3 — env dello scheduler lette all'avvio | struttura | 🛡 | 13 |
| 18 | R12 — percorsi assoluti | RISCHIOSO | ⚠️ scrivibile | — |
| 19 | R13 — scrittura del `.env` negli script | RISCHIOSO | ⚠️ scrivibile | — |
| 20 | R14 — due fusi orari nel pannello | RISCHIOSO | ⚠️ scrivibile | — |
| 21 | Superficie di `/docs`, `/redoc`, `/openapi.json` | da decidere | ⚠️ scrivibile | decisione P4 |
| 22 | R9 — listino dei prezzi dal server | RISCHIOSO | ⚠️ parziale | decisione P5 |
| 23 | R10 — ore valide per le sessioni da 2h dal server | RISCHIOSO | ⚠️ parziale | 22 |
| 24 | R3 — il pannello non guarda `res.ok` | RISCHIOSO | ⚠️ impossibile | — |
| 25 | R8 — errori silenziosi nel frontend pubblico | RISCHIOSO | ⚠️ impossibile | — |
| 26 | R15 — messaggi d'errore in una lingua sola | RISCHIOSO | ⚠️ impossibile | — |
| 27 | C2 — import locale senza ciclo | COSMETICO | 🛡 | — |
| 28 | C3 — doppio refresh nella sonda | COSMETICO | 🛡 | — |
| 29 | C4 — commenti e segnaposto che mentono | COSMETICO | — | — |
| 30 | C1a — `prezzo_pieno_cents` mai letto | COSMETICO | 🛡 | — |
| 31 | C1b — `GET /users/` mai chiamato | COSMETICO | — | — |
| 32 | C1c — import incompleto in `alembic/env.py` | COSMETICO | — | — |
| 33 | C5 — catalogo ed etichette in sei posti | COSMETICO | ⚠️ parziale | 22 |
| 34 | C6 — `event` implicito negli handler | COSMETICO | ⚠️ impossibile | — |
| 35 | Scope Calendar ridotto a `calendar.events` | non cosmetico | 🛡 | riautorizzazione Google |
| 36 | C1d — `telefono` e `attiva`: completare o rimuovere | prodotto | — | decisione P6 |
| 37 | `AUDIT.md` — due omissioni dichiarate | documentazione | — | 21 |
| 38 | Documentare l'orizzonte "fino a fine mese" | documentazione | 🛡 | — |

---

# Fascia A — prerequisito e BLOCCA

## 1. ✅ Attivare le chiavi esterne nella suite di test

**Chiuso** il 2026-09-15, commit `e3b52f5`. La suite è rimasta a 186 verdi con il listener attivo:
nessun difetto nuovo è emerso oltre a B1, che era atteso.

**Cosa si corregge** — la suite gira su SQLite senza `PRAGMA foreign_keys`, quindi i vincoli che in
produzione (MySQL) esistono davvero non vengono mai applicati. È la causa comune di B1, R6 e della
non osservabilità di B3. Un listener `PRAGMA foreign_keys=ON` su `TEST_ENGINE` rende visibile in
locale una classe di difetti oggi invisibile.

**File** — `tests/conftest.py:32-37` (un listener `event.listens_for(TEST_ENGINE, "connect")`).

**Test** — 🛡 l'intera suite: le 186 devono restare verdi. **Non dare per scontato che lo restino**:
`PROBLEMI.md` avvertiva che l'attivazione può far emergere altri punti oggi silenziosi. Se qualche
test cade, il commit si ferma qui e i fallimenti vanno censiti come voci nuove di questo piano —
non aggirati.

**Dipende da** — niente. **Sblocca** — 2 (e rende difendibile ogni intervento successivo sul DB).

**Verifica su MySQL** — l'obiettivo di questo intervento è far comportare SQLite come il MySQL che sta
già su `localhost`. Il metro di paragone non è ipotetico: dopo la modifica, un difetto di vincolo deve
fallire **in entrambi**.

> ⚠️ **Contraddizione con `CLAUDE.md`, risolta con questo intervento** — la sezione *NON TOCCARE
> SENZA CHIEDERE* elencava `tests/conftest.py` e il suo `PRAGMA foreign_keys=ON` come se la riga
> esistesse già. **Non esisteva**: era una raccomandazione scritta al futuro. Ora la riga c'è davvero
> e la voce di `CLAUDE.md` è stata riformulata di conseguenza, nello stesso commit.

---

## 2. ✅ B1 — La cancellazione di un cliente con pacchetto fallisce con 500

**Chiuso** il 2026-09-15, commit `ec62a89` per codice e test, verifica su MySQL locale eseguita lo
stesso giorno (esito in fondo alla sezione).

**Cosa si corregge** — `elimina_cliente` accoda `db.delete(p)` sulle prenotazioni (SQL differito al
commit) e poi esegue un **bulk delete** sui pacchetti (SQL immediato). Con `autoflush=False`
(`backend/database.py:28`) l'ordine reale è `DELETE FROM packages` **prima** di `DELETE FROM bookings`:
su MySQL il vincolo `fk_bookings_package_id` rifiuta con errore 1451 → 500 al pannello, cliente non
cancellato. È l'endpoint che implementa il diritto alla cancellazione dell'informativa privacy.

Correzione minima: un `db.flush()` prima dei due bulk delete, che rende vero il commento già presente
a `clients.py:126-127` («I pacchetti si possono rimuovere solo ora: erano referenziati dalle
prenotazioni, eliminate al passo precedente»).

**File** — `backend/routers/admin/clients.py:114-128`.

**Test**
- 📷 `tests/test_percorsi_critici_trasformazione.py:381` `test_cancellare_un_cliente_con_pacchetto_elimina_i_pacchetti_prima_delle_prenotazioni` — asserisce oggi `prima_occorrenza("DELETE FROM packages") < prima_occorrenza("DELETE FROM bookings")`. **Va invertito.**
- 🛡 `tests/test_admin.py:31` `test_elimina_cliente_rimuove_tutti_i_dati_collegati` (cliente con nota, senza pacchetto), `:67`, `:72`.

**Dipende da** — 1 (senza le FK attive il test continuerebbe a passare anche con l'ordine sbagliato,
e la correzione non sarebbe dimostrabile).

**Verifica su MySQL — eseguita il 2026-09-15, esito atteso su entrambi i rami.** Su `vgc_coaching`
(MySQL 9.7.0, collation `utf8mb4_unicode_ci`), con `fk_bookings_package_id` confermato presente, è
stato costruito uno scenario completo — cliente, nota, slot occupato, pacchetto e prenotazione
confermata che lo consuma, più una recensione — e `elimina_cliente` è stato invocato due volte:

- con la sequenza **pre-correzione** (bulk delete dei pacchetti senza flush delle prenotazioni
  accodate): `IntegrityError (1451, 'Cannot delete or update a parent row: a foreign key constraint
  fails (vgc_coaching.bookings, CONSTRAINT fk_bookings_package_id ...)')`, cioè il 500 al pannello con
  il cliente **non** cancellato;
- con il **codice attuale**: 200, `DELETE FROM bookings` allo statement 5 e `DELETE FROM packages` al
  7, nessuna riga residua.

Il difetto non era quindi dedotto dall'ordine degli statement: è stato **osservato** come errore 1451
vero, ed è la prova che il test di fotografia su SQLite non può dare. Le righe di prova sono state
rimosse e l'assenza di orfani in `bookings`, `packages`, `client_notes`, `reviews` è stata verificata.

---

## 3. ✅ B3 — `aggiorna_stato` non è una macchina a stati

**Chiuso** il 2026-09-15, codice e test nello stesso commit. Verifica su MySQL non richiesta:
l'intervento non tocca vincoli, collation né bulk delete, e sia il difetto sia la correzione sono
interamente osservabili sulla suite.

**Cosa si corregge** — `admin/bookings.py` assegna `prenotazione.status = dati.nuovo_stato` senza
guardare lo stato di partenza e libera lo slot a ogni `cancelled`. Due conseguenze:

1. cancellare due volte la stessa prenotazione libera lo slot **di un altro cliente** che nel
   frattempo l'ha preso, aggirando il claim atomico di `booking.py:178-187`;
2. `cancelled → confirmed` è ammesso e non ri-riserva nulla: prenotazione confermata su slot libero.

**Correzione applicata** — due guardie prima dell'assegnazione, invece di una tabella di transizioni
esplicita: la seconda sarebbe stata più lunga senza dire nulla di più.

1. **partenza `cancelled` → 409.** Una prenotazione cancellata ha già rilasciato il proprio slot e non
   conserva alcun diritto su di esso: qualunque cambio di stato successivo va rifiutato. Una sola
   guardia chiude entrambe le conseguenze sopra.
2. **`nuovo_stato` uguale allo stato attuale → 409**, invece di un 200 silenzioso: due clic sullo
   stesso bottone di solito significano che la lista a schermo è vecchia, e il coach deve saperlo.

Restano ammesse `confirmed → cancelled`, `confirmed → no_show`, `no_show → confirmed` (il coach
corregge un errore; lo slot è già occupato da questa stessa prenotazione, quindi non c'è niente da
ri-riservare) e `no_show → cancelled`. `libera_slot_prenotazione` è rimasta dov'era: è la prima
guardia a renderla sicura, perché quando ci si arriva lo stato di partenza è `confirmed` o `no_show`,
cioè lo slot che si libera appartiene ancora a questa prenotazione. Il commento sopra la chiamata lo
dichiara, così la dipendenza non si perde alla prossima modifica.

`cancelled → confirmed` è **rifiutata, non ri-riservata**: ri-riservare significherebbe riscrivere qui
il claim atomico di `booking.py:178-187`, gestire il caso «slot nel frattempo occupato» e decidere
cosa fare dell'evento Google Calendar già cancellato — molto codice in un endpoint usato poche volte
al giorno. Per rimettere in piedi una prenotazione cancellata si rifà la prenotazione dal flusso
normale, che lo slot lo riserva davvero.

**Perché 409 e non 400** — la richiesta è ben formata e sarebbe stata valida un minuto prima: l'unica
cosa cambiata è lo stato della risorsa, che è la definizione di `409 Conflict`. Serve anche al **24**:
il wrapper unico attorno a `fetch` potrà distinguere `401` (rifai login), `409` (i dati a schermo sono
vecchi, ricarico la lista) e `400`/`422` (richiesta sbagliata) — e il ramo intermedio, che è quello
che risolve il problema da solo, si può scrivere solo se il 409 è distinguibile.

**File** — `backend/routers/admin/bookings.py:105-120`. Il percorso self-service
(`backend/routers/booking.py:281-307`) fa già il controllo giusto a `:298-299` e **non è stato
toccato**: è il pannello l'anello debole.

**Test** — invertiti nello stesso commit, con i commenti `COMPORTAMENTO SOSPETTO` sostituiti dalla
motivazione del rifiuto:
- 📷 → 🛡 `tests/test_percorsi_critici_trasformazione.py:293`, rinominato `test_cancellare_due_volte_non_tocca_lo_slot_di_un_altro_cliente`: la seconda cancellazione risponde 409, lo slot del secondo cliente resta occupato e la sua prenotazione `confirmed`.
- 📷 → 🛡 `tests/test_percorsi_critici_trasformazione.py:328`, rinominato `test_riportare_a_confermata_una_prenotazione_cancellata_viene_rifiutato`: 409, la prenotazione resta `cancelled`.
- 🛡 `tests/test_percorsi_critici_trasformazione.py:263` (cancellazione normale) e `:279` (`no_show` non rimette in vendita) — verdi senza modifiche.
- 🛡 `tests/test_admin.py:224`, `:255` — verdi senza modifiche.

Suite dopo la correzione: `186 passed`, copertura di `backend/` al 90%. Nessuna `assert` toccata
fuori dalle due di fotografia.

**Dipende da** — niente. Si poteva fare anche prima del 2.

**Debito aperto, deliberato** — `booking.py:299` rifiuta il caso gemello sul percorso self-service
(«prenotazione non attiva») con un **400**, quindi lo stesso concetto ha ora due codici in due
endpoint. L'allineamento a 409 è stato valutato e **rimandato**, non scartato: costa una riga di
codice e una riga di test (`tests/test_booking.py:557`, l'unico che lo asserisce) ed è invisibile al
frontend, che a `app.js:199-203` guarda `res.ok` e mostra il `detail` senza leggere il numero.
Separato il ramo `:301` («sessione già passata»), che è privo di test e va trattato con la procedura
della Fascia D — prima il test, poi la modifica.

**Nota** — `frontend/js/admin.js:427-441` non mostra alcun errore: il pannello ora riceve un 409 e
continua a comportarsi come se tutto fosse andato bene — ricarica la lista e tace. È il difetto R3
(intervento 24), che diventa più visibile ma non più grave: il coach non vede il rifiuto, ma lo slot
del cliente subentrato non viene più rimesso in vendita, che era il danno vero.

---

## 4. B2a — Sblocco degli slot: endpoint e riapertura automatica

**Cosa si corregge** — `blocked_external` e `blocked_admin` vengono scritti **solo a `True`**: in
tutto `backend/` non esiste una riga che li riporti a `False`. Un errore di sincronizzazione o una
settimana di ferie inserita per sbaglio toglie quegli orari dalla vendita **per sempre**, e l'unico
rimedio è un `UPDATE` a mano sul database di produzione.

**File** — `backend/routers/admin/availability.py` (nuovo endpoint di sblocco; e `:213-230`
`elimina_blocco_eccezionale`, il cui docstring rimanda a un "a mano" che non esiste),
`backend/services/calendar_service.py:204-227` (la query di sync esamina solo gli slot con
`is_available == True`: va estesa a quelli con `blocked_external=True` se si sceglie la riapertura
automatica). Nessuna migrazione: le colonne esistono già.

**Test**
- 📷 `tests/test_percorsi_critici_trasformazione.py:188` `test_lo_slot_bloccato_non_viene_riaperto_quando_levento_sparisce` — **da invertire** se si sceglie la riapertura automatica.
- 📷 `tests/test_percorsi_critici_trasformazione.py:218` `test_uno_slot_bloccato_non_e_nemmeno_eliminabile_se_ha_uno_storico` — resta vero (preservare lo storico è corretto); va aggiornato il commento, che oggi motiva l'`assert` con l'impossibilità di sbloccare.
- 📷 `tests/test_availability.py:334` `test_elimina_blocco_non_riapre_gli_slot_che_aveva_chiuso` — **da invertire** se lo sblocco diventa parte dell'eliminazione del blocco.
- 🛡 `tests/test_percorsi_critici_trasformazione.py:82,102,121,142,162` — la sincronizzazione calendario nel suo complesso.
- 🛡 `tests/test_availability.py:189-334` — i blocchi eccezionali.

**Dipende da** — **decisione P1** (vedi in fondo).

---

## 5. B2b — Sblocco degli slot: il bottone nel pannello

**Cosa si corregge** — `frontend/js/admin.js:855` mostra il pulsante 🗑 Elimina **solo** quando
`s.disponibile` è vero: proprio gli slot bloccati non hanno alcun bottone. Senza questo intervento,
l'endpoint del 4 esiste ma non è raggiungibile dall'interfaccia.

**File** — `frontend/js/admin.js:845-861`, `frontend/admin.html` se serve un secondo bottone.

**Test** — ⚠️ **scoperto e non copribile**: il progetto non ha alcuna attrezzatura di test JavaScript
(nessun `package.json`, nessun runner). Verifica manuale sul pannello, da dichiarare nel messaggio di
commit.

**Dipende da** — 4.

---

# Fascia B — RISCHIOSO coperto da test esistenti

## 6. R17 — La cache delle credenziali Google è indicizzata solo sul refresh token

**Cosa si corregge** — `_credenziali_cache` usa il refresh token come chiave. Se `GMAIL_REFRESH_TOKEN`
e `DRIVE_REFRESH_TOKEN` sono entrambi assenti, le due chiamate condividono la chiave `None` e la
seconda riceve l'oggetto della prima: la sonda Drive riporterebbe l'errore di Gmail e suggerirebbe
`reauth_drive.py` per un problema che sta altrove — esattamente ciò che `CredenzialeSorvegliata`
(`scheduler.py:56-66`) dichiara di voler evitare.

**File** — `backend/services/google_oauth_service.py:23,33,42` (chiave composita
`(refresh_token, client_id)` e/o rifiuto esplicito di un `refresh_token` `None`). Cinque righe, un file.

**Test** — 🛡 `tests/test_email_service.py:148` `test_healthcheck_gmail_non_interroga_lapi_gmail`,
`:164` `test_healthcheck_drive_usa_il_proprio_refresh_token`, `:180`, `:191`. Il `:164` è quello che
verifica proprio la separazione fra le due credenziali.

**Dipende da** — niente. È l'intervento con il miglior rapporto fra rischio e superficie: primo della fascia.

---

## 7. R5 — `calendar_event_id` azzerato anche quando l'evento non è stato cancellato

**Cosa si corregge** — `elimina_evento_calendario` non restituisce nulla e cattura ogni eccezione: un
fallimento è indistinguibile da un successo, ma `libera_slot_prenotazione` azzera comunque l'id.
L'applicazione perde l'unico riferimento a un evento che resta sul calendario del coach.

Correzione: far restituire un booleano a `elimina_evento_calendario` e azzerare l'id solo in caso di
successo, lasciandolo altrimenti per un tentativo successivo.

**File** — `backend/services/calendar_service.py:234-244`, `backend/services/booking_service.py:20-22`,
e i tre chiamanti: `backend/routers/booking.py:304`, `backend/routers/admin/bookings.py:117`,
`backend/routers/admin/clients.py:118`.

**Test**
- 📷 `tests/test_percorsi_critici_trasformazione.py:351` `test_lidentificativo_dellevento_viene_azzerato_anche_se_google_non_risponde` — **da invertire**: con Google irraggiungibile l'id deve **sopravvivere**, mentre lo slot va comunque liberato.
- 🛡 `tests/test_booking.py:442` `test_cancellazione_self_service_libera_entrambi_gli_slot`, `:540` `test_doppia_cancellazione_rifiutata`.

**Dipende da** — niente. **Sblocca** — 12.

---

## 8. R7 — L'anonimizzazione GDPR lascia i dati personali nelle note

**Cosa si corregge** — `anonimizza_clienti_inattivi` azzera i campi di `users` ma non tocca
`client_notes.nota`, `bookings.note_cliente` e `bookings.note_admin`: testo libero che può contenere
nome e contatti, e che resta attribuibile via `user_id`/`booking_id`. Il docstring del modulo dichiara
che dopo l'anonimizzazione «il cliente collegato smette di essere identificabile»: non è vero.
`elimina_cliente` (`clients.py:127`) le cancella davvero — sono le **due vie** a divergere.

**File** — `backend/services/retention_service.py:43-56`.

**Test**
- 📷 `tests/test_percorsi_critici_trasformazione.py:437` `test_anonimizzare_un_cliente_non_ripulisce_note_e_prenotazioni` — asserisce `"Mario" in nota.nota` e `"Mario Rossi" in prenotazione.note_cliente`. **Da invertire.**
- 🛡 `tests/test_retention.py:38,53,83,103` — le quattro condizioni di anonimizzazione.

**Dipende da** — niente. Nessuna metrica legge le note (`admin/dashboard.py` non le usa), quindi
cancellarle non rompe statistiche.

---

## 9. R6 — Email con maiuscole diverse: 403 incomprensibile, solo in produzione

**Cosa si corregge** — `get_or_create_user` cerca con `User.email == ...` e `create_booking` confronta
in Python, entrambi senza normalizzare. Su MySQL (collation case-insensitive) `Mario@Example.com`
ritrova la riga `mario@example.com`, e il confronto Python successivo fallisce → **403 "user_id and
email do not match"** a un cliente che ha appena scritto la propria email corretta. Su SQLite succede
l'opposto (nascono due utenti), quindi la suite non può vederlo.

Correzione: normalizzare a lowercase in **un punto solo**, il validator di `UserCreate`, coprendo così
`POST /users/`, `/consulenze/` e `/pacchetti-richieste/` insieme; e allineare il confronto in
`booking.py:125`.

**File** — `backend/schemas/users.py:15-21`, `backend/routers/booking.py:125`.

**Test**
- 📷 `tests/test_percorsi_critici_ingresso.py:110` `test_email_con_maiuscole_diverse_crea_un_secondo_utente` — asserisce `primo != secondo` e due utenti. **Da invertire**: un utente solo, su entrambi i motori.
- 🛡 `tests/test_percorsi_critici_ingresso.py:52` `test_registrarsi_due_volte_con_la_stessa_email_non_crea_un_secondo_utente`.
- 🛡 `tests/test_booking.py:208` `test_prenotazione_guest_a_nome_di_un_altro_utente_viene_rifiutata` (protegge il confronto di `booking.py:125`).
- 🛡 `tests/test_richieste.py:12,39,47`.

**Dipende da** — niente.

**Verifica su MySQL** — obbligatoria, ed è l'intervento che ne ha più bisogno di tutti: la collation
locale è `utf8mb4_unicode_ci`, cioè **case-insensitive**, quindi il 403 si riproduce su `localhost`
registrandosi con `mario@example.com` e poi prenotando come `Mario@Example.com`. Su SQLite lo stesso
input produce l'esito **opposto** (due utenti, prenotazione riuscita): qui la suite non è solo muta,
è fuorviante. Prima di procedere, controllare che la collation di Railway coincida con quella locale.

**Da valutare a parte** — una migrazione di normalizzazione per le righe già in produzione, altrimenti
restano duplicati storici. Va fatta **dopo** aver contato le collisioni sul database vero: due righe
che differiscono solo per maiuscole non possono fondersi da sole. Su MySQL case-insensitive le
collisioni non possono esistere per costruzione, quindi il conteggio va fatto su Railway, non in
locale, e potrebbe risultare zero — nel qual caso la migrazione non serve.

---

## 10. R16 — Due job caricano l'intera tabella in memoria

**Cosa si corregge** — `anonimizza_clienti_inattivi` carica **tutti** gli utenti non anonimizzati con
`joinedload` di prenotazioni e pacchetti; `elimina_slot_obsoleti` costruisce un set Python con
**tutti** gli `slot_id` di `bookings` e carica tutti gli slot passati. Crescono senza limite con la
storia del servizio, e il guasto sarebbe silenzioso: `scheduler.py` non notifica le eccezioni di questi
due job. Correzione: query SQL con filtro / `NOT EXISTS`.

**File** — `backend/services/retention_service.py:23-60`,
`backend/services/availability_service.py:109-140`.

**Test** — 🛡 copertura buona e interamente protettiva:
- `tests/test_retention.py:38,53,83,103`
- `tests/test_availability.py:87,94,101,128,140` — in particolare `:101`
  `test_elimina_slot_obsoleti_preserva_slot_con_prenotazione_cancellata` e `:140`
  `test_elimina_slot_rifiuta_slot_secondario_di_una_sessione_da_2h`, che sono le due condizioni facili
  da perdere riscrivendo in SQL.

**Dipende da** — niente. Da fare **dopo il 8**, che tocca la stessa funzione: due modifiche non
correlate sulla stessa riga vanno separate nel tempo, non raggruppate.

**Verifica su MySQL** — necessaria: è l'intervento che sostituisce cicli Python con SQL, cioè l'unico
che introduce costrutti (`NOT EXISTS`, sottoquery correlate) il cui piano di esecuzione e la cui
sintassi accettata differiscono fra i due motori. Una suite verde su SQLite dice poco; le due funzioni
si possono invocare a mano contro il MySQL locale.

---

## 11. R4a — Nessun timeout sulla chiamata a Google Calendar

**Cosa si corregge** — `googleapiclient` usa il timeout di default del socket, cioè nessuno, mentre il
webhook Discord (`discord_service.py:47`, `timeout=5`) e lo scambio OAuth (`discord_auth.py:114`,
`timeout=10`) lo impostano. Un timeout esplicito è un cambio locale e non modifica il flusso.

**File** — `backend/services/calendar_service.py:48-50`.

**Test** — 🛡 `tests/test_percorsi_critici_uscita.py:156` `test_levento_sul_calendario_viene_creato_in_ora_italiana_dichiarata`, `:190` `test_se_google_calendar_fallisce_la_prenotazione_resta_senza_evento`.

**Dipende da** — niente. È la metà economica di R4: va fatta anche se il 12 venisse rimandato.

---

## 12. R4b — Creare l'evento dopo il commit, non dentro la transazione

**Cosa si corregge** — l'ordine in `create_booking` è `UPDATE slots SET is_available=0` →
`crea_evento_calendario(...)` → `db.commit()`. L'`UPDATE` non committato tiene un **lock di riga** su
`slots` per tutta la durata della chiamata HTTP a Google: se l'API è lenta, le richieste concorrenti
sullo stesso slot si accodano sul lock e le connessioni del pool si esauriscono. Il commento a
`booking.py:211-212` copre il caso "errore", non il caso "lenta", che è quello che consuma risorse.

Correzione: spostare la creazione dell'evento **dopo** il commit, insieme alle notifiche
(`booking.py:250-276`), aggiornando `calendar_event_id` con una seconda scrittura.

**File** — `backend/routers/booking.py:213-246`.

**Test** — 🛡 `tests/test_percorsi_critici_uscita.py:156,190`; `tests/test_booking.py:52,90,116`.

**Dipende da** — **7** (cambia il significato di `calendar_event_id`, che con questa modifica è
temporaneamente `None` anche nel percorso felice: le due modifiche vanno lette insieme) e **11**
(il timeout va messo prima, così se il 12 venisse abbandonato il rischio è comunque ridotto).

---

## 13. R11 — Lo scheduler gira senza fuso orario esplicito

**Cosa si corregge** — `BackgroundScheduler()` senza `timezone=` usa il fuso locale del processo. La
conseguenza vera non è l'orario ma che la generazione degli slot dipende da `date.today()`
(`availability_service.py:65`) confrontata con `ultimo_giorno_mese`: nella notte dell'ultimo giorno del
mese il job delle 03:00 UTC lavora su una data che in Italia è già il giorno dopo, e la finestra "fino
a fine mese" si sposta di un giorno rispetto a quello che il coach vede nel pannello (tutto in ora di
Roma). Genera uno slot in meno o in più al confine del mese, in modo non riproducibile.

**File** — `backend/scheduler.py:350`, `backend/services/availability_service.py:65`.

**Test** — 🛡 `tests/test_scheduler.py:416` `test_credenziali_e_backup_girano_una_volta_a_settimana`,
`:425` `test_le_credenziali_si_controllano_prima_del_backup`, `:440`
`test_gli_altri_job_notturni_restano_giornalieri`; `tests/test_availability.py:60,189-259`
(costruiscono date di riferimento e vanno **riletti**, non solo eseguiti).

**Dipende da** — **decisione P2**. `CLAUDE.md` lo elenca fra i punti da non toccare senza chiedere:
sposta l'orario reale di esecuzione di **tutti** i job (03:00 UTC → 03:00 Roma, cioè 01:00 o 02:00 UTC).

**Verifica su MySQL** — utile ma parziale: il difetto si manifesta al **confine del mese**, e né la
suite né una prova locale lo riproducono senza forzare la data di sistema. Il MySQL locale serve qui
solo a confermare che i `DateTime` naive continuino a essere scritti in UTC come prima; il resto
resta una verifica per ragionamento, non per esecuzione.

---

## 14. R1+R2 — L'identità dell'ospite è la sua email, e l'email è pubblica

**Cosa si corregge** — due facce dello stesso difetto, da trattare in un solo intervento perché la
decisione che li risolve è la stessa:

- **R1** — `POST /users/` è pubblico e si comporta da *get or create*: **restituisce l'id di un utente
  preesistente** a chiunque conosca l'email. Chi ha l'email ha quindi entrambi i valori che
  `booking.py:125` confronta, e può prenotare a nome della vittima: consuma il suo limite di
  prenotazioni, le manda email di conferma e occupa slot reali. Il commento a `booking.py:99-109`
  dichiara un costo dell'attacco ("conosci già l'email della vittima") che il codice non alza.
- **R2** — il limite di 2 prenotazioni attive è per `user.id`, e una seconda email crea un secondo
  utente: per gli ospiti — l'unico flusso in cui il rischio esiste — non impedisce nulla.

**File** — dipende dalla decisione. Minimo difendibile: `backend/routers/users.py:104-137`,
`backend/routers/booking.py:110-126,153-165`, `frontend/js/app.js:483-545` (che si aspetta **sempre**
un id e si romperebbe se `POST /users/` smettesse di restituirlo).

**Test**
- 📷 `tests/test_percorsi_critici_ingresso.py:70` `test_chi_conosce_lemail_di_un_cliente_ne_ottiene_lid_dallendpoint_pubblico` — **da invertire**.
- 📷 `tests/test_percorsi_critici_ingresso.py:89` `test_si_puo_prenotare_a_nome_di_un_altro_conoscendone_solo_lemail` — **da invertire**.
- 📷 `tests/test_percorsi_critici_ingresso.py:157` `test_il_limite_di_due_prenotazioni_attive_riparte_da_zero_con_unaltra_email` — **da invertire**, o da riscrivere come documentazione onesta del limite se si sceglie la strada minima.
- 🛡 `tests/test_percorsi_critici_ingresso.py:52`; `tests/test_booking.py:208,233`.

**Dipende da** — **decisione P3**. Se la decisione è "non ora", l'intervento si riduce a rendere onesti
i commenti di `booking.py:99-109` e `:153-155`, che oggi affermano una protezione inesistente: quello
è un commit da fare comunque, e subito.

---

# Fascia C — struttura: sbloccano altri interventi, comportamento invariato

Nessuno dei tre cambia cosa fa il programma: la rete di sicurezza è **l'intera suite**, che deve
restare a 186 verdi senza modificare una sola `assert`. Se una cambia, la modifica non era meccanica.

## 15. D1 — `get_admin` trascina dentro tutto il pannello admin

**Cosa si corregge** — `routers/slots.py:12` e `routers/users.py:20` importano `get_admin` da
`backend.routers.admin`; quell'import esegue `admin/__init__.py`, che in fondo (`:61`) importa i
**sei** sotto-router con i loro model, schemi e servizi. Non è possibile importare il router pubblico
degli slot senza caricare dashboard, analytics, export CSV, moderazione recensioni e il servizio
calendario. Il commento in `admin/__init__.py:8-9` riconosce il problema ma lo tratta come un vincolo.

Correzione: spostare `get_admin` e `oauth2_scheme` in un modulo di dipendenze neutro — `backend/dependencies.py`,
accanto a `backend/rate_limit.py`, che esiste già esattamente per questa ragione. Rimuove anche la
necessità dell'import in fondo al file.

**File** — `backend/routers/admin/__init__.py`, i 6 sotto-router, `backend/routers/slots.py:12`,
`backend/routers/users.py:20`, `tests/conftest.py:30` se cambia il punto di import.

**Test** — 🛡 intera suite; in particolare `tests/test_auth.py:127,141` (separazione dei due tipi di
token) e ogni test che usa `admin_headers()`.

**Dipende da** — niente. **Sblocca** — 16.

---

## 16. D2 — Router che importano router

**Cosa si corregge** — `booking.py:27` importa `get_studente`/`get_studente_opzionale` da
`routers/users.py`; `consulenza.py:14` e `pacchetti_richieste.py:14` importano `get_or_create_user`;
`discord_auth.py:23` importa `STUDENT_TOKEN_COOKIE`. Il router degli utenti è di fatto un modulo di
servizio ma vive in `routers/` e importa a sua volta `get_admin`: la catena
`booking → users → admin → 6 sotto-router` si percorre a ogni import.

**File** — `backend/routers/users.py:32-56,104-126` e i quattro router che importano da lì; stesso
`backend/dependencies.py` creato al 15.

**Test** — 🛡 intera suite.

**Dipende da** — **15**: è la stessa catena, e farlo prima significherebbe smontarla due volte.

---

## 17. D3 — Lo scheduler legge otto variabili d'ambiente a livello di modulo

**Cosa si corregge** — `scheduler.py:35-47` legge otto env var all'import, cioè anche quando il server
non viene avviato (`tests/conftest.py:27` importa `backend.main`). L'import non tocca database né
rete, quindi non è un difetto di correttezza; è però la ragione per cui `REMINDER_HOURS_BEFORE`,
`PUBLIC_BASE_URL` e compagnia sono **congelati all'import** e un test che voglia cambiarli deve
ricaricare il modulo. Correzione: leggerle dentro `avvia_scheduler`.

**File** — `backend/scheduler.py:35-47` e i punti che le usano (`:120,180,194,354,360,366`). Non tocca
`main.py`.

**Test** — 🛡 `tests/test_avvio.py:64` `test_import_non_avvia_scheduler_ne_esegue_migrazioni` (protegge
proprio l'assenza di effetti all'import); `tests/test_scheduler.py` per intero.

**Dipende da** — **13**, che tocca la stessa regione del file (`:35-47` e `:350`). Farli nell'ordine
opposto significherebbe riscrivere due volte le stesse righe.

---

# Fascia D — RISCHIOSO scoperto: il test va scritto prima

> Tutti gli interventi di questa fascia richiedono **due commit**: prima il test, poi la correzione.
> Dove il test non è scrivibile con l'attrezzatura attuale, è detto esplicitamente e la verifica resta
> manuale — da dichiarare nel messaggio di commit, non da lasciare implicita.

## 18. R12 — Percorsi relativi obbligano ad avviare il processo dalla radice

**Cosa si corregge** — `main.py:89` (`Config("alembic.ini")`), `:162`
(`StaticFiles(directory="frontend")`), `:190,194,198,202` (`FileResponse("frontend/*.html")`) sono
relativi alla **directory di lavoro**, non al file. Avviato altrove il server parte lo stesso: le
migrazioni falliscono nel `try` con un alert Discord, `/` risponde 404 e `/static` solleva al mount.
Nulla nel codice dichiara il vincolo, e `nixpacks.toml:5` non fissa una `WORKDIR`.
Correzione: derivare i percorsi da `Path(__file__).resolve().parent.parent`. Sei righe, un file.

**File** — `backend/main.py:89,162,190,194,198,202`.

**Test** — ⚠️ **scoperto ma scrivibile**. `tests/test_avvio.py` ha già il meccanismo giusto: esegue
l'import in un sottoprocesso, con `cwd=RADICE_PROGETTO`. Il test nuovo è lo stesso schema con un `cwd`
**diverso** (una `tmp_path`), che verifica che l'app si costruisca e che `/` serva l'HTML. Oggi
fallirebbe; dopo la correzione passa.

**Dipende da** — niente.

---

## 19. R13 — `hash_admin_password.py` può lasciare due `ADMIN_PASSWORD_HASH` nel `.env`

**Cosa si corregge** — lo script mantiene una **copia** della logica di `_env_utils.aggiorna_env_locale`
per gestire la migrazione dalla vecchia riga in chiaro, e il ramo legacy sostituisce
`ADMIN_PASSWORD=...` con `ADMIN_PASSWORD_HASH=...` **senza verificare se una riga
`ADMIN_PASSWORD_HASH=` esista già**. In un `.env` che le contiene entrambe — lo stato intermedio della
migrazione — il risultato ha due righe: `python-dotenv` tiene l'ultima, cioè la vecchia, e **la nuova
password non funziona senza alcun segnale**.

Collaterale: `_env_utils.py:26` passa il valore come stringa di sostituzione a `re.subn`, dove `\` e
`\g` sono sequenze speciali. Hash bcrypt e refresh token OAuth non contengono backslash, quindi oggi
non si manifesta — ma è una trappola latente. Correzione: `re.escape` o sostituzione con `lambda`.

**File** — `scripts/hash_admin_password.py:60-85` (ridotto a una sola chiamata),
`scripts/_env_utils.py:12-41`. Nessun codice applicativo.

**Test** — ⚠️ **scoperto ma scrivibile**: `scripts/` non ha oggi **nessun** test. `aggiorna_env_locale`
è una funzione pura su file, testabile con `tmp_path`: un `.env` con entrambe le righe, la chiamata,
e l'asserzione che la riga risultante sia una sola e sia quella nuova. Più un caso con un valore che
contiene `\g<1>`.

**Dipende da** — niente.

---

## 20. R14 — Nel pannello convivono due formati di data e due fusi orari

**Cosa si corregge** — il backend converte in ora di Roma e formatta `gg/mm/aaaa hh:mm` per
prenotazioni, clienti, recensioni e slot; per le **note cliente** (`ClientNoteResponse`) e i
**pacchetti** (`PackageResponse`) restituisce il `datetime` naive così com'è, e il JS lo taglia con
`.replace('T',' ').slice(0,16)` → `aaaa-mm-gg hh:mm`, **in UTC**. Nella stessa schermata
"Registrato il 08/09/2026 14:30" (Roma) sta accanto a "2026-09-08 12:30" (UTC) per lo stesso istante.
Il commento che spiega perché («lo sfalsa di un'ora d'inverno e di due d'estate») è ripetuto tre volte
nel backend: la correzione è stata applicata a tre viste su cinque.

**File** — `backend/routers/admin/clients.py:136-174`, `backend/routers/admin/packages.py:19-25`,
`backend/schemas/client_note.py`, `backend/schemas/package.py`,
`frontend/js/admin.js:599-604,729-737,1013-1024` (anche il formato dei blocchi, `aaaa-mm-gg`).

**Test** — ⚠️ **scoperto ma scrivibile**, e il modello esiste già:
`tests/test_admin.py:318` `test_data_creazione_prenotazione_in_ora_italiana` e `:340`
`test_data_registrazione_cliente_in_ora_italiana` fanno esattamente questo per le due viste già
corrette. Il test nuovo è lo stesso schema applicato a note e pacchetti. La metà frontend (`admin.js`)
resta a verifica manuale.

**Dipende da** — niente.

---

## 21. Superficie pubblica di `/docs`, `/redoc`, `/openapi.json`

**Cosa si corregge** — `backend/main.py:129` costruisce `FastAPI(...)` senza `docs_url`, `redoc_url` né
`openapi_url`: le tre rotte di default sono **attive e senza autenticazione**. Non espongono dati né
credenziali, ma pubblicano l'intero inventario degli endpoint, compresi quelli admin.

**Provenienza** — è l'unica voce di questo piano che **non** compariva in `PROBLEMI.md`: emerge dalla
nota finale di `DRIFT.md`, dove era registrata come omissione di `AUDIT.md` §2.9.

**File** — `backend/main.py:129` (una riga: `docs_url=None, redoc_url=None, openapi_url=None`, oppure
le tre rotte dietro `Depends(get_admin)`).

**Test** — ⚠️ **scoperto ma scrivibile e banale**: un test che chiama `GET /openapi.json` senza token e
asserisce lo status atteso. Va scritto **prima**, perché fotografa la scelta qualunque essa sia.

**Dipende da** — **decisione P4**.

---

## 22. R9 — Il prezzo delle sessioni è scritto in tre posti indipendenti

**Cosa si corregge** — il server decide il prezzo (giustamente), ma il riepilogo mostrato al cliente
prima della conferma viene da `data-price` nell'HTML e dallo stato JS. Cambiando il listino nel backend,
il cliente vede il vecchio importo in `summary-price`, conferma quella cifra, e riceve l'email di
conferma con l'importo **nuovo**. È una discrepanza visibile al cliente nel momento dell'acquisto.

**File** — `backend/routers/booking.py:38`, un nuovo endpoint o `backend/schemas/slots.py:60-66`,
`frontend/index.html:190-203`, `frontend/js/app.js:14-31,374-388,402-406`.

**Test** — ⚠️ **parziale**: 🛡 `tests/test_percorsi_critici_ingresso.py:134`
`test_il_prezzo_inviato_dal_client_viene_ignorato` protegge la metà che conta (il server decide), e un
test sul nuovo endpoint è banale da scrivere. La metà frontend — che il riepilogo mostri il prezzo
ricevuto e non quello scritto nell'HTML — **non è testabile** con l'attrezzatura attuale.

**Dipende da** — **decisione P5**. L'alternativa minima e onesta, già indicata in `PROBLEMI.md`, è
lasciare il numero duplicato e aggiungere in `booking.py:35-38` il riferimento esplicito ai due punti
del frontend da aggiornare insieme: è un commit da dieci minuti che elimina il modo più probabile di
sbagliare.

---

## 23. R10 — Il vincolo sugli orari delle sessioni da 2 ore è duplicato in due linguaggi

**Cosa si corregge** — `booking.py:44` (`ORE_INIZIO_VALIDE_2H = {15, 17}`) e `app.js:311`
(`const ORE_INIZIO_VALIDE_2H = [15, 17]`) devono restare identici. Se divergono, il frontend mostra
card che il backend rifiuta con 400, o — peggio — nasconde slot prenotabili: il secondo caso è già
costato una regressione, documentata in `app.js:16-23`. Il frontend ricalcola inoltre l'ora italiana
per conto proprio (`Intl.DateTimeFormat` su `Europe/Rome`) mentre il backend usa `ZoneInfo`: due
implementazioni della stessa conversione.

**File** — `backend/routers/booking.py:40-44`, `frontend/js/app.js:300-332`.

**Test** — ⚠️ **parziale**: 🛡 `tests/test_booking.py:116` `test_prenotazione_2_ore_alle_17_e_permessa`
e `:132` `test_prenotazione_2_ore_alle_16_e_rifiutata` proteggono la regola lato server. La metà
frontend non è testabile.

**Dipende da** — **22**: stessa strada (far arrivare la regola dal server), stesso endpoint.

---

## 24. R3 — Il pannello admin non controlla mai l'esito delle richieste

**Cosa si corregge** — nessuna delle 26 chiamate `fetch` di `admin.js` guarda `res.ok`. Il token admin
dura 480 minuti e vive solo in memoria; alla scadenza ogni endpoint risponde 401. Nelle **letture** il
pannello fa `dati.items` su un oggetto d'errore → eccezione → `catch` che scrive solo in console: in
pagina non compare nulla, e il coach vede un pannello che sembra dire "non ci sono prenotazioni".
Nelle **scritture** è peggio: `aggiornaStato` ricarica la lista come se avesse funzionato. `creaSlot`
è il caso più netto — un 400 "Questo slot si sovrappone" o un 422 sulla durata **spariscono senza
traccia**, e l'interfaccia si comporta esattamente come in caso di successo.

Correzione: un wrapper unico attorno a `fetch` che controlli `res.ok`, gestisca il 401 chiamando
`logout()` (`:139-143`) e mostri il `detail`. Meccanico e concentrato in un file.

**File** — `frontend/js/admin.js` (letture `:247,308,345,469,709,752,816,898,994`; scritture
`:432,454,801,980,1075,1095`). Nessun impatto sul backend.

**Test** — ⚠️ **scoperto e non copribile**: nessuna attrezzatura JS nel progetto. Verifica manuale, da
dichiarare nel commit.

**Dipende da** — niente. Diventa più utile dopo il **3**, che comincia a restituire errori veri al
pannello.

---

## 25. R8 — Errori silenziosi nel frontend pubblico

**Cosa si corregge** — `controllaPacchettoAttivo` (`app.js:412-437`) ha un `catch` **vuoto** che
assume "nessun pacchetto utilizzabile", ma cattura anche rete giù e 500: uno studente che **ha** un
pacchetto pagato non vede il checkbox e prenota a 20 €/ora invece che a credito, senza alcun messaggio.
`loadBookingHistory` (`:152-160`) restituisce `[]` su qualsiasi errore: lo storico sparisce dalla barra
di login e con esso il pulsante "Cancella", cioè la cancellazione self-service. Il terzo caso
(`about.js:35-38`, vetrina recensioni) è dichiarato nel commento ed è accettabile: **non va toccato**.

Correzione: distinguere `!res.ok` (condizione applicativa) da `catch` (guasto) nei due punti, e
mostrare un avviso nel secondo caso.

**File** — `frontend/js/app.js:152-160,412-437`.

**Test** — ⚠️ **scoperto e non copribile**. Verifica manuale.

**Dipende da** — niente.

---

## 26. R15 — I messaggi d'errore mostrati al pubblico sono in una lingua sola

**Cosa si corregge** — il sito pubblico è bilingue (`i18n.js`), ma i `detail` del backend sono stringhe
fisse mostrate **così come arrivano**: un visitatore con l'interfaccia in italiano che tenta di
cancellare una prenotazione passata riceve "This session has already happened, it can no longer be
cancelled". La pagina recensione è interamente in inglese hard-coded e `frontend/recensione.html` non
carica nemmeno `i18n.js`: è l'unica pagina monolingua del sito, ed è quella che riceve i clienti dal
link email.

**File** — `backend/routers/booking.py` (≈20 stringhe), `frontend/js/app.js:196-212`,
`frontend/js/recensione.js` per intero, `frontend/recensione.html` (aggiungere `i18n.js`), chiavi in
`frontend/js/i18n.js`.

**Test** — ⚠️ **scoperto e non copribile** nella parte che conta. Se si sostituiscono i `detail` con
codici, i test che asseriscono lo **status** restano validi; nessun test asserisce oggi il testo dei
`detail`, quindi la sostituzione è sicura lato backend.

**Dipende da** — niente. È l'intervento con più superficie della fascia: valutare se limitarsi a
`recensione.html`, che è il punto di attrito reale.

---

# Fascia E — cosmetico

## 27. C2 — Import locale giustificato da un ciclo che non esiste

`calendar_service.py:198-200` importa localmente con il commento *"Import locale per evitare un ciclo"*.
Ma `models/slots.py` importa solo `backend.database`, e non c'è nessun percorso che riporti da `models`
a `calendar_service`: un import in cima al file funzionerebbe, come già fa `availability_service.py:11`.
Il commento scoraggia attivamente dal sistemarlo.
**File** — `backend/services/calendar_service.py:198-200`. **Test** — 🛡 `tests/test_percorsi_critici_trasformazione.py:82-162`.

## 28. C3 — La sonda delle credenziali chiede due access token invece di uno

`credenziali_oauth_google` fa già `refresh()` se il token non è valido (`:44-45`);
`verifica_credenziali_google` ne chiama un secondo esplicito (`:81`). Il secondo è **voluto** e il
docstring lo spiega, ma nel percorso "cache vuota" — il primo controllo dopo ogni riavvio — se ne fanno
due di fila. Correzione: un parametro `forza_refresh`, oppure lasciare com'è e correggere il commento.
**File** — `backend/services/google_oauth_service.py:44-45,81`. **Test** — 🛡 `tests/test_email_service.py:123,130,139`.

## 29. C4 — Commenti e segnaposto che descrivono qualcosa di diverso dal codice

Quattro stringhe, un commit solo (escluso l'ultimo punto, che è il 35):
- `app.js:428-432` + `i18n.js:84,217`: il segnaposto si chiama `{used}` ma riceve
  `sessioni_residue`. Il testo mostrato è corretto; il nome dice il contrario del valore.
- `availability_service.py:28-31`: *"nessuna sessione dura più di 6 ore"* giustifica `margine = 6h`, ma
  la durata massima è 2 ore.
- `scheduler.py:401-402`: *"Sfalsato di un minuto per non sovrapporlo al job precedente"* — il job che
  lo precede **nel file** gira la domenica alle 03:30; quello da cui è realmente sfalsato è
  `genera_slot_giornaliero`, scritto più sopra.

**Test** — nessuno: sono stringhe e commenti.

## 30. C1a — `prezzo_pieno_cents` non è letto da nessun modulo

`package_service.py:13,20,27` definisce 8000/16000/24000, mai letti (verificato su tutto il repo). I
prezzi barrati del sito sono scritti a mano in `index.html:368,380,392`.
**File** — `backend/services/package_service.py:7-29`. **Test** — 🛡 `tests/test_booking.py:269,340`, `tests/test_richieste.py:47,62`.

## 31. C1b — `GET /users/` non è chiamato da nessuna pagina

Nessun frontend lo chiama, nessun test lo esercita, e restituisce `UserResponse` completo — nome,
email, telefono, Discord — di **tutti** i clienti. Superficie di attacco senza contropartita.
**File** — `backend/routers/users.py:59-61`. **Test** — nessuno oggi; l'assenza è proprio ciò che rende la rimozione sicura.

## 32. C1c — `alembic/env.py` importa 6 model su 8

Mancano `Package` e `Review`. Innocuo, perché `from backend.models import ...` esegue l'intero
`backend/models/__init__.py` e registra tutte e otto le tabelle — ma la riga suggerisce una completezza
che non ha, e chi aggiungesse un nono model potrebbe crederla la lista da mantenere.
**File** — `alembic/env.py:14`. **Test** — nessuno; verifica con `alembic check` o una revisione a vuoto.

## 33. C5 — Le stesse etichette scritte in sei posti

I quattro tipi di servizio vivono in `schemas/booking.py:9` (autorevole), `models/booking.py:32`
(commento), `services/discord_service.py:25-30`, `admin.js:181-186`, `i18n.js:56-59,191-194`,
`index.html:172`. Stesso schema per il catalogo pacchetti. Oggi sono allineati — verificato valore per
valore — ma nessuno dei due elenchi frontend può accorgersi di una divergenza: `admin.js:732` e `:381`
degradano al valore grezzo (`|| p.tipo`).
**Test** — ⚠️ parziale: 🛡 `tests/test_percorsi_critici_uscita.py:291` protegge la traduzione lato Discord.
**Dipende da** — **22**: stesso endpoint pubblico. Se il listino non cambia mai, la risposta
proporzionata è un commento incrociato nei sei punti, non un endpoint nuovo.

## 34. C6 — `event` implicito negli handler

`app.js:359` e `admin.js:160` usano la variabile globale `event` dentro un handler invece del
parametro: funziona in tutti i browser attuali ma è deprecato, e in una funzione chiamata non da un
handler (`showSection` invocata da codice) sarebbe `undefined`. Le tre copie di `escapeHtml`
(`about.js:6-10`, `app.js:55-64`, `admin.js:199-210`) sono invece una conseguenza **accettata**
dell'assenza di build step, dichiarata nel commento di `about.js:4-5`: **non vanno unificate**.
**File** — `frontend/js/app.js:359`, `frontend/js/admin.js:160`, più gli `onclick` negli HTML.
**Test** — ⚠️ non copribile.

---

# Fuori fascia: non sono cosmetici, ma non sono difetti

## 35. Lo scope di Google Calendar è più largo del necessario

`calendar_service.py:25` chiede `.../auth/calendar`, cioè accesso pieno. Gli altri due script scelgono
deliberatamente lo scope minimo e lo dichiarano (`reauth_gmail.py:50-53` "SOLO invio",
`reauth_drive.py:43-46` "principio di minimo privilegio"): il service account Calendar non segue la
stessa regola e nessun commento lo giustifica. `calendar.events` basterebbe per insert/list/delete.

**Perché è separato dal 29** — non è una modifica di stringa: richiede di **riautorizzare su Google
Cloud** e di provare con `verifica_credenziali_calendario`. Un errore qui spegne la sincronizzazione
del calendario in produzione, in silenzio (`sincronizza_slot_con_calendario` cattura ogni errore).

**Test** — 🛡 `tests/test_email_service.py:180,191` (la sonda Calendar), che però girano su credenziali
finte: la verifica vera è in produzione, dopo la riautorizzazione.

## 36. C1d — `telefono` e `attiva`: completare o rimuovere

Due colonne a metà. **Non sono pulizia**: rimuoverle richiede una migrazione, completarle è lavoro di
prodotto. Da decidere (**decisione P6**), non da eseguire in automatico.

- `User.telefono` — nessun form lo raccoglie: `app.js:499` invia sempre `telefono: null`, e non esiste
  un campo telefono in `index.html`. La colonna è solo letta (`clients.py:77`) e azzerata
  (`retention_service.py:52`).
- `AvailabilityRule.attiva` — letta da `scheduler.py:230`, mai scritta da un endpoint: non è in
  `AvailabilityRuleCreate`, il router non la valorizza e non esiste un `PATCH` sulla regola. Il
  commento del model lo dichiara per esteso: *"una regola nasce attiva e per sospenderla serve
  intervenire sul database"*. **È l'unica voce di `DRIFT.md` (§1) che sopravvive come fatto di codice.**

---

# Fascia F — documentazione

## 37. `AUDIT.md`: due omissioni che il documento stesso dichiara complete

Dalla nota finale di `DRIFT.md`, con il codice che dà ragione ai documenti oggi cancellati:

- **`/docs`, `/redoc`, `/openapi.json`** non compaiono nell'inventario degli endpoint di §2.9. È
  l'unica superficie HTTP pubblica che l'audit non copre. Da aggiornare **dopo il 21**, così il
  documento registra la decisione presa e non lo stato di allora.
- **`tests/conftest.py`** è descritto in §5 come «sostituisce `get_db` con un SQLite in memoria e
  disattiva il rate limiter»: la riga si legge come una lista completa, ma la fixture autouse
  `integrazioni_esterne_finte` (`:72-100`) sostituisce con no-op **dieci** funzioni di Calendar, email
  e Discord nei tre router che le chiamano. L'omissione è coerente con il perimetro dichiarato
  (`tests/` era fuori), ma la formulazione va corretta. Da aggiornare anche dopo il **1**, che
  aggiunge il `PRAGMA`.

## 38. Documentare l'orizzonte di generazione degli slot

`genera_slot_da_regola` si ferma all'ultimo giorno del **mese corrente**
(`availability_service.py:69`, `calendar.monthrange`), e il job notturno riapre la finestra il primo
del mese. La conseguenza osservabile è che **l'orizzonte prenotabile oscilla**: circa trenta giorni a
inizio mese, quasi zero negli ultimi giorni, poi di colpo di nuovo trenta. Decide quanto in là arriva
il calendario che lo studente vede, cioè cosa si può prenotare.

La scelta è deliberata e spiegata nel docstring della funzione (`:46-52`); manca la sua **conseguenza**,
che non compare oggi in nessun documento — `CLAUDE.md` non la nomina. Una riga in `CLAUDE.md`, sezione
*Convenzioni e vincoli*. Se l'oscillazione fosse giudicata un difetto di prodotto, la correzione starebbe
nel codice (finestra scorrevole a N giorni) e sarebbe una decisione nuova, non un riallineamento.

**Test** — 🛡 `tests/test_availability.py:60` e i test sui blocchi fissano già il comportamento.

---

# Decisioni da prendere prima di aprire l'editor

Sei nodi in cui il codice non basta a scegliere. Ogni intervento che vi dipende è fermo finché non
sono sciolti.

| | Decisione | Blocca |
|---|---|---|
| **P1** | Uno slot bloccato si riapre **da solo** quando l'evento sparisce dal calendario, o solo con un'azione esplicita del coach? La prima è più comoda e più rischiosa (un errore di sincronizzazione rimette in vendita un orario occupato); la seconda richiede che il coach si accorga del blocco. | 4, 5 |
| **P2** | Lo scheduler passa a `timezone=ROME_TZ`? Sposta l'orario **reale** di tutti i job (03:00 UTC → 03:00 Roma). L'alternativa è lasciare i job in UTC e correggere solo `date.today()` in `availability_service.py:65`, che è la causa vera del difetto e non sposta niente. | 13, 17 |
| **P3** | Prenotare resta possibile senza login? Le strade sono tre: login obbligatorio, conferma via email del guest checkout, oppure nessuna delle due e i commenti resi onesti. | 14 |
| **P4** | `/docs`, `/redoc` e `/openapi.json` restano pubblici? | 21, 37 |
| **P5** | Il listino (prezzi e ore valide) arriva dal server, o resta duplicato con riferimenti incrociati espliciti nei commenti? | 22, 23, 33 |
| **P6** | `User.telefono` e `AvailabilityRule.attiva`: completare (form + `PATCH`) o rimuovere (migrazione)? | 36 |

---

# Cosa è decaduto di `DRIFT.md`

`DRIFT.md` confrontava il codice con otto documenti in `_archivio_docs/`. **Quei documenti non
esistono più**: sono stati cancellati nel commit `c8fc0ca` insieme all'aggiunta dei test di
regressione, e `CLAUDE.md` (commit `4599d6f`) li ha sostituiti con un contesto verificato e minimale.
I markdown tracciati oggi sono quattro: `AUDIT.md`, `CLAUDE.md`, `DRIFT.md`, `PROBLEMI.md`.

Di conseguenza **le voci §1–§9 di `DRIFT.md` sono chiuse per cancellazione della fonte**, e nessuna
richiede un intervento sul codice. Restano vive solo tre cose, già assorbite in questo piano:

| Voce di `DRIFT.md` | Esito |
|---|---|
| §1 `AvailabilityRule.attiva` | Vive come fatto di codice → **intervento 36** |
| §2 recensioni a intervallo, §3 backup settimanale, §4 "sei girano ogni giorno", §5 nomi dell'healthcheck, §7 `monitor.yml`, §8 albero dei documenti, §9 conteggio delle variabili | Chiuse: descrivevano documenti cancellati. `CLAUDE.md` e la suite (`test_scheduler.py:416-440`) riportano già il comportamento reale. Nessuna azione. |
| §6 orizzonte "fino a fine mese" | Il fatto non è documentato da nessuna parte → **intervento 38** |
| Nota finale (`/docs`, `conftest.py`) | → **interventi 21 e 37** |

---

# Nota di metodo

Tre difetti di questo piano — **2 (B1)**, **9 (R6)** e, per costruzione, la non osservabilità di
**3 (B3)** — hanno la stessa causa: la suite gira su SQLite in memoria senza chiavi esterne attive e
con confronti di stringa case-sensitive, mentre la produzione è MySQL. Sono esattamente i difetti che
un test, così com'è configurato, **non può vedere** — la stessa dinamica già documentata nel codice per
l'ordinamento degli slot (`backend/routers/slots.py:30-41`: *"è la differenza fra i due database, non
la query, a nascondere il difetto"*).

Per questo l'intervento **1** sta in cima pur non essendo BLOCCA: una riga, e rende visibile la classe
di difetti più costosa da scoprire in produzione. Vale la pena ricordare che nemmeno con le chiavi
esterne attive una suite verde dimostra che il codice funzioni su MySQL: la collation, il
comportamento dei bulk delete e il locking di riga restano diversi.

**Ma il salto non è fra la suite e la produzione.** In mezzo c'è lo sviluppo locale, che gira su un
MySQL vero (vedi *Dove si verifica*, in cima). Quei tre difetti — B1, R6 e la verifica di B3 — sono
quindi riproducibili **oggi, su questa macchina**, senza toccare Railway: quello che manca non è
l'ambiente, è l'abitudine di usarlo. Ogni volta che questo piano dice "non osservabile dai test", la
frase va letta come *"non osservabile dalla suite, osservabile a mano sul MySQL locale"* — mai come
*"osservabile solo in produzione"*.
