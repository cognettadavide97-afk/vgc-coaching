// Script della pagina di recensione, raggiunta dal link inviato per email
// dopo la sessione. L'autorizzazione è il token nella query string: senza
// quello, o senza booking_id, il form non viene nemmeno mostrato.

const urlParams = new URLSearchParams(window.location.search);
const bookingId = urlParams.get('booking_id');
const token = urlParams.get('token');

let votoSelezionato = null;

const bottoniVoto = document.querySelectorAll('#voto-buttons .duration-btn');
bottoniVoto.forEach(btn => {
    btn.addEventListener('click', () => {
        bottoniVoto.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        votoSelezionato = parseInt(btn.dataset.voto);
    });
});

function mostraEsito(messaggio, nascondiForm) {
    document.getElementById('recensione-esito').textContent = messaggio;
    if (nascondiForm) {
        document.getElementById('recensione-form-box').style.display = 'none';
    }
}

document.getElementById('btn-invia-recensione').addEventListener('click', async () => {
    if (!bookingId || !token) {
        mostraEsito('Invalid link: missing required parameters.', true);
        return;
    }
    if (!votoSelezionato) {
        alert('Please select a rating from 1 to 5.');
        return;
    }

    const btn = document.getElementById('btn-invia-recensione');
    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
        const res = await fetch(`/bookings/${bookingId}/recensione`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token,
                voto: votoSelezionato,
                commento: document.getElementById('commento').value.trim()
            })
        });

        if (!res.ok) {
            const errore = await res.json().catch(() => ({}));
            throw new Error(errore.detail || 'Error submitting review');
        }

        mostraEsito('Thanks for your feedback!', true);
    } catch (error) {
        mostraEsito(error.message || 'An error occurred. Please try again.', false);
        btn.disabled = false;
        btn.textContent = 'Submit review';
    }
});

if (!bookingId || !token) {
    mostraEsito('Invalid link: missing required parameters.', true);
}
