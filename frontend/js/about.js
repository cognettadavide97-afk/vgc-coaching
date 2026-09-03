// Script della pagina "Meet the Coach". L'unica parte dinamica è la
// vetrina delle recensioni approvate; il resto della pagina è statico.

// Duplicata da app.js e non condivisa: il progetto non ha un build step e
// ogni pagina carica solo gli script che le servono.
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

        // Placeholder e sottotitolo di attesa non servono più una volta
        // che ci sono recensioni da mostrare.
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
        // Rete assente o risposta non valida: resta il contenuto statico.
        // Non è una condizione da segnalare al visitatore.
    }
}

caricaRecensioniPubbliche();
