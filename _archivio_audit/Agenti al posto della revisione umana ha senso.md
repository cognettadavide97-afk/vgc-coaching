# Agenti al posto della revisione umana: ha senso?

Nov 6, 2026 · @Davide

Valutazione dell'idea di affidare a una squadra di agenti i passi del Protocollo operativo, al posto della revisione manuale.

## I tre tipi di passo

I sei passi del ciclo non sono la stessa cosa, e la domanda va scomposta invece di valutarla in blocco.

**Meccanici** — passi 4, 5, 6: lanciare `git diff`, lanciare i test, fare commit. Sono già automatizzabili, e in effetti Claude Code li esegue già. Il motivo per cui li fai tu non è che siano difficili: è che un resoconto non è una prova. Un agente che riporta «la suite è verde» ti dà la stessa frase che ti darebbe Claude Code, con un passaggio in più nel mezzo.

**Di giudizio** — passi 2 e 3: il piano è proporzionato? Il diff tocca i file annunciati? Qui l'agente sembra utile, ed è il punto dove si rompe.

**Irriducibilmente tuoi** — le decisioni P2–P6b. Nessun agente può decidere se prenotare richiede il login.

## L'obiezione che conta

Un agente che revisiona il lavoro di un altro agente sembra un controllo indipendente. Non lo è. È lo stesso modello con un prompt diverso: condivide gli stessi punti ciechi, le stesse tendenze a dare per buono ciò che suona plausibile, la stessa incapacità di accorgersi che una modifica è andata oltre il richiesto se la giustificazione è ben scritta.

La tua revisione è debole sul contenuto — non leggi il codice — ma è **strutturalmente indipendente**. Quando guardi `git diff --stat` e vedi otto file invece di due, stai applicando un criterio che non dipende dal capire cosa fanno quelle righe. Un agente che legge lo stesso diff lo valuta con lo stesso apparato che l'ha prodotto.

E c'è un precedente che pesa: il progetto è andato in deriva perché il lavoro procedeva senza un punto di controllo esterno. Aggiungere agenti autonomi è lo stesso movimento che ha causato il problema, con un nome nuovo.

## Dove invece funzionano davvero

Il criterio è: **delega dove l'output è verificabile a costo basso da chi non ha competenza.**

Funziona per il lavoro di lettura. Un agente che produce l'audit di un modulo citando `file:riga` è verificabile a campione — apri tre righe e controlli. Un agente che scrive test è verificabile con la prova del semaforo — rompi un valore e vedi se reagisce. In entrambi i casi la verifica non richiede di saper programmare.

Non funziona dove l'unica verifica è l'opinione di un altro agente.

## L'uso che chiude davvero il divario

Gli agenti non chiudono il divario di competenza: lo nascondono. Più cose succedono in parallelo, meno ne vedi.

L'unico uso che lo chiude è l'opposto di quello che viene in mente per primo — un agente il cui compito è spiegarti, non fare:

> Spiegami il modulo X come se non avessi mai visto questo progetto. Parti da un input reale, dimmi cosa succede passo per passo, quale output esce. Poi dimmi le tre cose che più facilmente si possono rompere qui.

Uno a settimana, sui moduli che l'audit segnala come centrali. In un mese la differenza è sostanziale, e ogni revisione successiva costa meno.

## Il punto pratico

Il collo di bottiglia non è la velocità di esecuzione: sono sei decisioni di prodotto che bloccano otto interventi. Una squadra di agenti su un progetto fermo su decisioni umane accelera la parte che non è lenta.

Il perimetro ragionevole, se si vuole comunque provarci:

- **Sì** ad agenti per audit, scrittura di test e spiegazione dei moduli.
- **No** ad agenti che decidono, correggono e committano senza che tu veda il diff.
