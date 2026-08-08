// Questo file è il "cervello" della pagina pubblica di prenotazione
// (frontend/index.html). È JavaScript "vanilla": nessun framework (niente
// React, Vue...), solo funzioni che manipolano direttamente la pagina
// (il "DOM" — Document Object Model, cioè la rappresentazione in memoria
// della pagina HTML che il browser ti lascia leggere e modificare da
// codice) e che parlano con il backend tramite fetch(), l'equivalente nel
// browser di quello che in Python fai con la libreria "requests".
//
// Se vieni da Python, alcune differenze di sintassi da tenere a mente
// mentre leggi: le funzioni si dichiarano con "function nome() {}" (o come
// "arrow function" più sotto), i blocchi di codice usano le graffe {} al
// posto dell'indentazione, ogni istruzione finisce con ";" (opzionale ma
// buona abitudine), e "const"/"let" sono i modi per dichiarare variabili
// (const = non verrà mai riassegnata, let = può cambiare — non esiste un
// vero equivalente di "var pigro" come in Python, dove basta scrivere
// nome = valore).

// ─── STATO GLOBALE ───────────────────────────────────────────
// Qui salviamo tutto quello che l'utente sceglie durante il flusso
const state = {
    selectedSlot: null,      // slot scelto
    selectedHours: 1,        // durata scelta
    selectedPrice: 35,       // prezzo calcolato
    selectedService: 'vod_review', // tipo di servizio scelto
    userId: null              // id utente creato nel DB
};
// "state" è un oggetto letterale — l'equivalente JavaScript di un
// dizionario Python ({}). Essendo dichiarato con "const" non lo si può
// riassegnare (non puoi scrivere "state = qualcos'altro"), ma i suoi
// CAMPI restano modificabili liberamente (vedrai più sotto "state.userId
// = ..."), esattamente come un dizionario Python passato come parametro
// resta modificabile anche se la variabile che lo referenzia non cambia.

const SERVICE_LABELS = {
    vod_review: 'VOD Review',
    team_building: 'Team Building',
    bo3_sparring: 'Bo3 Sparring',
    mentality_prep: 'Mentality Prep'
};

// ─── LOGIN DISCORD (opzionale, non blocca mai il guest checkout) ──

// localStorage è uno "spazio di archiviazione" che il browser mette a
// disposizione di ogni sito: quello che ci salvi resta lì anche se chiudi
// la scheda o il browser, finché non lo cancelli esplicitamente (a
// differenza delle variabili JavaScript normali, che si azzerano appena
// ricarichi la pagina). Lo usiamo per "ricordare" che lo studente è
// loggato anche tra una visita e l'altra, senza dover rifare il login con
// Discord ogni volta.
let studentToken = localStorage.getItem('student_token');

function escapeHtmlPublic(str) {
    // Questa funzione protegge da un problema di sicurezza chiamato XSS
    // (Cross-Site Scripting): se un valore che arriva dal server (es. il
    // nome di uno studente) contenesse per qualche motivo del codice HTML
    // o JavaScript malevolo, e lo inserissimo così com'è in una pagina con
    // innerHTML (come si fa spesso più sotto in questo file), quel codice
    // verrebbe davvero ESEGUITO nel browser di chi guarda la pagina.
    // Il trucco: creo un <div> "invisibile" (mai inserito nella pagina
    // vera), ci scrivo dentro il testo con .textContent (che tratta
    // SEMPRE il contenuto come testo semplice, mai come HTML), e poi leggo
    // .innerHTML di quello stesso div — a quel punto il browser ha già
    // convertito ogni carattere speciale (come < e >) nel suo equivalente
    // "innocuo" (&lt; e &gt;), pronto per essere inserito altrove in
    // sicurezza.
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

async function initDiscordLogin() {
    // "async function" dichiara una funzione che può contenere "await" al
    // suo interno — vedi la spiegazione completa più sotto, sulla prima
    // vera chiamata fetch(), su cosa vogliano dire "async"/"await".

    // window.location.search è la parte dell'URL della pagina che inizia
    // con "?" (es. "?student_token=abc123"). URLSearchParams è un'utility
    // del browser che la legge e la trasforma in qualcosa di comodo da
    // interrogare con .get("nome_parametro").
    const urlParams = new URLSearchParams(window.location.search);
    const tokenDaUrl = urlParams.get('student_token');
    const erroreDiscord = urlParams.get('discord_error');

    if (tokenDaUrl) {
        // Questo è il caso "sto tornando da Discord dopo il login": il
        // backend (backend/routers/discord_auth.py) ci ha rimandati qui
        // con il token nell'URL. Lo salviamo per il futuro...
        studentToken = tokenDaUrl;
        localStorage.setItem('student_token', studentToken);
        // ...e poi "puliamo" l'URL (togliendo "?student_token=..." dalla
        // barra degli indirizzi) senza ricaricare la pagina — altrimenti
        // il token resterebbe visibile lì e potrebbe essere ricondiviso
        // per sbaglio (es. copiando il link).
        window.history.replaceState({}, '', window.location.pathname);
    } else if (erroreDiscord) {
        window.history.replaceState({}, '', window.location.pathname);
        alert('Accesso con Discord non riuscito. Riprova, oppure prenota come ospite senza login.');
    }

    if (studentToken) {
        await loadStudentProfile();
    } else {
        showLoginButton();
    }
}

function showLoginButton() {
    // innerHTML sostituisce TUTTO il contenuto di un elemento con la
    // stringa HTML che gli passi — qui usiamo una "template literal"
    // (le virgolette backtick `...`), che a differenza delle stringhe
    // normali '...' o "..." possono andare su più righe e possono
    // contenere ${espressioni} che vengono calcolate e inserite al posto
    // giusto (l'equivalente JavaScript delle f-string di Python).
    document.getElementById('discord-login-bar').innerHTML = `
        <a href="/auth/discord/login" class="discord-login-btn">
            Accedi con Discord (opzionale)
        </a>
    `;
}

async function loadStudentProfile() {
    try {
        // fetch(url, opzioni) manda una richiesta HTTP e restituisce una
        // "Promise" — un oggetto che rappresenta "un risultato che arriverà
        // più avanti" (la richiesta di rete richiede tempo, non è
        // immediata). "await" davanti a fetch() dice "aspetta che questa
        // Promise sia risolta prima di andare avanti con la riga
        // successiva" — è concettualmente identico a una chiamata di
        // funzione bloccante in Python, solo che qui va dichiarato
        // esplicitamente (e la funzione che lo contiene deve essere
        // "async"), perché JavaScript di norma preferisce non bloccare mai
        // l'esecuzione in attesa di operazioni lente come la rete.
        const res = await fetch('/users/me', {
            headers: { 'Authorization': `Bearer ${studentToken}` }
        });

        // res.ok è true se il codice di stato HTTP della risposta è nella
        // fascia "successo" (200-299) — un modo rapido per controllare se
        // la richiesta è andata a buon fine, senza dover confrontare
        // manualmente res.status con dei numeri.
        if (!res.ok) {
            // token scaduto o non valido: torna al bottone di login
            localStorage.removeItem('student_token');
            studentToken = null;
            showLoginButton();
            return;
        }

        // res.json() legge il corpo della risposta e lo trasforma da testo
        // JSON a un vero oggetto JavaScript — anche questa è un'operazione
        // "asincrona" (per questo c'è un altro "await"), perché leggere il
        // corpo della risposta può richiedere un altro po' di tempo.
        const profilo = await res.json();
        state.userId = profilo.id;

        // precompila i campi del form step 2, se presenti
        const campoNome = document.getElementById('nome');
        const campoEmail = document.getElementById('email');
        const campoShowdown = document.getElementById('showdown');
        const campoDiscord = document.getElementById('discord');
        // "campoNome ||" non c'entra qui — invece "profilo.nome || ''" (poco
        // sotto) vuol dire "usa profilo.nome se non è vuoto/null/undefined,
        // altrimenti usa una stringa vuota" — lo stesso pattern "or" di
        // Python (note_cliente or "Nessuna nota") visto nel backend.
        if (campoNome) campoNome.value = profilo.nome || '';
        if (campoEmail) campoEmail.value = profilo.email || '';
        if (campoShowdown) campoShowdown.value = profilo.showdown_username || '';
        if (campoDiscord) campoDiscord.value = profilo.discord_tag || '';

        const prenotazioni = await loadBookingHistory();

        document.getElementById('discord-login-bar').innerHTML = `
            <div class="login-bar-content">
                <span>👋 Bentornato, <strong>${escapeHtmlPublic(profilo.nome)}</strong>!</span>
                ${prenotazioni.length > 0 ? `
                    <button class="link-btn" onclick="toggleBookingHistory()">
                        Le tue prenotazioni (${prenotazioni.length})
                    </button>
                ` : ''}
                <button class="link-btn" onclick="logoutStudent()">Esci</button>
            </div>
            <div id="storico-prenotazioni" style="display:none"></div>
        `;
        // ${condizione ? 'seA' : 'seB'} dentro una template literal è
        // l'operatore ternario di JavaScript (identico nell'idea a
        // "A if condizione else B" in Python): qui decide se includere o
        // no il bottone "Le tue prenotazioni", a seconda che ce ne siano.

        if (prenotazioni.length > 0) {
            renderBookingHistory(prenotazioni);
        }
    } catch (error) {
        // "try/catch" in JavaScript è l'equivalente di "try/except" in
        // Python: se una qualunque riga dentro il blocco try genera un
        // errore (qui, tipicamente un problema di rete), l'esecuzione
        // salta direttamente al blocco catch invece di far "esplodere"
        // tutta la pagina.
        console.error('Errore caricamento profilo Discord:', error);
        showLoginButton();
    }
}

async function loadBookingHistory() {
    try {
        const res = await fetch('/users/me/prenotazioni', {
            headers: { 'Authorization': `Bearer ${studentToken}` }
        });
        if (!res.ok) return [];
        return await res.json();
    } catch (error) {
        return [];
    }
}

function renderBookingHistory(prenotazioni) {
    const container = document.getElementById('storico-prenotazioni');
    if (!container) return;

    container.innerHTML = `
        <ul class="storico-lista">
            ${prenotazioni.map(p => `
                <li>
                    ${SERVICE_LABELS[p.servizio] || p.servizio} — ${p.data} alle ${p.ora}
                    <span class="storico-stato storico-stato-${p.stato}">${p.stato}</span>
                </li>
            `).join('')}
        </ul>
    `;
    // prenotazioni.map(p => `...`) è l'equivalente JavaScript di una list
    // comprehension Python: per ogni elemento dell'array "prenotazioni",
    // calcola una nuova stringa HTML, producendo un nuovo array di
    // stringhe. ".join('')" poi le incolla tutte insieme in un'unica
    // stringa (come "".join(lista) in Python, con gli argomenti invertiti:
    // qui è il metodo dell'array a chiamare join, non il separatore).
    // "p => `...`" è una ARROW FUNCTION: una sintassi più corta per
    // scrivere una funzione piccola, equivalente a "function(p) { return
    // `...` }" — molto simile nello spirito a una lambda Python, ma
    // utilizzabile anche per funzioni con un corpo più lungo.
}

function toggleBookingHistory() {
    const container = document.getElementById('storico-prenotazioni');
    if (container) {
        // container.style.display legge/scrive lo stile CSS "display"
        // direttamente dall'elemento — qui alterniamo tra 'none'
        // (nascosto) e 'block' (visibile) ogni volta che l'utente clicca.
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
    }
}

function logoutStudent() {
    localStorage.removeItem('student_token');
    studentToken = null;
    showLoginButton();
}

// ─── UTILITÀ ─────────────────────────────────────────────────
// Formatta una data ISO in formato leggibile italiano
function formatDate(isoString) {
    // new Date(...) crea un oggetto Date di JavaScript a partire da una
    // stringa. Il punto CRUCIALE (collegato ai fusi orari, vedi i commenti
    // in backend/schemas/slots.py): isoString arriva dal backend con
    // l'offset UTC esplicito (es. "...+00:00"), quindi new Date() la
    // interpreta correttamente come un istante preciso nel tempo — non
    // come "un orario nel fuso di chi legge".
    const date = new Date(isoString);
    // .toLocaleDateString(...) è dove avviene la "magia": senza specificare
    // nessun fuso orario esplicito, il browser usa AUTOMATICAMENTE il fuso
    // orario del dispositivo di chi sta guardando la pagina — è così che
    // uno studente in un altro paese vede l'orario corretto per lui, senza
    // che il nostro codice debba sapere dove si trova.
    return date.toLocaleDateString('it-IT', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('it-IT', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Naviga tra gli step
function showStep(stepId) {
    // document.querySelectorAll('.step-content') trova TUTTI gli elementi
    // della pagina con classe "step-content" (le 4 <section> di
    // index.html) e restituisce una lista su cui possiamo iterare con
    // .forEach(...) — molto simile a un ciclo "for x in lista" di Python,
    // solo scritto come chiamata di metodo invece che come parola chiave.
    // classList.remove('active')/.add('active') tolgono/aggiungono una
    // classe CSS: è così che nascondiamo/mostriamo gli step (vedi il CSS
    // in frontend/css/style.css: .step-content senza "active" ha
    // display:none).

    // nasconde tutti gli step
    document.querySelectorAll('.step-content').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));

    // mostra lo step richiesto
    document.getElementById(stepId).classList.add('active');

    // aggiorna la barra degli step
    const stepNumber = stepId.replace('step-', '');
    if (!isNaN(stepNumber)) {
        // "?." è l'optional chaining: se document.getElementById(...)
        // restituisse null (elemento non trovato), ".classList" su null
        // darebbe un errore che blocca lo script — con "?." invece,
        // l'intera espressione si ferma silenziosamente e restituisce
        // undefined, senza errori. Utile qui perché "step-indicator-3" (lo
        // step finale di successo) potrebbe non avere un indicatore
        // corrispondente nella barra in alto.
        document.getElementById(`step-indicator-${stepNumber}`)?.classList.add('active');
        // marca i precedenti come completati
        for (let i = 1; i < parseInt(stepNumber); i++) {
            document.getElementById(`step-indicator-${i}`)?.classList.add('completed');
        }
    }

    // scrolla in cima
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── STEP 1: CARICA GLI SLOT ──────────────────────────────────
// Ogni slot ha una durata fissa (decisa dal coach). Per evitare di poter
// prenotare una durata diversa da quella reale dello slot (il backend
// la rifiuterebbe comunque), lo step 1 mostra solo gli slot la cui durata
// corrisponde a quella attualmente selezionata.
let allSlots = [];

async function loadSlots() {
    try {
        const response = await fetch('/slots/');
        allSlots = await response.json();
        renderSlots();
    } catch (error) {
        document.getElementById('slots-container').innerHTML =
            '<p class="loading">Errore nel caricamento degli slot.</p>';
    }
}

function renderSlots() {
    const container = document.getElementById('slots-container');
    // .filter(...) costruisce un nuovo array con solo gli elementi che
    // soddisfano la condizione — l'equivalente JavaScript di
    // [s for s in all_slots if s.duration_hours == state.selectedHours]
    // in Python.
    const slotsFiltrati = allSlots.filter(s => s.duration_hours === state.selectedHours);
    // "===" (triplo uguale) confronta valore E TIPO senza fare nessuna
    // conversione automatica — è la forma raccomandata in JavaScript,
    // perché "==" (doppio uguale) a volte confronta cose di tipo diverso
    // in modi sorprendenti (es. 0 == '' è true con "=="). Non esiste un
    // equivalente di questa distinzione in Python, dove "==" si comporta
    // già come il "===" di JavaScript.

    if (slotsFiltrati.length === 0) {
        container.innerHTML = '<p class="loading">Nessuno slot disponibile per questa durata. Prova un\'altra durata.</p>';
        return;
    }

    container.innerHTML = slotsFiltrati.map(slot => `
        <div class="slot-card" onclick="selectSlot(${slot.id}, '${slot.start_time}')">
            <div class="slot-date">${formatDate(slot.start_time)}</div>
            <div class="slot-time">${formatTime(slot.start_time)}</div>
        </div>
    `).join('');
    // Nota: onclick="selectSlot(...)" qui viene scritto DENTRO una
    // stringa HTML generata da JavaScript — a runtime diventa un attributo
    // HTML vero e proprio, e verrà eseguito come se l'avessi scritto a
    // mano nel file .html (come location.reload() in index.html).
}

// Quando l'utente clicca uno slot
function selectSlot(slotId, startTime) {
    state.selectedSlot = { id: slotId, start_time: startTime };

    // rimuove la selezione precedente
    document.querySelectorAll('.slot-card').forEach(c => c.classList.remove('selected'));

    // trova e seleziona la card cliccata
    // "event" qui è una variabile GLOBALE implicita del browser (esiste
    // automaticamente dentro qualunque gestore di evento, senza doverla
    // dichiarare) che rappresenta "il click che ha appena fatto scattare
    // questa funzione". event.currentTarget è l'elemento HTML su cui
    // l'evento è stato agganciato — qui, la card sulla quale si è
    // cliccato.
    event.currentTarget.classList.add('selected');

    // abilita il pulsante continua
    document.getElementById('btn-to-step2').disabled = false;
}

// Gestione bottoni servizio
document.querySelectorAll('.service-btn').forEach(btn => {
    // addEventListener('click', funzione) è il modo "moderno" (alternativo
    // a onclick="..." nell'HTML) di dire "quando questo elemento viene
    // cliccato, esegui questa funzione". Qui la funzione è scritta come
    // arrow function anonima direttamente sul posto, invece di essere
    // definita a parte con un nome.
    btn.addEventListener('click', () => {
        document.querySelectorAll('.service-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // btn.dataset.service legge l'attributo data-service="..." scritto
        // nell'HTML (vedi frontend/index.html) — .dataset è come il
        // browser espone tutti gli attributi "data-*" di un elemento.
        state.selectedService = btn.dataset.service;
    });
});

// Gestione bottoni durata
document.querySelectorAll('.duration-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // parseInt(...) converte una stringa (btn.dataset.hours è sempre
        // testo, anche se scritto come numero nell'HTML) in un numero
        // intero vero — come int(...) in Python.
        state.selectedHours = parseInt(btn.dataset.hours);
        state.selectedPrice = parseInt(btn.dataset.price);

        // cambiando durata, gli slot mostrati cambiano: la selezione
        // precedente potrebbe non essere più valida/visibile
        state.selectedSlot = null;
        document.getElementById('btn-to-step2').disabled = true;
        renderSlots();
    });
});

// Pulsante continua step 1 → step 2
document.getElementById('btn-to-step2').addEventListener('click', () => {
    showStep('step-2');
});

// ─── STEP 2: FORM DATI ────────────────────────────────────────
document.getElementById('btn-back-1').addEventListener('click', () => {
    showStep('step-1');
});

document.getElementById('btn-to-step3').addEventListener('click', () => {
    // validazione base
    // .value legge il testo digitato in un <input>. .trim() rimuove spazi
    // bianchi a inizio/fine — stesso metodo, stesso nome, di Python.
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!nome || !email) {
        alert('Nome e email sono obbligatori.');
        return;
    }

    // aggiorna il riepilogo
    // .textContent imposta il testo "puro" dentro un elemento (a
    // differenza di .innerHTML, non interpreta il valore come HTML — più
    // sicuro quando, come qui, il testo potrebbe contenere caratteri
    // speciali digitati dall'utente).
    document.getElementById('summary-slot').textContent =
        `${formatDate(state.selectedSlot.start_time)} alle ${formatTime(state.selectedSlot.start_time)}`;
    document.getElementById('summary-service').textContent =
        SERVICE_LABELS[state.selectedService] || state.selectedService;
    document.getElementById('summary-duration').textContent =
        `${state.selectedHours} ora${state.selectedHours > 1 ? 'e' : ''}`;
    document.getElementById('summary-nome').textContent = nome;
    document.getElementById('summary-email').textContent = email;
    document.getElementById('summary-price').textContent = `€${state.selectedPrice}`;

    showStep('step-3');
});

// ─── STEP 3: CONFERMA ─────────────────────────────────────────
document.getElementById('btn-back-2').addEventListener('click', () => {
    showStep('step-2');
});

document.getElementById('btn-confirm').addEventListener('click', async () => {
    const btn = document.getElementById('btn-confirm');
    btn.disabled = true;
    btn.textContent = 'Invio in corso...';
    // Disabilitare subito il bottone e cambiargli testo evita che
    // l'utente clicchi due volte per impazienza mentre la richiesta è
    // ancora in corso, creando magari due prenotazioni per errore.

    try {
        // 1 — crea l'utente
        // method: 'POST' + JSON.stringify(oggetto) è il modo standard di
        // mandare dati al server con fetch(): JSON.stringify trasforma un
        // oggetto JavaScript in una stringa di testo JSON (l'operazione
        // inversa di JSON.parse, che è quello che res.json() fa per te
        // dietro le quinte quando leggi una risposta).
        const userResponse = await fetch('/users/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome: document.getElementById('nome').value.trim(),
                email: document.getElementById('email').value.trim(),
                showdown_username: document.getElementById('showdown').value.trim(),
                discord_tag: document.getElementById('discord').value.trim(),
                telefono: null
            })
        });

        if (!userResponse.ok) throw new Error('Errore creazione utente');
        // "throw new Error(...)" solleva un errore manualmente — l'equivalente
        // di "raise Exception(...)" in Python. Verrà catturato dal blocco
        // catch più sotto, che mostra un messaggio generico all'utente.
        const user = await userResponse.json();
        state.userId = user.id;

        // 2 — crea la prenotazione
        const bookingResponse = await fetch('/bookings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: state.userId,
                slot_id: state.selectedSlot.id,
                duration_hours: state.selectedHours,
                service_type: state.selectedService,
                note_cliente: document.getElementById('note').value.trim(),
                vod_link: document.getElementById('vod-link').value.trim(),
                replay_code: document.getElementById('replay-code').value.trim()
            })
        });

        if (!bookingResponse.ok) throw new Error('Errore creazione prenotazione');

        // successo
        showStep('step-success');

    } catch (error) {
        // Se QUALSIASI cosa nel blocco try sopra fallisce (rete assente,
        // server che risponde con errore, slot nel frattempo occupato da
        // qualcun altro...), finiamo qui: riabilitiamo il bottone e
        // mostriamo un messaggio, invece di lasciare l'utente bloccato su
        // "Invio in corso..." per sempre.
        alert('Si è verificato un errore. Riprova.');
        btn.disabled = false;
        btn.textContent = '✓ Conferma prenotazione';
    }
});

// ─── AVVIO ────────────────────────────────────────────────────
// quando la pagina è pronta, carica gli slot
// 'DOMContentLoaded' è un evento che il browser genera automaticamente
// quando ha finito di leggere e costruire tutto l'HTML della pagina (ma
// non necessariamente immagini/CSS, che possono ancora star caricando) —
// aspettarlo garantisce che tutti gli elementi con id che usiamo sopra
// (document.getElementById(...)) esistano già quando le funzioni li
// cercano.
document.addEventListener('DOMContentLoaded', () => {
    loadSlots();
    initDiscordLogin();
});
