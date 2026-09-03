// Script della pagina pubblica: wizard di prenotazione in tre step,
// login opzionale via Discord, richiesta di consulenza e di pacchetti.
// JavaScript senza framework né build step.
//
// Le funzioni t() e tf() vengono da i18n.js, caricato prima di questo
// file: ogni testo mostrato all'utente deve passare da lì.
//
// Principio valido per tutto il file: i controlli fatti qui servono a
// costruire un'interfaccia coerente, non a garantire correttezza. Il
// backend riverifica tutto, perché l'interfaccia è scavalcabile.

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

// Il token di sessione non è accessibile da qui: vive in un cookie
// httpOnly impostato dal server, che il browser allega da solo alle
// richieste verso questa origine. Nessuno script può leggerlo, nemmeno
// questo.
//
// studentLoggedIn è quindi solo lo stato dedotto dalle risposte del
// server, usato per decidere cosa mostrare in pagina. Non è il token.
let studentLoggedIn = false;

function escapeHtmlPublic(str) {
    // Rende inerte il markup nei valori inseriti in pagina con innerHTML.
    // Necessaria perché i testi provengono da campi compilati dagli utenti.
    // Il div non viene mai inserito nel documento: serve solo a farsi
    // restituire dal browser la versione con le entità già sostituite.
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

async function initDiscordLogin() {
    // Il ritorno dal login Discord non passa più da un parametro nell'URL:
    // il cookie è già stato impostato dal server. Resta da gestire il solo
    // caso di errore.
    const urlParams = new URLSearchParams(window.location.search);
    const erroreDiscord = urlParams.get('discord_error');

    if (erroreDiscord) {
        window.history.replaceState({}, '', window.location.pathname);
        alert(t('discord_login_failed'));
    }

    // Il cookie non è leggibile da JavaScript, quindi lo stato di login si
    // deduce dall'esito della richiesta: un 401 fa mostrare il pulsante.
    await loadStudentProfile();
}

function showLoginButton() {
    document.getElementById('discord-login-bar').innerHTML = `
        <a href="/auth/discord/login" class="discord-login-btn">
            ${t('discord_login_btn')}
        </a>
    `;
}

async function loadStudentProfile() {
    try {
        // Le due richieste partono insieme: usano lo stesso cookie e non
        // dipendono l'una dall'altra, quindi attenderle in sequenza
        // raddoppierebbe l'attesa a ogni caricamento per un utente loggato.
        // loadBookingHistory gestisce già i propri errori.
        const prenotazioniPromise = loadBookingHistory();

        // Nessun header da allegare qui: se esiste un cookie di sessione
        // valido, il browser lo manda da solo (stessa origine della
        // pagina) — vedi il commento su studentLoggedIn in cima al file.
        const res = await fetch('/users/me');

        if (!res.ok) {
            // nessun cookie valido (mai loggato, oppure token scaduto):
            // torna al bottone di login
            studentLoggedIn = false;
            showLoginButton();
            return;
        }

        studentLoggedIn = true;

        const profilo = await res.json();
        state.userId = profilo.id;

        // precompila i campi del form step 2, se presenti
        const campoNome = document.getElementById('nome');
        const campoEmail = document.getElementById('email');
        const campoCategoria = document.getElementById('categoria');
        const campoDiscord = document.getElementById('discord');
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

        if (prenotazioni.length > 0) {
            renderBookingHistory(prenotazioni);
        }
    } catch (error) {
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

    // Il pulsante compare solo per le prenotazioni ancora annullabili. Il
    // backend rifà comunque il controllo: qui decide solo cosa mostrare.
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
}

async function cancellaPrenotazione(bookingId) {
    // Conferma esplicita: l'azione libera lo slot ed elimina l'evento sul
    // calendario, e non è reversibile.
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
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
    }
}

async function logoutStudent() {
    // Un cookie httpOnly non è cancellabile lato client: il logout richiede
    // una chiamata al server.
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
    // isoString arriva con l'offset UTC esplicito, quindi rappresenta un
    // istante preciso e non un orario ambiguo.
    const date = new Date(isoString);
    // Senza timezone esplicita il browser usa quella del dispositivo: è
    // così che un utente all'estero vede l'orario corretto per sé. Il
    // locale controlla solo la lingua del formato.
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

    // nasconde tutti gli step
    document.querySelectorAll('.step-content').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));

    // mostra lo step richiesto
    document.getElementById(stepId).classList.add('active');

    // aggiorna la barra degli step
    const stepNumber = stepId.replace('step-', '');
    if (!isNaN(stepNumber)) {
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
// Vengono mostrati solo gli slot compatibili con la durata selezionata:
// una durata diversa da quella dello slot verrebbe comunque rifiutata.
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

// Ora italiana dell'istante, indipendente dal fuso del visitatore.
// Serve ad applicare il vincolo sugli orari di inizio delle sessioni da
// 2 ore, che è espresso in ora italiana. new Date().getHours() userebbe
// il fuso del dispositivo e darebbe risultati diversi per utente.
function oraItaliana(isoString) {
    return parseInt(
        new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', hourCycle: 'h23' })
            .format(new Date(isoString))
    );
}

const ORE_INIZIO_VALIDE_2H = [15, 17];

function renderSlots() {
    const container = document.getElementById('slots-container');

    // Il calendario contiene solo slot da 1 ora. Una card da 2 ore è
    // virtuale: esiste se ci sono due slot adiacenti e l'orario di inizio
    // è fra quelli ammessi. Il backend riapplica la stessa regola al
    // momento della prenotazione; qui serve solo a scegliere cosa mostrare.
    const slotsUnOra = allSlots.filter(s => s.duration_hours === 1);

    let cardsDaMostrare;
    if (state.selectedHours === 1) {
        cardsDaMostrare = slotsUnOra;
    } else {
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
    // L'attributo onclick riceve solo valori numerici e una stringa ISO
    // generata dal backend: nessun dato compilato dall'utente entra qui.
}

// Quando l'utente clicca uno slot
function selectSlot(slotId, startTime) {
    state.selectedSlot = { id: slotId, start_time: startTime };

    // rimuove la selezione precedente
    document.querySelectorAll('.slot-card').forEach(c => c.classList.remove('selected'));

    // trova e seleziona la card cliccata
    event.currentTarget.classList.add('selected');

    // abilita il pulsante continua
    document.getElementById('btn-to-step2').disabled = false;
}

// Gestione bottoni servizio
document.querySelectorAll('.service-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.service-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.selectedService = btn.dataset.service;
    });
});

// Gestione bottoni durata
document.querySelectorAll('.duration-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
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

// Mostra il checkbox "usa pacchetto" se lo studente ha un pacchetto
// compatibile con la durata scelta. Da chiamare solo a login effettuato:
// l'endpoint identifica l'utente dal cookie e non accetta più un'email
// come parametro.
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
        // Nessun pacchetto utilizzabile: il form resta valido a prezzo pieno.
    }
}

document.getElementById('usa-pacchetto').addEventListener('change', aggiornaPrezzoRiepilogo);

// Richiamata anche al cambio lingua, quando lo step 3 è già visibile.
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
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!nome || !email) {
        alert(t('name_email_required'));
        return;
    }

    // L'uso di un pacchetto richiede il login: senza identità verificata
    // chiunque conoscesse l'email di un cliente potrebbe consumarne i
    // crediti. Per un ospite la ricerca viene saltata del tutto.
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
        // Disabilita il pulsante per evitare un doppio invio.

    try {
        // 1 — crea l'utente
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
        const user = await userResponse.json();
        state.userId = user.id;

        // Intenzione dell'utente, non un permesso: proprietà e capienza del
        // pacchetto sono riverificate dal server.
        const checkboxPacchetto = document.getElementById('usa-pacchetto');
        const packageId = (checkboxPacchetto.checked && state.pacchettoAttivo) ? state.pacchettoAttivo.id : null;

        // 2 — crea la prenotazione
        // Nessun header di autenticazione: il cookie di sessione viaggia da
        // solo ed è ciò che il server usa per verificare il pacchetto.
        const bookingResponse = await fetch('/bookings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: state.userId,
                // Serve al server per verificare che user_id appartenga a
                // chi sta prenotando, quando non c'è un login.
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
        // Qualsiasi errore riabilita il pulsante e mostra un messaggio,
        // invece di lasciare l'utente bloccato sullo stato di invio.
        alert(t('generic_error'));
        btn.disabled = false;
        btn.textContent = t('confirm_booking');
    }
});

// ─── CONSULENZA GRATUITA (20 minuti) ──────────────────────────
// Indipendente dal wizard: non tocca slot né prenotazioni, invia solo i
// contatti al coach.
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
// I pulsanti delle card aprono un unico form condiviso, ricordando quale
// pacchetto è stato scelto. Come la consulenza, non attiva nulla: invia
// una richiesta che il coach evade dopo il pagamento.
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
// i18n.js ritraduce da solo gli elementi con data-i18n. Qui si
// ridisegnano i contenuti generati da questo file, che non ne hanno.
document.addEventListener('langchange', () => {
    renderSlots();
    aggiornaRiepilogo();
    // La barra di login è costruita interamente qui: senza attributi
    // data-i18n va ricostruita a mano in entrambi gli stati.
    if (studentLoggedIn) {
        loadStudentProfile();
    } else {
        showLoginButton();
    }
});

// ─── AVVIO ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadSlots();
    initDiscordLogin();
});
