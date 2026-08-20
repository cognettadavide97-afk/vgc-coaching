// Cervello di frontend/about.html — pagina indipendente dal wizard di
// prenotazione (frontend/js/app.js). L'unica cosa dinamica qui è la
// vetrina recensioni: il resto della pagina è HTML statico.

// Identica a escapeHtmlPublic in frontend/js/app.js — duplicata qui invece
// di condivisa perché questo progetto non ha un build step (vedi i
// commenti sulle variabili CSS duplicate in frontend/css/admin.css per lo
// stesso motivo): ogni pagina carica solo gli script che le servono.
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

async function caricaRecensioniPubbliche() {
    const container = document.getElementById('reviews-list');
    if (!container) return;

    try {
        const res = await fetch('/bookings/recensioni/pubbliche');
        if (!res.ok) return;
        const recensioni = await res.json();

        if (recensioni.length === 0) return; // resta il placeholder statico già presente nell'HTML

        // Nasconde sia il placeholder ("nessuna recensione") sia il
        // sottotitolo ("appariranno presto qui") — entrambi non hanno più
        // senso una volta che ci sono recensioni vere da mostrare.
        document.querySelector('.reviews-placeholder').style.display = 'none';
        document.querySelector('.reviews-section .subtitle').style.display = 'none';

        container.innerHTML = recensioni.map(r => `
            <div class="review-card">
                <div class="review-stars">${'⭐'.repeat(r.voto)}</div>
                ${r.commento ? `<p class="review-comment">"${escapeHtml(r.commento)}"</p>` : ''}
                <p class="review-author">— ${escapeHtml(r.nome_cliente)}</p>
            </div>
        `).join('');
    } catch (error) {
        // Nessuna recensione da mostrare o rete assente: resta il
        // placeholder statico, non è un errore da segnalare al visitatore.
    }
}

caricaRecensioniPubbliche();
