// ─── STATO GLOBALE ───────────────────────────────────────────
// Qui salviamo tutto quello che l'utente sceglie durante il flusso
const state = {
    selectedSlot: null,      // slot scelto
    selectedHours: 1,        // durata scelta
    selectedPrice: 35,       // prezzo calcolato
    userId: null,            // id utente creato nel DB
    bookingId: null          // id prenotazione creata nel DB
};

// ─── UTILITÀ ─────────────────────────────────────────────────
// Formatta una data ISO in formato leggibile italiano
function formatDate(isoString) {
    const date = new Date(isoString);
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
async function loadSlots() {
    try {
        // chiama l'API FastAPI
        const response = await fetch('/slots/');
        const slots = await response.json();

        const container = document.getElementById('slots-container');

        if (slots.length === 0) {
            container.innerHTML = '<p class="loading">Nessuno slot disponibile al momento.</p>';
            return;
        }

        // crea una card per ogni slot
        container.innerHTML = slots.map(slot => `
            <div class="slot-card" onclick="selectSlot(${slot.id}, '${slot.start_time}')">
                <div class="slot-date">${formatDate(slot.start_time)}</div>
                <div class="slot-time">${formatTime(slot.start_time)}</div>
            </div>
        `).join('');

    } catch (error) {
        document.getElementById('slots-container').innerHTML =
            '<p class="loading">Errore nel caricamento degli slot.</p>';
    }
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

// Gestione bottoni durata
document.querySelectorAll('.duration-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.selectedHours = parseInt(btn.dataset.hours);
        state.selectedPrice = parseInt(btn.dataset.price);
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
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!nome || !email) {
        alert('Nome e email sono obbligatori.');
        return;
    }

    // aggiorna il riepilogo
    document.getElementById('summary-slot').textContent =
        `${formatDate(state.selectedSlot.start_time)} alle ${formatTime(state.selectedSlot.start_time)}`;
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

    try {
        // 1 — crea l'utente
        const userResponse = await fetch('/users/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome: document.getElementById('nome').value.trim(),
                email: document.getElementById('email').value.trim(),
                showdown_username: document.getElementById('showdown').value.trim(),
                telefono: null
            })
        });

        if (!userResponse.ok) throw new Error('Errore creazione utente');
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
                note_cliente: document.getElementById('note').value.trim()
            })
        });

        if (!bookingResponse.ok) throw new Error('Errore creazione prenotazione');

        // successo
        showStep('step-success');

    } catch (error) {
        alert('Si è verificato un errore. Riprova.');
        btn.disabled = false;
        btn.textContent = '✓ Conferma prenotazione';
    }
});

// ─── AVVIO ────────────────────────────────────────────────────
// quando la pagina è pronta, carica gli slot
document.addEventListener('DOMContentLoaded', () => {
    loadSlots();
});