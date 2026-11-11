# PIANO

Stato degli interventi. Analisi: `_archivio_audit/PIANO_ANALISI_2026-09.md` (voci 1-45) e
`_archivio_audit/ANALISI_2026-11.md` (verifica del 2026-11-09, voci 46-54, ordine di priorità); dalla 55 i
riferimenti stanno nella riga. Un intervento risolto si cancella da qui nello stesso commit che lo risolve, dove sta il dettaglio.

Decisioni (P1-P6: dettaglio nell'archivio 2026-09, riga 1328):
- P1 ✅ — Slot bloccati: sblocco esplicito del coach, non riapertura automatica (interventi 4, 5)
- P3 — Prenotare senza login: login obbligatorio, conferma via email, tetto giornaliero o commenti resi onesti (14)
- P4 — `/docs`, `/redoc` e `/openapi.json` restano pubblici? (21)
- P5 — Listino (prezzi, ore valide, etichette) servito dal server, o duplicato con rimandi nei commenti (22, 33)
- P6a — `User.telefono`: campo nel form pubblico o migrazione che lo rimuove (36)
- P6b — `AvailabilityRule.attiva`: `PATCH` nel pannello o migrazione che la rimuove (36)
- P7 — Sessione a pacchetto cancellata, dal cliente o dal pannello: il credito torna? (56)
- P8 — Cosa conta come incassato: sessioni future comprese? pacchetti alla data di vendita? (57)
- P9 — Disponibilità calcolata da regole, blocchi, prenotazioni e impegni Google, non salvata come slot; rivede P1 (60)

Aperti, in ordine di priorità (il numero è l'ordine di scoperta, non il rischio):
- [ ] 40 — Misure su Railway prima del 9: versione, collation, sql_mode, time_zone, IP dietro il proxy, repliche, attesa della CI
- [ ] 9 · R6 — Email con maiuscole: 403 su MySQL, e su ogni motore se il dominio ha maiuscole (EmailStr)
- [ ] 56 — Il credito del pacchetto non torna mai, né alla disdetta né dal pannello, che non può correggerlo (`booking.py:243`; decisione P7)
- [ ] 47 — Job schedulati che falliscono o saltano senza avviso: slot, pulizia, anonimizzazione, backup
- [ ] 61 — Backup su Drive anteriori al deploy del 2026-11-11 (`bbe099b`, SET NAMES): fino al 13/12, quando l'ultimo esce dai 30 giorni,
  il ripristino va fatto con `--default-character-set=utf8mb4` o accenti ed emoji tornano corrotti senza errori. Ricontrollo il 15/11:
  il backup delle 04:00 UTC ha `SET NAMES utf8mb4;` alla riga 4; la voce si chiude il 13/12 se ce l'hanno tutti
- [ ] 46 — Asset statici senza versione né cache-control: dopo un rilascio il browser usa il JS vecchio
- [ ] 24 · R3 — 16 fetch su 26 del pannello admin non controllano res.ok
- [ ] 48 — Rate limit forse unico per tutti dietro il proxy: verificare con la 40, poi FORWARDED_ALLOW_IPS
- [ ] 26 · R15 — Messaggi d'errore pubblici in una lingua sola; recensione.html senza i18n
- [ ] 25 · R8 — Errori silenziosi nel frontend pubblico; ogni errore di prenotazione è lo stesso avviso generico (`app.js:533`)
- [ ] 60 — Sessioni da 2 h solo alle 15 e alle 17 (`booking.py:44`): con la regola 18-22 proposta dal pannello spariscono
- [ ] 20 · R14 — Due formati di data e due fusi orari nel pannello
- [ ] 57 — Tre definizioni di incasso, nessuna conta i pacchetti venduti (`dashboard.py:48-52,135-137`, `clients.py:55-61`; decisione P8)
- [ ] 58 — `created_at` usa `func.now()` negli 8 model: l'ora la decide il fuso di MySQL (in locale Roma), non è UTC
- [ ] 39 — Servizi esterni: email e note nel calendario a ogni prenotazione, e lì restano oltre i 24 mesi; promemoria segnati inviati se falliti
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

Decaduti il 2026-11-09 (motivi nel commit e nell'analisi 2026-11, §4): 10 13 15 16 17 19 28 34 42 43 45; il 37 in bd6d6f0.
Accorpati: 23→22 · 27→29 · 30→33 · 32→29 · 41→40 · 44→14.
