# PIANO

Stato degli interventi. Analisi e motivazioni: `_archivio_audit/PIANO_ANALISI_2026-09.md` (storico).
Un intervento si chiude spuntandolo qui con il commit; il dettaglio sta nel messaggio di commit.

Decisioni (dettaglio nell'archivio, riga 1328):
- P1 ✅ — Slot bloccati: sblocco esplicito del coach, non riapertura automatica (interventi 4, 5)
- P2 — Scheduler a `timezone=ROME_TZ`, o job in UTC correggendo solo `date.today()` (13, 17)
- P3 — Prenotare senza login: login obbligatorio, conferma via email, o commenti resi onesti (14)
- P4 — `/docs`, `/redoc` e `/openapi.json` restano pubblici? (21)
- P5 — Listino (prezzi e ore valide) servito dal server, o duplicato con rimandi nei commenti (22, 23, 33)
- P6a — `User.telefono`: campo nel form pubblico o migrazione che lo rimuove (36)
- P6b — `AvailabilityRule.attiva`: `PATCH` nel pannello o migrazione che la rimuove (36)

- [x] 1 — Chiavi esterne attive nella suite di test (commit e3b52f5)
- [x] 2 · B1 — Cancellare un cliente con pacchetto dà 500 per la FK package_id (commit ec62a89)
- [x] 3 · B3 — Il cambio di stato della prenotazione diventa una macchina a stati (commit 7af28c8)
- [x] 4 · B2a — Endpoint di sblocco esplicito degli slot bloccati (commit dab88f5)
- [x] 5 · B2b — Bottone di sblocco degli slot nel pannello admin (commit b348c30)
- [x] 6 · R17 — Cache delle credenziali Google indicizzata su (refresh_token, client_id) (commit aee536b)
- [x] 7 · R5 — calendar_event_id azzerato solo se Google conferma la cancellazione (commit 90062f9)
- [x] 8 · R7 — L'anonimizzazione GDPR copre anche note e prenotazioni (commit 132a5a2)
- [ ] 9 · R6 — Email con maiuscole diverse: 403 su MySQL, va normalizzata
- [ ] 10 · R16 — Due job notturni caricano l'intera tabella in memoria
- [ ] 11 · R4a — Timeout sulla chiamata a Google Calendar
- [ ] 12 · R4b — Creare l'evento Calendar dopo il commit, non nella transazione
- [ ] 13 · R11 — Lo scheduler gira senza fuso orario esplicito (decisione P2)
- [ ] 14 · R1+R2 — Identità dell'ospite = email pubblica, limite di prenotazioni aggirabile (decisione P3)
- [ ] 39 — Esiti ambigui dei servizi esterni: quattro marcatori senza voce
- [ ] 15 · D1 — get_admin si trascina dietro tutto il pannello admin
- [ ] 16 · D2 — Router che importano router
- [ ] 17 · D3 — Variabili d'ambiente dello scheduler lette a livello di modulo
- [ ] 18 · R12 — Percorsi relativi obbligano ad avviare il processo dalla radice
- [ ] 19 · R13 — hash_admin_password.py può lasciare due ADMIN_PASSWORD_HASH nel .env
- [ ] 20 · R14 — Due formati di data e due fusi orari nel pannello
- [ ] 21 — /docs, /redoc e /openapi.json pubblici (decisione P4)
- [ ] 22 · R9 — Prezzo delle sessioni scritto in tre posti (decisione P5)
- [ ] 23 · R10 — Ore valide delle sessioni da 2h duplicate fra backend e JS
- [ ] 24 · R3 — Il pannello admin non controlla mai res.ok
- [ ] 25 · R8 — Errori silenziosi nel frontend pubblico
- [ ] 26 · R15 — Messaggi d'errore pubblici in una lingua sola
- [ ] 27 · C2 — Import locale giustificato da un ciclo che non esiste
- [ ] 28 · C3 — La sonda delle credenziali chiede due access token
- [ ] 29 · C4 — Commenti e segnaposto che descrivono altro dal codice
- [ ] 30 · C1a — prezzo_pieno_cents non è letto da nessun modulo
- [ ] 31 · C1b — GET /users/ non è chiamato da nessuna pagina
- [ ] 32 · C1c — alembic/env.py importa 6 model su 8
- [ ] 33 · C5 — Le stesse etichette scritte in sei posti
- [ ] 34 · C6 — event implicito negli handler
- [ ] 35 — Scope Google Calendar ridotto a calendar.events (serve riautorizzare)
- [ ] 36 · C1d — telefono e attiva: completare o rimuovere (decisioni P6a, P6b)
- [x] ~~37 — AUDIT.md: due omissioni~~ decaduta, AUDIT.md non si aggiorna
- [x] 38 — Documentare in CLAUDE.md l'orizzonte "fino a fine mese" degli slot (commit 21a2f3c)
- [ ] 40 — Misurare versione e collation del MySQL di Railway, prima del 9 (riga 152)
- [ ] 41 — Contare su Railway le email che differiscono solo per maiuscole; migrazione solo se ce ne sono (riga 723)
- [ ] 42 — booking.py:299 rifiuta con 400 il caso che l'admin rifiuta con 409: allineare (riga 347)
- [ ] 43 — Ramo booking.py:301 «sessione già passata» senza test: prima il test, poi la modifica (riga 352)
- [ ] 44 — Commenti di booking.py:99-109 e :153-155 che dichiarano una protezione inesistente (riga 845)
- [ ] 45 — Il 35 è passato da cosmetico a non cosmetico senza dichiararlo: verificare e registrare la riclassificazione (riga 88)
