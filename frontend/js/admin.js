// ─── TOKEN ───────────────────────────────────────────────────
// Il token JWT viene salvato in memoria — dura fino
// a quando la pagina è aperta
let token = null;

// ─── LOGIN ───────────────────────────────────────────────────
async function login() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const errore = document.getElementById('login-error');

    if (!username || !password) {
        errore.textContent = 'Inserisci username e password.';
        return;
    }

    try {
        // OAuth2PasswordRequestForm richiede form-urlencoded
        // non JSON — è uno standard specifico di OAuth2
        const body = new URLSearchParams();
        body.append('username', username);
        body.append('password', password);

        const response = await fetch('/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body
        });

        if (!response.ok) {
            errore.textContent = 'Credenziali non valide.';
            return;
        }

        const data = await response.json();
        token = data.access_token;

        // nasconde il login e mostra il pannello
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('admin-panel').style.display = 'flex';

        // carica i dati della dashboard
        caricaDashboard();

    } catch (error) {
        errore.textContent = 'Errore di connessione.';
    }
}

// ─── LOGOUT ──────────────────────────────────────────────────
function logout() {
    token = null;
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('admin-panel').style.display = 'none';
}

// ─── UTILITÀ ─────────────────────────────────────────────────
// aggiunge il token a ogni richiesta API
function authHeaders() {
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

// naviga tra le sezioni del pannello
function showSection(nome) {
    document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(`section-${nome}`).classList.add('active');
    event.currentTarget.classList.add('active');

    // carica i dati della sezione
    if (nome === 'dashboard') caricaDashboard();
    if (nome === 'prenotazioni') caricaPrenotazioni();
    if (nome === 'clienti') caricaClienti();
    if (nome === 'slots') caricaSlots();
}

// converte lo stato in un badge colorato
function badgeStato(stato) {
    const map = {
        'pending': '<span class="badge badge-pending">In attesa</span>',
        'confirmed': '<span class="badge badge-confirmed">Confermato</span>',
        'cancelled': '<span class="badge badge-cancelled">Cancellato</span>'
    };
    return map[stato] || stato;
}

// ─── DASHBOARD ───────────────────────────────────────────────
async function caricaDashboard() {
    try {
        const res = await fetch('/admin/dashboard', { headers: authHeaders() });
        const data = await res.json();

        document.getElementById('stat-totale').textContent = data.totale_prenotazioni;
        document.getElementById('stat-oggi').textContent = data.prenotazioni_oggi;
        document.getElementById('stat-incassato').textContent = `€${data.totale_incassato_euro.toFixed(2)}`;

        const container = document.getElementById('prossimi-slot');
        if (data.prossimi_slot_liberi.length === 0) {
            container.innerHTML = '<p style="color:#aaa">Nessuno slot libero disponibile.</p>';
        } else {
            container.innerHTML = `<div class="slot-list">${
                data.prossimi_slot_liberi.map(s => `
                    <div class="slot-item">
                        <span>📅 ${s.data}</span>
                        <span>🕐 ${s.ora}</span>
                    </div>
                `).join('')
            }</div>`;
        }
    } catch (error) {
        console.error('Errore dashboard:', error);
    }
}

// ─── PRENOTAZIONI ────────────────────────────────────────────
async function caricaPrenotazioni() {
    const stato = document.getElementById('filtro-stato').value;
    const url = stato ? `/admin/prenotazioni?stato=${stato}` : '/admin/prenotazioni';

    try {
        const res = await fetch(url, { headers: authHeaders() });
        const prenotazioni = await res.json();

        const container = document.getElementById('lista-prenotazioni');

        if (prenotazioni.length === 0) {
            container.innerHTML = '<p style="color:#aaa; padding:1rem">Nessuna prenotazione trovata.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Cliente</th>
                        <th>Data</th>
                        <th>Durata</th>
                        <th>Prezzo</th>
                        <th>Stato</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${prenotazioni.map(p => `
                        <tr>
                            <td>#${p.id}</td>
                            <td>
                                <strong>${p.cliente.nome}</strong><br>
                                <small style="color:#888">${p.cliente.email}</small>
                            </td>
                            <td>${p.slot.data} ${p.slot.ora}</td>
                            <td>${p.durata_ore}h</td>
                            <td>€${p.prezzo_euro.toFixed(2)}</td>
                            <td>${badgeStato(p.stato)}</td>
                            <td>
                                ${p.stato === 'pending' ? `
                                    <button class="action-btn action-confirm"
                                        onclick="aggiornaStato(${p.id}, 'confirmed')">
                                        ✓ Conferma
                                    </button>
                                ` : ''}
                                ${p.stato !== 'cancelled' ? `
                                    <button class="action-btn action-cancel"
                                        onclick="aggiornaStato(${p.id}, 'cancelled')">
                                        ✗ Cancella
                                    </button>
                                ` : ''}
                                <button class="action-btn action-note"
                                    onclick="modificaNota(${p.id}, '${(p.note_admin || '').replace(/'/g, "\\'")}')">
                                    📝 Nota
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore prenotazioni:', error);
    }
}

async function aggiornaStato(id, stato) {
    try {
        await fetch(`/admin/prenotazioni/${id}/stato?nuovo_stato=${stato}`, {
            method: 'PATCH',
            headers: authHeaders()
        });
        caricaPrenotazioni();
    } catch (error) {
        console.error('Errore aggiornamento stato:', error);
    }
}

async function modificaNota(id, notaAttuale) {
    const nuovaNota = prompt('Nota interna (non visibile al cliente):', notaAttuale);
    if (nuovaNota === null) return;

    try {
        await fetch(`/admin/prenotazioni/${id}/note?note=${encodeURIComponent(nuovaNota)}`, {
            method: 'PATCH',
            headers: authHeaders()
        });
        caricaPrenotazioni();
    } catch (error) {
        console.error('Errore nota:', error);
    }
}

// ─── CLIENTI ─────────────────────────────────────────────────
async function caricaClienti() {
    try {
        const res = await fetch('/admin/clienti', { headers: authHeaders() });
        const clienti = await res.json();

        const container = document.getElementById('lista-clienti');

        if (clienti.length === 0) {
            container.innerHTML = '<p style="color:#aaa; padding:1rem">Nessun cliente registrato.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Email</th>
                        <th>Showdown</th>
                        <th>Sessioni</th>
                        <th>Totale speso</th>
                        <th>Registrato il</th>
                    </tr>
                </thead>
                <tbody>
                    ${clienti.map(c => `
                        <tr>
                            <td><strong>${c.nome}</strong></td>
                            <td>${c.email}</td>
                            <td>${c.showdown || '—'}</td>
                            <td>${c.sessioni_totali}</td>
                            <td>€${c.totale_speso_euro.toFixed(2)}</td>
                            <td>${c.registrato_il}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore clienti:', error);
    }
}

// ─── SLOTS ───────────────────────────────────────────────────
async function caricaSlots() {
    try {
        const res = await fetch('/admin/slots', { headers: authHeaders() });
        const slots = await res.json();

        const container = document.getElementById('lista-slots');

        if (slots.length === 0) {
            container.innerHTML = '<p style="color:#aaa; padding:1rem">Nessuno slot creato.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Ora</th>
                        <th>Durata</th>
                        <th>Stato</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${slots.map(s => `
                        <tr>
                            <td>${s.data}</td>
                            <td>${s.ora}</td>
                            <td>${s.durata_ore}h</td>
                            <td>
                                ${s.disponibile
                                    ? '<span class="badge badge-confirmed">Libero</span>'
                                    : '<span class="badge badge-pending">Prenotato</span>'
                                }
                            </td>
                            <td>
                                ${s.disponibile ? `
                                    <button class="action-btn action-delete"
                                        onclick="eliminaSlot(${s.id})">
                                        🗑 Elimina
                                    </button>
                                ` : '—'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore slots:', error);
    }
}

async function creaSlot() {
    const data = document.getElementById('nuovo-slot-data').value;
    const durata = document.getElementById('nuovo-slot-durata').value;

    if (!data) {
        alert('Seleziona una data e un orario.');
        return;
    }

    try {
        await fetch('/slots/', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                start_time: data,
                duration_hours: parseInt(durata)
            })
        });
        document.getElementById('nuovo-slot-data').value = '';
        caricaSlots();
    } catch (error) {
        console.error('Errore creazione slot:', error);
    }
}

async function eliminaSlot(id) {
    if (!confirm('Sei sicuro di voler eliminare questo slot?')) return;

    try {
        await fetch(`/admin/slots/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        caricaSlots();
    } catch (error) {
        console.error('Errore eliminazione slot:', error);
    }
}

// ─── EXPORT CSV ──────────────────────────────────────────────
function exportCSV() {
    // apre il link di download con il token nell'URL
    window.open(`/admin/export/csv?token=${token}`, '_blank');
}

// ─── AVVIO ───────────────────────────────────────────────────
// permette di fare login premendo Invio
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('login-password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });
});