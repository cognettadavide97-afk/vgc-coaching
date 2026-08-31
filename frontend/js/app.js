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
//
// Multilingua: le funzioni t("chiave") e tf("chiave", {...}) usate in
// tutto questo file sono definite in frontend/js/i18n.js, caricato PRIMA
// di questo script in index.html — leggi quel file per il dizionario
// completo e per come funziona il cambio lingua.

// ─── STATO GLOBALE ───────────────────────────────────────────
// Qui salviamo tutto quello che l'utente sceglie durante il flusso
const state = {
    selectedSlot: null,      // slot scelto
    selectedHours: 2,        // durata scelta (default 2h, vedi bottone "active" in index.html)
    selectedPrice: 40,       // prezzo calcolato
    selectedService: 'vod_review', // tipo di servizio scelto
    userId: null,              // id utente creato nel DB
    pacchettoAttivo: null,      // { id, nome, sessioni_residue, durata_sessione_ore } se trovato per l'email inserita
    pacchettoRichiestaTipo: null, // "intro"/"team"/"tour" scelto nella vetrina pacchetti
    pacchettoRichiestaNome: null  // nome leggibile dello stesso pacchetto, per il messaggio di riepilogo
};
// "state" è un oggetto letterale — l'equivalente JavaScript di un
// dizionario Python ({}). Essendo dichiarato con "const" non lo si può
// riassegnare (non puoi scrivere "state = qualcos'altro"), ma i suoi
// CAMPI restano modificabili liberamente (vedrai più sotto "state.userId
// = ..."), esattamente come un dizionario Python passato come parametro
// resta modificabile anche se la variabile che lo referenzia non cambia.

// Etichette leggibili per servizio/stato prenotazione, prese dal
// dizionario multilingua invece che scritte qui a mano — così cambiano
// da sole quando l'utente cambia lingua (vedi setLang in i18n.js).
function getServiceLabel(servizio) {
    return t(`service_${servizio}`);
}

function getStatusLabel(stato) {
    return t(`status_${stato}`);
}

// ─── LOGIN DISCORD (opzionale, non blocca mai il guest checkout) ──

// Il token che prova l'identità dello studente NON passa più da qui: dal
// login Discord in poi vive in un cookie httpOnly (impostato dal server,
// vedi backend/routers/discord_auth.py) — invisibile e non manipolabile da
// JavaScript, mandato AUTOMATICAMENTE dal browser ad ogni richiesta verso
// questo stesso sito, senza che questo file debba mai leggerlo o
// allegarlo a mano in un header. Prima (quando viveva in localStorage)
// un eventuale bug XSS altrove nella pagina avrebbe potuto rubarlo con una
// singola riga di JavaScript; un cookie httpOnly non è leggibile da
// nessuno script, nemmeno il nostro.
//
// studentLoggedIn è quindi tutto quello che resta lato JS: un semplice
// SI/NO per decidere cosa mostrare in pagina (bottone di login o profilo,
// checkbox "usa pacchetto"...), aggiornato in base all'esito delle
// richieste sotto — non è più il token stesso, solo lo stato "sono
// loggato?" dedotto da esse.
let studentLoggedIn = false;

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

    // Il caso "sto tornando da Discord dopo il login" non passa più da un
    // parametro nell'URL (il server ha già impostato il cookie prima di
    // rimandarci qui, vedi backend/routers/discord_auth.py) — resta solo
    // da controllare l'eventuale errore.
    const urlParams = new URLSearchParams(window.location.search);
    const erroreDiscord = urlParams.get('discord_error');

    if (erroreDiscord) {
        window.history.replaceState({}, '', window.location.pathname);
        alert(t('discord_login_failed'));
    }

    // Non c'è più un token da controllare lato JS per sapere "sono
    // loggato?" (il cookie non è leggibile da qui) — proviamo sempre a
    // caricare il profilo: se non esiste nessun cookie valido, il server
    // risponde 401 e loadStudentProfile mostra da sola il bottone di login.
    await loadStudentProfile();
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
            ${t('discord_login_btn')}
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
        // Avviata subito, ma await SOLO più sotto (dove prima stava questa
        // stessa chiamata): /users/me e /users/me/prenotazioni si
        // autenticano con lo stesso cookie e non dipendono l'una
        // dall'altra — partire in parallelo invece che una dopo l'altra
        // dimezza il tempo di attesa a ogni caricamento della pagina per
        // un visitatore già loggato. loadBookingHistory() gestisce già i
        // propri errori (try/catch, restituisce [] in caso di problemi).
        const prenotazioniPromise = loadBookingHistory();

        // Nessun header da allegare qui: se esiste un cookie di sessione
        // valido, il browser lo manda da solo (stessa origine della
        // pagina) — vedi il commento su studentLoggedIn in cima al file.
        const res = await fetch('/users/me');

        // res.ok è true se il codice di stato HTTP della risposta è nella
        // fascia "successo" (200-299) — un modo rapido per controllare se
        // la richiesta è andata a buon fine, senza dover confrontare
        // manualmente res.status con dei numeri.
        if (!res.ok) {
            // nessun cookie valido (mai loggato, oppure token scaduto):
            // torna al bottone di login
            studentLoggedIn = false;
            showLoginButton();
            return;
        }

        studentLoggedIn = true;

        // res.json() legge il corpo della risposta e lo trasforma da testo
        // JSON a un vero oggetto JavaScript — anche questa è un'operazione
        // "asincrona" (per questo c'è un altro "await"), perché leggere il
        // corpo della risposta può richiedere un altro po' di tempo.
        const profilo = await res.json();
        state.userId = profilo.id;

        // precompila i campi del form step 2, se presenti
        const campoNome = document.getElementById('nome');
        const campoEmail = document.getElementById('email');
        const campoCategoria = document.getElementById('categoria');
        const campoDiscord = document.getElementById('discord');
        // "campoNome ||" non c'entra qui — invece "profilo.nome || ''" (poco
        // sotto) vuol dire "usa profilo.nome se non è vuoto/null/undefined,
        // altrimenti usa una stringa vuota" — lo stesso pattern "or" di
        // Python (note_cliente or "Nessuna nota") visto nel backend.
        if (campoNome) campoNome.value = profilo.nome || '';
        if (campoEmail) campoEmail.value = profilo.email || '';
        if (campoCategoria && profilo.categoria) campoCategoria.value = profilo.categoria;
        if (campoDiscord) campoDiscord.value = profilo.discord_tag || '';

        const prenotazioni = await prenotazioniPromise;

        document.getElementById('discord-login-bar').innerHTML = `
            <div class="login-bar-content">
                <span>👋 ${t('welcome_back')} <strong>${escapeHtmlPublic(profilo.nome)}</strong>!</span>
                ${prenotazioni.length > 0 ? `
                    <button class="link-btn" onclick="toggleBookingHistory()">
                        ${t('your_bookings')} (${prenotazioni.length})
                    </button>
                ` : ''}
                <button class="link-btn" onclick="logoutStudent()">${t('log_out')}</button>
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
        studentLoggedIn = false;
        showLoginButton();
    }
}

async function loadBookingHistory() {
    try {
        const res = await fetch('/users/me/prenotazioni');
        if (!res.ok) return [];
        return await res.json();
    } catch (error) {
        return [];
    }
}

function renderBookingHistory(prenotazioni) {
    const container = document.getElementById('storico-prenotazioni');
    if (!container) return;

    // Cancellabile solo se ancora confermata E non già passata — stesso
    // controllo (ridondante apposta) che il backend rifà comunque in
    // cancella_prenotazione_cliente (vedi backend/routers/booking.py):
    // qui serve solo a decidere se mostrare il bottone.
    const ora = Date.now();

    container.innerHTML = `
        <ul class="storico-lista">
            ${prenotazioni.map(p => {
                const cancellabile = p.stato === 'confirmed' && new Date(p.start_time_iso).getTime() > ora;
                return `
                <li>
                    ${getServiceLabel(p.servizio)} — ${p.data} ${t('at_time_connector')} ${p.ora}
                    <span class="storico-stato storico-stato-${p.stato}">${getStatusLabel(p.stato)}</span>
                    ${cancellabile ? `
                        <button class="link-btn storico-cancella" onclick="cancellaPrenotazione(${p.id})">
                            ${t('cancel_booking')}
                        </button>
                    ` : ''}
                </li>
            `;
            }).join('')}
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

async function cancellaPrenotazione(bookingId) {
    // confirm() è un dialogo BLOCCANTE nativo del browser: l'esecuzione si
    // ferma finché l'utente non clicca OK/Annulla — va benissimo qui,
    // perché è un'azione irreversibile (libera lo slot, cancella l'evento
    // sul calendario del coach) e vogliamo un ultimo controllo esplicito.
    if (!confirm(t('confirm_cancel_booking'))) return;

    try {
        const res = await fetch(`/bookings/${bookingId}/cancella`, {
            method: 'PATCH'
        });
        if (!res.ok) {
            const errore = await res.json().catch(() => ({}));
            alert(errore.detail || t('generic_error'));
            return;
        }
        // Ricarica sia lo storico (mostra "cancelled" al posto del bottone)
        // sia gli slot dello step 1 (quello appena liberato torna prenotabile).
        const prenotazioni = await loadBookingHistory();
        renderBookingHistory(prenotazioni);
        loadSlots();
    } catch (error) {
        alert(t('generic_error'));
    }
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

async function logoutStudent() {
    // Un cookie httpOnly non è cancellabile da JavaScript (è invisibile
    // anche a questo script, non solo agli script malevoli) — va chiesto
    // al server di farlo, con una richiesta dedicata (vedi
    // backend/routers/discord_auth.py). Prima, con il token in
    // localStorage, bastava una riga locale; ora serve un giro di rete.
    try {
        await fetch('/auth/discord/logout', { method: 'POST' });
    } catch (error) {
        console.error('Errore durante il logout:', error);
    }
    studentLoggedIn = false;
    showLoginButton();
}

// ─── UTILITÀ ─────────────────────────────────────────────────
// Formatta una data ISO in formato leggibile, nella lingua corrente
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
    // che il nostro codice debba sapere dove si trova. Il "locale" (primo
    // parametro) invece cambia solo la LINGUA con cui la data viene
    // scritta (nomi dei giorni/mesi, ordine giorno/mese...) — lo
    // agganciamo a currentLang (definita in i18n.js) così cambia insieme
    // al resto della pagina.
    const locale = currentLang === 'it' ? 'it-IT' : 'en-GB';
    return date.toLocaleDateString(locale, {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });
}

function formatTime(isoString) {
    const date = new Date(isoString);
    const locale = currentLang === 'it' ? 'it-IT' : 'en-GB';
    return date.toLocaleTimeString(locale, {
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
            `<p class="loading">${t('error_loading_slots')}</p>`;
    }
}

// Estrae l'ora (0-23) di un istante nel fuso orario italiano, A
// PRESCINDERE da dove si trovi fisicamente chi guarda la pagina — a
// differenza di new Date(...).getHours(), che userebbe il fuso del
// dispositivo del visitatore. Serve per applicare la stessa regola "solo
// 15:00 o 17:00" di ORE_INIZIO_VALIDE_2H in backend/routers/booking.py,
// che è un orario di ricevimento fissato in ora italiana, non locale a chi
// prenota.
function oraItaliana(isoString) {
    return parseInt(
        new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', hourCycle: 'h23' })
            .format(new Date(isoString))
    );
}

const ORE_INIZIO_VALIDE_2H = [15, 17];

function renderSlots() {
    const container = document.getElementById('slots-container');

    // Il calendario genera SOLO slot da 1 ora (vedi
    // backend/services/availability_service.py). Una card da 1h è quindi
    // uno slot reale, presa così com'è; una card da 2h è invece "virtuale":
    // esiste solo se ci sono DUE slot da 1h adiacenti (stesso giorno, il
    // secondo inizia esattamente un'ora dopo il primo) E l'orario di inizio
    // è uno di quelli ammessi per una sessione da 2h — la stessa identica
    // logica che il backend riapplica per davvero al momento della
    // prenotazione (vedi create_booking in backend/routers/booking.py), qui
    // serve solo a decidere quali card mostrare.
    const slotsUnOra = allSlots.filter(s => s.duration_hours === 1);

    let cardsDaMostrare;
    if (state.selectedHours === 1) {
        cardsDaMostrare = slotsUnOra;
    } else {
        // .getTime() converte una data in un numero (millisecondi dall'inizio
        // del 1970) — confrontare numeri è più sicuro che confrontare
        // stringhe, che potrebbero essere formattate in modo leggermente
        // diverso pur rappresentando lo stesso istante.
        const perTimestamp = new Map(slotsUnOra.map(s => [new Date(s.start_time).getTime(), s]));
        cardsDaMostrare = slotsUnOra.filter(slot => {
            if (!ORE_INIZIO_VALIDE_2H.includes(oraItaliana(slot.start_time))) return false;
            const inizioSecondario = new Date(slot.start_time).getTime() + 60 * 60 * 1000;
            return perTimestamp.has(inizioSecondario);
        });
    }

    if (cardsDaMostrare.length === 0) {
        container.innerHTML = `<p class="loading">${t('no_slots')}</p>`;
        return;
    }

    // Anche per una card da 2h, si passa a selectSlot() solo il PRIMO slot:
    // il backend risale da solo al secondo (stesso motivo del filtro sopra).
    container.innerHTML = cardsDaMostrare.map(slot => `
        <button type="button" class="slot-card" onclick="selectSlot(${slot.id}, '${slot.start_time}')">
            <div class="slot-date">${formatDate(slot.start_time)}</div>
            <div class="slot-time">${formatTime(slot.start_time)}</div>
        </button>
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

// Aggiorna la riga del totale nel riepilogo, tenendo conto del checkbox
// "usa pacchetto" (se presente e selezionato, la sessione è gratis).
function aggiornaPrezzoRiepilogo() {
    const checkbox = document.getElementById('usa-pacchetto');
    const usaPacchetto = checkbox && checkbox.checked;
    document.getElementById('summary-price').textContent = usaPacchetto ? t('free_package') : `€${state.selectedPrice}`;
}

// Cerca un pacchetto attivo dello studente LOGGATO, compatibile con la
// durata scelta allo step 1 (i pacchetti del catalogo sono tutti da 2 ore,
// vedi backend/services/package_service.py) — se lo trova, mostra il
// checkbox "usa pacchetto" allo step 3, altrimenti lo tiene nascosto.
// Nessun parametro email: da quando GET /users/pacchetti-attivi identifica
// l'utente dal cookie di sessione invece che da un'email nell'URL (fix di
// sicurezza, vedi backend/routers/users.py), questa funzione va chiamata
// solo se studentLoggedIn è vero — vedi il chiamante, il click su
// "btn-to-step3".
async function controllaPacchettoAttivo() {
    const box = document.getElementById('pacchetto-attivo-box');
    const testo = document.getElementById('pacchetto-attivo-testo');
    const checkbox = document.getElementById('usa-pacchetto');
    state.pacchettoAttivo = null;
    checkbox.checked = false;
    box.style.display = 'none';

    try {
        const res = await fetch('/users/pacchetti-attivi');
        if (!res.ok) return;
        const pacchetti = await res.json();
        const compatibile = pacchetti.find(p => p.durata_sessione_ore === state.selectedHours);
        if (!compatibile) return;

        state.pacchettoAttivo = compatibile;
        testo.textContent = tf('use_package_session', {
            name: compatibile.nome,
            used: compatibile.sessioni_residue,
            total: compatibile.sessioni_totali
        });
        box.style.display = 'block';
    } catch (error) {
        // Nessun pacchetto disponibile o email non ancora nota: non è un
        // errore da segnalare all'utente, il form funziona comunque a
        // prezzo pieno.
    }
}

document.getElementById('usa-pacchetto').addEventListener('change', aggiornaPrezzoRiepilogo);

// Estratta a parte (non solo dentro il click di "Continue") perché va
// richiamata anche quando l'utente cambia lingua mentre è già allo step 3
// — vedi il listener "langchange" più in fondo al file.
function aggiornaRiepilogo() {
    if (!state.selectedSlot) return;
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();

    document.getElementById('summary-slot').textContent =
        `${formatDate(state.selectedSlot.start_time)} ${t('at_time_connector')} ${formatTime(state.selectedSlot.start_time)}`;
    document.getElementById('summary-service').textContent = getServiceLabel(state.selectedService);
    document.getElementById('summary-duration').textContent =
        `${state.selectedHours} ${state.selectedHours > 1 ? t('unit_hours') : t('unit_hour')}`;
    document.getElementById('summary-nome').textContent = nome;
    document.getElementById('summary-email').textContent = email;
    aggiornaPrezzoRiepilogo();
}

document.getElementById('btn-to-step3').addEventListener('click', async () => {
    // validazione base
    // .value legge il testo digitato in un <input>. .trim() rimuove spazi
    // bianchi a inizio/fine — stesso metodo, stesso nome, di Python.
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!nome || !email) {
        alert(t('name_email_required'));
        return;
    }

    // Usare un pacchetto ora richiede login Discord (vedi il controllo
    // "if not studente" su POST /bookings/ in backend/routers/booking.py):
    // senza un'identità verificata, chiunque conoscesse l'email di un
    // cliente avrebbe potuto scoprire e consumare il suo pacchetto già
    // pagato. Per un ospite non loggato, saltiamo del tutto la ricerca —
    // GET /users/pacchetti-attivi ora richiede comunque login, quindi non
    // troverebbe nulla di utile.
    if (studentLoggedIn) {
        await controllaPacchettoAttivo();
    }
    aggiornaRiepilogo();

    showStep('step-3');
});

// ─── STEP 3: CONFERMA ─────────────────────────────────────────
document.getElementById('btn-back-2').addEventListener('click', () => {
    showStep('step-2');
});

document.getElementById('btn-confirm').addEventListener('click', async () => {
    const btn = document.getElementById('btn-confirm');
    btn.disabled = true;
    btn.textContent = t('sending');
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
                categoria: document.getElementById('categoria').value,
                discord_tag: document.getElementById('discord').value.trim(),
                telefono: null
            })
        });

        if (!userResponse.ok) throw new Error('Error creating user');
        // "throw new Error(...)" solleva un errore manualmente — l'equivalente
        // di "raise Exception(...)" in Python. Verrà catturato dal blocco
        // catch più sotto, che mostra un messaggio generico all'utente.
        const user = await userResponse.json();
        state.userId = user.id;

        // Se il checkbox "usa pacchetto" è selezionato, la sessione viene
        // scalata dal pacchetto invece di essere pagata — il backend
        // ricontrolla comunque tutto server-side (vedi create_booking in
        // backend/routers/booking.py), questo è solo quello che l'utente
        // ha scelto in UI.
        const checkboxPacchetto = document.getElementById('usa-pacchetto');
        const packageId = (checkboxPacchetto.checked && state.pacchettoAttivo) ? state.pacchettoAttivo.id : null;

        // 2 — crea la prenotazione
        // Nessun header di autenticazione da costruire a mano: se lo
        // studente è loggato, il cookie di sessione viaggia da solo con la
        // richiesta (stessa origine) — è quello che il server legge per
        // verificare la proprietà del pacchetto quando packageId non è
        // null (vedi il commento sopra su controllaPacchettoAttivo).
        const bookingResponse = await fetch('/bookings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: state.userId,
                // Il backend verifica che questa email corrisponda davvero
                // a user_id quando non c'è un login Discord (vedi il
                // commento su BookingCreate.email in
                // backend/schemas/booking.py) — stessa email appena
                // mandata a POST /users/ qui sopra, nessun campo nuovo per
                // chi compila il form.
                email: document.getElementById('email').value.trim(),
                slot_id: state.selectedSlot.id,
                duration_hours: state.selectedHours,
                service_type: state.selectedService,
                note_cliente: document.getElementById('note').value.trim(),
                vod_link: document.getElementById('vod-link').value.trim(),
                replay_code: document.getElementById('replay-code').value.trim(),
                package_id: packageId
            })
        });

        if (!bookingResponse.ok) throw new Error('Error creating booking');

        // successo
        showStep('step-success');

    } catch (error) {
        // Se QUALSIASI cosa nel blocco try sopra fallisce (rete assente,
        // server che risponde con errore, slot nel frattempo occupato da
        // qualcun altro...), finiamo qui: riabilitiamo il bottone e
        // mostriamo un messaggio, invece di lasciare l'utente bloccato su
        // "Invio in corso..." per sempre.
        alert(t('generic_error'));
        btn.disabled = false;
        btn.textContent = t('confirm_booking');
    }
});

// ─── CONSULENZA GRATUITA (20 minuti) ──────────────────────────
// Completamente indipendente dal wizard sopra: non tocca slot/prenotazioni,
// manda solo i contatti al coach (POST /consulenze/) — vedi
// backend/routers/consulenza.py.
document.getElementById('btn-mostra-consulenza').addEventListener('click', () => {
    const form = document.getElementById('consulenza-form');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
});

document.getElementById('btn-invia-consulenza').addEventListener('click', async () => {
    const btn = document.getElementById('btn-invia-consulenza');
    const esito = document.getElementById('consulenza-esito');
    const nome = document.getElementById('consulenza-nome').value.trim();
    const email = document.getElementById('consulenza-email').value.trim();

    if (!nome || !email) {
        alert(t('name_email_required'));
        return;
    }

    btn.disabled = true;
    btn.textContent = t('sending');

    try {
        const res = await fetch('/consulenze/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome,
                email,
                discord_tag: document.getElementById('consulenza-discord').value.trim(),
                messaggio: document.getElementById('consulenza-messaggio').value.trim()
            })
        });

        if (!res.ok) throw new Error('Error sending request');

        esito.textContent = t('request_sent');
        document.getElementById('consulenza-form').querySelectorAll('input, textarea').forEach(el => el.value = '');
    } catch (error) {
        esito.textContent = t('generic_error');
    } finally {
        btn.disabled = false;
        btn.textContent = t('consulenza_submit');
    }
});

// ─── SELEZIONE PACCHETTO ───────────────────────────────────────
// Ogni card pacchetto ha un bottone "Select this package" (vedi
// index.html, classe .pacchetto-select-btn) — click su uno qualsiasi apre
// lo stesso form condiviso più sotto, ricordando quale pacchetto è stato
// scelto. Come la consulenza gratuita, questo NON attiva davvero il
// pacchetto (nessun pagamento in-app): manda solo la richiesta al coach
// (POST /pacchetti-richieste/), che poi lo assegna per davvero da
// /admin/pacchetti dopo il pagamento.
document.querySelectorAll('.pacchetto-select-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        state.pacchettoRichiestaTipo = btn.dataset.tipo;
        state.pacchettoRichiestaNome = btn.dataset.nome;

        document.getElementById('pacchetto-selezionato-nome').textContent = btn.dataset.nome;
        const form = document.getElementById('pacchetto-form');
        form.style.display = 'block';
        document.getElementById('pacchetto-esito').textContent = '';
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
});

document.getElementById('btn-invia-pacchetto').addEventListener('click', async () => {
    const btn = document.getElementById('btn-invia-pacchetto');
    const esito = document.getElementById('pacchetto-esito');
    const nome = document.getElementById('pacchetto-nome').value.trim();
    const email = document.getElementById('pacchetto-email').value.trim();

    if (!nome || !email) {
        alert(t('name_email_required'));
        return;
    }

    btn.disabled = true;
    btn.textContent = t('sending');

    try {
        const res = await fetch('/pacchetti-richieste/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome,
                email,
                discord_tag: document.getElementById('pacchetto-discord').value.trim(),
                tipo: state.pacchettoRichiestaTipo,
                messaggio: document.getElementById('pacchetto-messaggio').value.trim()
            })
        });

        if (!res.ok) throw new Error('Error sending request');

        esito.textContent = t('request_sent');
        document.getElementById('pacchetto-form').querySelectorAll('input, textarea').forEach(el => el.value = '');
    } catch (error) {
        esito.textContent = t('generic_error');
    } finally {
        btn.disabled = false;
        btn.textContent = t('pkg_request_submit');
    }
});

// ─── CAMBIO LINGUA ─────────────────────────────────────────────
// i18n.js (caricato prima di questo file) si occupa da solo di ritradurre
// ogni elemento con data-i18n quando la lingua cambia — qui reagiamo solo
// ai pezzi che app.js ha scritto "a mano" in precedenza (con innerHTML o
// textContent), che quindi non hanno un data-i18n da rileggere.
document.addEventListener('langchange', () => {
    renderSlots();
    aggiornaRiepilogo();
    // La barra di login Discord è scritta interamente da JS (vedi
    // showLoginButton/loadStudentProfile sopra), quindi non ha data-i18n
    // da ritradurre da sola — va ricostruita a mano in entrambi i casi
    // (loggato o no), altrimenti resterebbe nella lingua con cui era
    // stata disegnata la prima volta.
    if (studentLoggedIn) {
        loadStudentProfile();
    } else {
        showLoginButton();
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
