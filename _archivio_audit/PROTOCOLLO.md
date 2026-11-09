# Protocollo operativo — coaching-app

Nov 6, 2026 · @Davide

Si lavora direttamente in Claude Code. Questo documento contiene il ciclo da seguire, i prompt da usare e i segnali che impongono di fermarsi.

## Regola zero: una sola fonte di verità

`CLAUDE.md` e `PIANO.md` vincono su qualsiasi conversazione. Se una chat li contraddice, o sbaglia la chat o il file va aggiornato deliberatamente — non si procede sulla base del dialogo contro il documento.

Tutto ciò che viene deciso parlando e deve sopravvivere si scrive in uno dei due **nella stessa sessione**. Quello che resta solo in chat è già perso: la conversazione non è sotto git, non si rigenera, nessuno la riaprirà.

Limiti rigidi: `CLAUDE.md` sotto le 60 righe, `PIANO.md` sotto le 60 righe. Quando sforano non si allarga il limite, si taglia. La lunghezza è l'unica cosa che tiene vero un documento che nessuno rilegge.

I documenti storici — `AUDIT.md`, `PROBLEMI.md`, `DRIFT.md`, `_archivio_audit/` — si leggono e non si scrivono. Si rigenerano, non si aggiornano.

## Il ciclo di intervento

Un intervento per volta, dal primo all'ultimo passo. Non si raggruppano lavori non correlati e non si salta un controllo perché la modifica sembra piccola.

&#91;embedded content: ciclo di intervento · 6 passi, 3 controlli\]

I passi 1, 2 e 3 avvengono in Claude Code. I passi 4, 5 e 6 in Git Bash: l'indipendenza fra chi modifica e chi verifica è il meccanismo che regge tutto il resto.

Il controllo sul diff funziona anche senza leggere il codice, perché quello che valuti è l'ampiezza: se il piano parlava di una funzione e il diff tocca otto file, qualcosa è andato oltre il richiesto.

## Quando fermarsi

Il ciclo si esegue da soli. Ci si ferma e si chiede aiuto solo su questi inneschi, che sono pochi di proposito: una lista lunga diventa «sempre», e allora tanto vale non averla.

- **Una decisione di prodotto.** Le P2–P6b aperte, e quelle che emergeranno. Nessun documento le contiene e nessuno può prenderle al posto tuo.
- **Un diff più ampio di quanto annunciato nel piano.** È il segnale d'allarme più affidabile che hai, e funziona anche senza leggere il codice.
- **Un test che fallisce in un modo che non capisci.** Non tentare di riparare sopra la riparazione: `git checkout -- .` e ripensa il piano.
- **Qualcosa di irreversibile.** Un `git push`, una migrazione sui dati di produzione, una modifica allo schema.
- **Un documento che sfora il suo limite.** 60 righe per `CLAUDE.md`, 60 per `PIANO.md`.
- **La ripresa dopo una pausa lunga.** Non ricostruire a memoria: parti dallo stato reale su disco.

Fuori da questi, esegui e basta.

## Libreria dei prompt

Tienili anche in un `PROMPT.txt` nella cartella del progetto, così li hai sotto mano mentre lavori.

**Chiedere il piano (passo 2)**

> Intervento N di `PIANO.md`. Leggi il contesto in `_archivio_audit/PIANO_ANALISI_2026-09.md`. Descrivimi cosa cambieresti e in quali file. Non scrivere codice. Attendi la mia conferma.

**Se il piano non è chiaro**

> Spiegamelo come se non conoscessi il progetto, con un esempio concreto di cosa succede prima della modifica e cosa dopo.

**Se il diff è più ampio del previsto**

> Il piano annunciava N file e il diff ne tocca M. Spiegami file per file perché ciascuno è necessario a questo intervento. Non modificare nulla.

**Autorizzare (passo 3)**

> Procedi. Solo questo intervento, nient'altro. Al termine esegui la suite e mostrami l'output reale del comando.

**Chiudere (passo 6)**

> Spunta la voce N in `PIANO.md` con il riferimento al commit. Non toccare altre voci.

**Test prima della correzione — obbligatorio per gli interventi 11, 12 e 39**

> Prima di modificare, aggiungi test che documentino il comportamento attuale di questo percorso. Non modificare il codice di produzione. Se il comportamento attuale è sbagliato, scrivi comunque il test che passa con un commento `# COMPORTAMENTO SOSPETTO`.

**Documentare qualcosa in CLAUDE.md**

> Aggiungi una voce di massimo due righe dentro NON TOCCARE SENZA CHIEDERE. Non una sezione, non un paragrafo di contesto. Poi dimmi `wc -l` del file.

**Ripresa dopo una pausa**

> Leggi `PIANO.md` e `git log --oneline -10`. Dimmi in chat: quali interventi risultano chiusi, quali restano aperti, e se qualche voce spuntata non ha un commit corrispondente. Non modificare nulla.

## Comandi Git Bash

Finestra separata da Claude Code, sempre. Apri con tasto destro nella cartella del progetto → Open Git Bash here.

```
# verifica del diff (passo 4)
git --no-pager diff --stat

# suite (passo 5) — non serve attivare la venv
./venv/Scripts/python.exe -m pytest -q --tb=line

# chiusura (passo 6)
git add -A
git commit -m "fix: descrizione in una riga (N)"

# annullare modifiche non committate
git checkout -- .

# stato all'apertura di una sessione
git status
git --no-pager log --oneline -5
grep -n "\[ \]" PIANO.md
```

Tre trappole già incontrate. Il **pager** trattiene gli output lunghi e aspetta `q`: per questo ogni comando git qui porta `--no-pager`. Gli **output enormi** bloccano il terminale, e `-q --tb=line` serve a evitarlo quando qualcosa fallisce in massa. La **venv** va riattivata a ogni nuova finestra, oppure si chiama direttamente `./venv/Scripts/python.exe`, che è la forma più sicura.

I percorsi Windows in Git Bash si scrivono `/c/Users/...` con slash normali: il backslash è un carattere di escape e viene mangiato silenziosamente.

## Controllo anti-deriva

Ogni cinque interventi chiusi, cinque minuti in Git Bash:

```
wc -l CLAUDE.md PIANO.md
grep -c "\[ \]" PIANO.md
./venv/Scripts/python.exe -m pytest -q --tb=line
```

Se un documento ha sforato, si pota subito: aspettare significa poi doverlo riscrivere da capo, come è successo con le 1385 righe di `PIANO_ANALISI`.

A Fase 8 conclusa, o dopo un periodo di modifiche intense, si rigenera l'audit da una sessione pulita con il prompt originale e si confronta:

```
git --no-pager diff HEAD -- AUDIT.md
```

Le differenze dovrebbero corrispondere agli interventi fatti. **Quelle che non sai spiegare sono la cosa più interessante che questo metodo può produrre**: o un effetto collaterale non previsto, o una parte del codice descritta male fin dall'inizio.

Per questo il vecchio audit deve restare intatto. Un documento rattoppato strada facendo non permette quel confronto.

## Stato e prossimi passi

Verifica strutturale completata. Suite a 198 test verdi, copertura 91%, working tree pulito, voci 37 e 38 chiuse, `CLAUDE.md` riportato nel limite. Restano 31 interventi aperti.

L'ordine non segue la numerazione del piano, perché la numerazione riflette l'ordine di scoperta e non il rischio.

1. **Decisioni P2–P6b.** Bloccano gli interventi 13, 14, 17, 21, 22, 23, 33 e 36. È il punto con il rapporto migliore fra sforzo e progresso: una sessione sblocca un quarto del piano.
2. **Intervento 40.** Misurare versione e collation del MySQL di Railway. È una misura, non una modifica: nessun rischio.
3. **Intervento 41.** Contare le email che differiscono solo per maiuscole. Dice se serve una migrazione dei dati esistenti.
4. **Intervento 9 · R6.** La correzione vera. Dipende dai due precedenti: senza, correggeresti alla cieca.

Una cosa da sapere prima di arrivarci. Gli interventi 11, 12 e 39 toccano Google Calendar, email e Discord, che la fixture `integrazioni_esterne_finte` sostituisce con no-op. Lì una suite verde non dimostra nulla, e i test vanno chiesti **prima** della correzione.

E prima di qualsiasi `git push`: ci sono commit locali non pubblicati e `origin` è collegato a un repository da cui Railway potrebbe fare deploy automatico. Verificalo sulla dashboard prima, non dopo.
