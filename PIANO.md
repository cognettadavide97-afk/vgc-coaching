# PIANO

Stato degli interventi. Analisi: `_archivio_audit/PIANO_ANALISI_2026-09.md` (voci 1-45) e
`_archivio_audit/ANALISI_2026-11.md` (verifica del 2026-11-09, voci 46-54, ordine di priorità).
Un intervento si chiude spuntandolo con il commit e spostandolo fra i chiusi; il dettaglio sta nel commit.

Decisioni (dettaglio nell'archivio 2026-09, riga 1328):
- P1 ✅ — Slot bloccati: sblocco esplicito del coach, non riapertura automatica (interventi 4, 5)
- P3 — Prenotare senza login: login obbligatorio, conferma via email, tetto giornaliero o commenti resi onesti (14)
- P4 — `/docs`, `/redoc` e `/openapi.json` restano pubblici? (21)
- P5 — Listino (prezzi, ore valide, etichette) servito dal server, o duplicato con rimandi nei commenti (22, 33)
- P6a — `User.telefono`: campo nel form pubblico o migrazione che lo rimuove (36)
- P6b — `AvailabilityRule.attiva`: `PATCH` nel pannello o migrazione che la rimuove (36)

Aperti, in ordine di priorità (il numero è l'ordine di scoperta, non il rischio):
- [ ] 40 — Misure su Railway prima del 9: versione, collation, sql_mode, time_zone, IP dietro il proxy, repliche
- [ ] 9 · R6 — Email con maiuscole: 403 su MySQL, e su ogni motore se il dominio ha maiuscole (EmailStr)
- [ ] 47 — Job schedulati che falliscono o saltano senza avviso: slot, pulizia, anonimizzazione, backup
- [ ] 52 — Provare il ripristino di un dump Drive sul MySQL locale: il backup è l'unica copia dei dati
- [ ] 46 — Asset statici senza versione né cache-control: dopo un rilascio il browser usa il JS vecchio
- [ ] 24 · R3 — 16 fetch su 26 del pannello admin non controllano res.ok
- [ ] 48 — Rate limit forse unico per tutti dietro il proxy: verificare con la 40, poi FORWARDED_ALLOW_IPS
- [ ] 26 · R15 — Messaggi d'errore pubblici in una lingua sola; recensione.html senza i18n
- [ ] 25 · R8 — Errori silenziosi nel frontend pubblico
- [ ] 20 · R14 — Due formati di data e due fusi orari nel pannello
- [ ] 39 — Servizi esterni: email e note nel calendario a ogni prenotazione; promemoria segnati inviati se falliti
- [ ] 49 — Input pubblici senza limiti: max_length, a-capo nel nome, token di recensione non ASCII
- [ ] 50 — Email dei clienti nei log: booking_id al posto dell'email
- [ ] 14 · R1+R2 — Identità dell'ospite = email pubblica, limite di prenotazioni aggirabile (decisione P3)
- [ ] 12 · R4b — Creare l'evento Calendar dopo il commit, non nella transazione
- [ ] 11 · R4a — Timeout Google di 60 s, oltre i 50 s di attesa dei lock MySQL: accorciarlo
- [ ] 53 — Railway: variabili sul solo servizio app, GMAIL_HEALTHCHECK_INTERVAL_HOURS, https, MYSQL_PUBLIC_URL
- [ ] 22 · R9 — Prezzi e ore valide duplicati fra backend e frontend (decisione P5)
- [ ] 33 · C5 — Etichette, pacchetti e prezzi barrati scritti in più posti (decisione P5)
- [ ] 51 — Test che possono chiamare il Google vero: .env caricato all'import, fixture solo sui router pubblici
- [ ] 29 · C4 — Commenti che dicono altro dal codice, rimandi a documenti cancellati, motivazioni perse (§6)
- [ ] 18 · R12 — Percorsi relativi: il sito non parte se avviato fuori dalla radice
- [ ] 35 — Scope Google Calendar ridotto a calendar.events (serve riautorizzare)
- [ ] 21 — /docs, /redoc e /openapi.json pubblici (decisione P4)
- [ ] 31 · C1b — GET /users/ non è chiamato da nessuna pagina
- [ ] 36 · C1d — telefono e attiva: completare o rimuovere (decisioni P6a, P6b)
- [ ] 54 — File inutili nel codice: Werkzeug in requirements.txt, alembic/README, regola obsoleta in .gitignore

Chiusi:
- [x] 1 — Chiavi esterne attive nella suite di test (commit e3b52f5)
- [x] 2 · B1 — Cancellare un cliente con pacchetto dà 500 per la FK package_id (commit ec62a89)
- [x] 3 · B3 — Il cambio di stato della prenotazione diventa una macchina a stati (commit 7af28c8)
- [x] 4 · B2a — Endpoint di sblocco esplicito degli slot bloccati (commit dab88f5)
- [x] 5 · B2b — Bottone di sblocco degli slot nel pannello admin (commit b348c30)
- [x] 6 · R17 — Cache delle credenziali Google indicizzata su (refresh_token, client_id) (commit aee536b)
- [x] 7 · R5 — calendar_event_id azzerato solo se Google conferma la cancellazione (commit 90062f9)
- [x] 8 · R7 — L'anonimizzazione GDPR copre anche note e prenotazioni (commit 132a5a2)
- [x] 38 — Documentare in CLAUDE.md l'orizzonte "fino a fine mese" degli slot (commit 21a2f3c)

Decaduti il 2026-11-09 (motivi nel commit e nell'analisi 2026-11, §4): 10 13 15 16 17 19 28 34 42 43 45; il 37 in bd6d6f0.
Accorpati: 23→22 · 27→29 · 30→33 · 32→29 · 41→40 · 44→14.
