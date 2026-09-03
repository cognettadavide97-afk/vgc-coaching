// Script del pannello di amministrazione: dashboard, analytics,
// prenotazioni, clienti, disponibilità, pacchetti e recensioni.
//
// È il file più grande del frontend perché il pannello copre molte aree.
// Ogni sezione segue lo stesso schema: una funzione caricaX() che
// interroga l'API, costruisce l'HTML e lo inserisce nel contenitore.

// ─── TOKEN ───────────────────────────────────────────────────
// Il token vive solo in memoria: si perde ricaricando la pagina e il coach
// deve rifare il login. È deliberato — dà accesso ai dati di tutti i
// clienti e non merita la comodità di una sessione persistente.
let token = null;

// ─── PAGINAZIONE (helper condiviso da prenotazioni/clienti/slot) ─
// tiene traccia della pagina corrente di ciascuna lista, cosi le azioni
// (nota, cambio stato, elimina...) possono ricaricare la stessa pagina
// invece di riportare sempre l'admin a pagina 1
const paginaCorrente = { prenotazioni: 1, clienti: 1, slots: 1 };

// ─── AZIONI SU RIGHE (delegazione eventi, al posto di onclick inline) ─
// PERCHÉ esiste questo blocco: prima i bottoni "Note/Pacchetto/Elimina"
// dei clienti e "Nota" delle prenotazioni venivano generati interpolando
// dati del PUBBLICO (il nome del cliente, inserito nel form senza login)
// dentro un attributo onclick="funzione(id, 'NOME')". escapeHtml() non
// protegge l'apice singolo né il backslash — e proprio quei caratteri
// chiudono la stringa dentro l'onclick: un nome tipo  ');codice;//  faceva
// eseguire codice arbitrario nel browser del coach al click (XSS). Il
// .replace(/'/g, "\\'") che doveva difendere usava un escaping in stile
// JavaScript, che dentro un attributo HTML non ha alcun effetto.
//
// La cura NON è "escapare meglio", è NON mescolare più dato e codice: il
// bottone porta solo l'id (un numero, non iniettabile) in un attributo
// data-*, e un unico gestore agganciato al contenitore con addEventListener
// ("delegazione") legge quell'id, ritrova l'oggetto completo in una cache
// per-id, e chiama la funzione giusta. Il nome del cliente non entra più in
// nessun attributo né in nessuna stringa di codice.
//
// La cache viene riscritta a ogni caricamento pagina (indicizzata per id);
// le funzioni chiamate ricevono il nome via JavaScript normale (mai via
// HTML), e dove lo mostrano in un modale lo passano comunque da escapeHtml
// (contesto "contenuto", lì escapeHtml è la difesa giusta).
let clientiPerId = {};
let prenotazioniPerId = {};

function agganciaDelegato(container, gestore) {
    // Aggancia il gestore UNA VOLTA SOLA per contenitore: il listener sta
    // sul contenitore (che resta lo stesso), non sui bottoni (ricreati a
    // ogni innerHTML), quindi sopravvive ai re-render e non si duplica. Il
    // flag data-delegato evita di riagganciarlo a ogni caricaX().
    if (!container || container.dataset.delegato) return;
    container.addEventListener('click', gestore);
    container.dataset.delegato = '1';
}

function gestisciAzioneCliente(e) {
    const btn = e.target.closest('button[data-azione]');
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const cliente = clientiPerId[id];
    if (!cliente) return;
    if (btn.dataset.azione === 'note') apriNoteCliente(id, cliente.nome);
    else if (btn.dataset.azione === 'pacchetto') apriAssegnaPacchetto(id, cliente.nome);
    else if (btn.dataset.azione === 'elimina') eliminaCliente(id, cliente.nome);
}

function gestisciAzionePrenotazione(e) {
    const btn = e.target.closest('button[data-azione]');
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.azione === 'cancella') aggiornaStato(id, 'cancelled');
    else if (btn.dataset.azione === 'noshow') aggiornaStato(id, 'no_show');
    else if (btn.dataset.azione === 'nota') {
        const p = prenotazioniPerId[id];
        modificaNota(id, p ? (p.note_admin || '') : '');
    }
}

function renderPaginazione(dati, nomeFunzione) {
    // nomeFunzione è il nome della funzione che ricarica la lista,
    // interpolato negli onclick: è ciò che rende questo helper riusabile
    // dalle tre liste paginate invece di duplicarlo.
    if (dati.pagine_totali <= 1) return '';
    return `
        <div class="paginazione">
            <button class="btn-secondary" ${dati.pagina <= 1 ? 'disabled' : ''}
                onclick="${nomeFunzione}(${dati.pagina - 1})">← Precedente</button>
            <span>Pagina ${dati.pagina} di ${dati.pagine_totali} (${dati.totale} totali)</span>
            <button class="btn-secondary" ${dati.pagina >= dati.pagine_totali ? 'disabled' : ''}
                onclick="${nomeFunzione}(${dati.pagina + 1})">Successiva →</button>
        </div>
    `;
}

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
        // L'endpoint di login accetta form-urlencoded, non JSON: è il
        // formato previsto dallo standard OAuth2.
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
// Header di autenticazione condivisi da tutte le chiamate del file.
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

    // Ogni cambio sezione ricarica i dati: evita di mostrare valori
    // rimasti in pagina da una visita precedente.
    if (nome === 'dashboard') caricaDashboard();
    if (nome === 'prenotazioni') caricaPrenotazioni();
    if (nome === 'clienti') caricaClienti();
    if (nome === 'slots') {
        caricaSlots();
        caricaRegole();
        caricaBlocchi();
    }
    if (nome === 'pacchetti') caricaPacchetti();
    if (nome === 'recensioni') caricaRecensioni();
}

const GIORNI_SETTIMANA = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];
// L'ordine è vincolante: l'indice deve combaciare con la numerazione del
// backend (0=lunedì ... 6=domenica), perché la traduzione avviene per
// posizione.

const SERVICE_LABELS = {
    vod_review: 'VOD Review',
    team_building: 'Team Building',
    bo3_sparring: 'Bo3 Sparring',
    tournament_prep: 'Tournament Prep'
};

// Copia ridotta del catalogo, con i soli campi necessari a comporre il
// modale di assegnazione. La fonte autoritativa per prezzi e sessioni
// resta il backend.
const CATALOGO_PACCHETTI = {
    intro: { nome: 'Competitive Intro', sessioni: 2, prezzo: 70 },
    team: { nome: 'Team Building Session', sessioni: 4, prezzo: 130 },
    tour: { nome: 'Tournament Prep', sessioni: 6, prezzo: 190 }
};

// sfugge caratteri HTML per evitare che testo inserito dallo studente
// (link VOD, codice replay, ecc.) venga interpretato come markup nel pannello
function escapeHtml(str) {
    // Rende inerte il markup nei dati mostrati nel pannello. Serve perché
    // molti di questi valori (nome, note, link, codici) sono compilati dal
    // pubblico senza autenticazione.
    //
    // Attenzione: è adatta al contenuto di un elemento, non a costruire
    // attributi o codice. Non protegge apici e backslash.
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// mostra il link VOD come anchor cliccabile solo se è davvero un URL http/https,
// altrimenti come testo semplice (sempre sfuggito)
function renderVodLink(link) {
    const safe = escapeHtml(link);
    // Accetta come link cliccabile solo http:// e https://. Il controllo
    // esiste per escludere schemi come javascript:, che in un attributo
    // href eseguirebbero codice invece di aprire una pagina.
    if (/^https?:\/\//i.test(link)) {
        return `<a href="${safe}" target="_blank" rel="noopener noreferrer">VOD ↗</a>`;
    }
    return safe;
}

// converte lo stato in un badge colorato
function badgeStato(stato) {
    const map = {
        'confirmed': '<span class="badge badge-confirmed">Confermato</span>',
        'cancelled': '<span class="badge badge-cancelled">Cancellato</span>',
        'no_show': '<span class="badge badge-no-show">No-show</span>'
    };
    // map[stato] cerca la chiave dentro l'oggetto — se "stato" non è
    // nessuna delle tre chiavi previste, map[stato] vale "undefined", e
    // "|| stato" fa da rete di sicurezza restituendo il valore originale
    // così com'è, invece di mostrare "undefined" nella pagina.
    return map[stato] || stato;
}

// ─── DASHBOARD ───────────────────────────────────────────────
async function caricaDashboard() {
    // Le due richieste sono indipendenti e partono insieme: attenderle in
    // sequenza raddoppierebbe il tempo di apertura del pannello.
    // caricaAnalytics gestisce già i propri errori.
    const analyticsPromise = caricaAnalytics();

    try {
        const res = await fetch('/admin/dashboard', { headers: authHeaders() });
        const data = await res.json();

        document.getElementById('stat-totale').textContent = data.totale_prenotazioni;
        document.getElementById('stat-oggi').textContent = data.prenotazioni_oggi;
        // .toFixed(2) formatta un numero con esattamente 2 cifre decimali
        // (es. 35 diventa "35.00") — utile qui perché stiamo mostrando un
        // importo in euro, che vogliamo sempre con i centesimi visibili.
        document.getElementById('stat-incassato').textContent = `€${data.totale_incassato_euro.toFixed(2)}`;
        document.getElementById('stat-voto-medio').textContent =
            data.media_voto_recensioni !== null ? `⭐ ${data.media_voto_recensioni}` : '—';

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

    await analyticsPromise;
}

function renderBarChart(container, dati, chiaveEtichetta, chiaveValore, formattatore) {
    // Grafico a barre senza librerie: div con larghezza percentuale.
    // Sufficiente per queste metriche e coerente con l'assenza di build.
    if (!container) return;
    // .every(...) restituisce true solo se TUTTI gli elementi dell'array
    // soddisfano la condizione — qui: "sono tutti i valori pari a zero?"
    // (cioè "non c'è ancora nessun dato interessante da mostrare").
    if (dati.length === 0 || dati.every(d => d[chiaveValore] === 0)) {
        container.innerHTML = '<p style="color:#aaa">Nessun dato ancora disponibile.</p>';
        return;
    }
    // Il massimo normalizza le barre al 100%. Il secondo argomento evita
    // una divisione per zero quando tutti i valori sono nulli.
    const max = Math.max(...dati.map(d => d[chiaveValore]), 1);
    container.innerHTML = dati.map(d => `
        <div class="bar-row">
            <span class="bar-label">${escapeHtml(String(d[chiaveEtichetta]))}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width:${(d[chiaveValore] / max) * 100}%"></div>
            </div>
            <span class="bar-value">${formattatore ? formattatore(d[chiaveValore]) : d[chiaveValore]}</span>
        </div>
    `).join('');
    // formattatore, se passato, personalizza la resa del valore (per
    // esempio l'importo in euro).
}

async function caricaAnalytics() {
    try {
        const res = await fetch('/admin/analytics', { headers: authHeaders() });
        const analytics = await res.json();

        document.getElementById('stat-no-show').textContent = `${analytics.tasso_no_show_percento}%`;
        document.getElementById('stat-clienti-nuovi').textContent = analytics.clienti_nuovi;
        document.getElementById('stat-clienti-ricorrenti').textContent = analytics.clienti_ricorrenti;

        renderBarChart(
            document.getElementById('chart-sessioni-mese'),
            analytics.sessioni_per_mese, 'mese', 'conteggio'
        );
        renderBarChart(
            document.getElementById('chart-incasso-mese'),
            analytics.incasso_per_mese, 'mese', 'euro',
            v => `€${v.toFixed(2)}`
        );
        renderBarChart(
            document.getElementById('chart-servizi'),
            // renderBarChart mostra il campo così com'è: qui il codice tecnico
            // del servizio viene sostituito con la sua etichetta leggibile.
            analytics.servizi_piu_richiesti.map(s => ({ ...s, servizio: SERVICE_LABELS[s.servizio] || s.servizio })),
            'servizio', 'conteggio'
        );
    } catch (error) {
        console.error('Errore analytics:', error);
    }
}

// ─── PRENOTAZIONI ────────────────────────────────────────────
async function caricaPrenotazioni(pagina = 1) {
    paginaCorrente.prenotazioni = pagina;
    const stato = document.getElementById('filtro-stato').value;
    const params = new URLSearchParams({ pagina: pagina, per_pagina: 20 });
    if (stato) params.set('stato', stato);

    try {
        // URLSearchParams gestisce da sé la codifica dei caratteri speciali.
        const res = await fetch(`/admin/prenotazioni?${params}`, { headers: authHeaders() });
        const dati = await res.json();
        const prenotazioni = dati.items;

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
                        <th>Servizio</th>
                        <th>Data</th>
                        <th>Durata</th>
                        <th>Prezzo</th>
                        <th>Risorse</th>
                        <th>Voto</th>
                        <th>Stato</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${prenotazioni.map(p => `
                        <tr>
                            <td>#${p.id}</td>
                            <td>
                                <strong>${escapeHtml(p.cliente.nome)}</strong><br>
                                <small style="color:#888">${escapeHtml(p.cliente.email)}</small>
                                ${p.cliente.discord ? `<br><small style="color:#888">Discord: ${escapeHtml(p.cliente.discord)}</small>` : ''}
                            </td>
                            <td>${SERVICE_LABELS[p.servizio] || p.servizio}</td>
                            <td>${p.slot.data} ${p.slot.ora}</td>
                            <td>${p.durata_ore}h</td>
                            <td>€${p.prezzo_euro.toFixed(2)}</td>
                            <td style="font-size: 0.85rem;">
                                ${p.vod_link ? renderVodLink(p.vod_link) : ''}
                                ${p.vod_link && p.replay_code ? '<br>' : ''}
                                ${p.replay_code ? escapeHtml(p.replay_code) : ''}
                                ${!p.vod_link && !p.replay_code ? '—' : ''}
                            </td>
                            <td>${p.voto ? `⭐ ${p.voto}` : '—'}</td>
                            <td>${badgeStato(p.stato)}</td>
                            <td>
                                ${p.stato === 'confirmed' ? `
                                    <button class="action-btn action-cancel"
                                        data-azione="cancella" data-id="${p.id}">
                                        ✗ Cancella
                                    </button>
                                    <button class="action-btn action-no-show"
                                        data-azione="noshow" data-id="${p.id}">
                                        🚫 No-show
                                    </button>
                                ` : ''}
                                <button class="action-btn action-note"
                                    data-azione="nota" data-id="${p.id}">
                                    📝 Nota
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${renderPaginazione(dati, 'caricaPrenotazioni')}
        `;
        // I bottoni azione portano solo data-azione/data-id (vedi il blocco
        // "AZIONI SU RIGHE" in cima al file): la nota — testo potenzialmente
        // scritto dal coach, ma comunque una stringa qualsiasi — viene
        // ritrovata qui per id invece di essere interpolata in un onclick.
        prenotazioniPerId = {};
        prenotazioni.forEach(p => { prenotazioniPerId[p.id] = p; });
        agganciaDelegato(container, gestisciAzionePrenotazione);
    } catch (error) {
        console.error('Errore prenotazioni:', error);
    }
}

async function aggiornaStato(id, stato) {
    try {
        // nuovo_stato viaggia nel body JSON, non più come query param (vedi
        // BookingStatoUpdate in backend/schemas/booking.py) — uno stato
        // finiva altrimenti nei log di accesso del server/proxy.
        await fetch(`/admin/prenotazioni/${id}/stato`, {
            method: 'PATCH',
            headers: authHeaders(),
            body: JSON.stringify({ nuovo_stato: stato })
        });
        caricaPrenotazioni(paginaCorrente.prenotazioni);
    } catch (error) {
        console.error('Errore aggiornamento stato:', error);
    }
}

async function modificaNota(id, notaAttuale) {
    // prompt è sufficiente per una modifica testuale rapida: non vale un
    // form dedicato.
    const nuovaNota = prompt('Nota interna (non visibile al cliente):', notaAttuale);
    if (nuovaNota === null) return;

    try {
        // note viaggia nel body JSON, non più come query param (vedi
        // BookingNoteUpdate in backend/schemas/booking.py) — un testo
        // potenzialmente sensibile su un cliente finiva altrimenti nei log
        // di accesso del server/proxy e nella cronologia del browser.
        await fetch(`/admin/prenotazioni/${id}/note`, {
            method: 'PATCH',
            headers: authHeaders(),
            body: JSON.stringify({ note: nuovaNota })
        });
        caricaPrenotazioni(paginaCorrente.prenotazioni);
    } catch (error) {
        console.error('Errore nota:', error);
    }
}

// ─── CLIENTI ─────────────────────────────────────────────────
async function caricaClienti(pagina = 1) {
    paginaCorrente.clienti = pagina;
    try {
        const res = await fetch(`/admin/clienti?pagina=${pagina}&per_pagina=20`, { headers: authHeaders() });
        const dati = await res.json();
        const clienti = dati.items;

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
                        <th>Categoria</th>
                        <th>Discord</th>
                        <th>Sessioni</th>
                        <th>Totale speso</th>
                        <th>Registrato il</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${clienti.map(c => `
                        <tr>
                            <td><strong>${escapeHtml(c.nome)}</strong></td>
                            <td>${escapeHtml(c.email)}</td>
                            <td>${escapeHtml(c.categoria) || '—'}</td>
                            <td>${escapeHtml(c.discord) || '—'}</td>
                            <td>${c.sessioni_totali}</td>
                            <td>€${c.totale_speso_euro.toFixed(2)}</td>
                            <td>${c.registrato_il}</td>
                            <td>
                                <button class="action-btn action-note"
                                    data-azione="note" data-id="${c.id}">
                                    📋 Note (${c.note_totali})
                                </button>
                                <button class="action-btn action-note"
                                    data-azione="pacchetto" data-id="${c.id}">
                                    🎁 Pacchetto
                                </button>
                                <button class="action-btn action-delete"
                                    data-azione="elimina" data-id="${c.id}">
                                    🗑️ Elimina
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${renderPaginazione(dati, 'caricaClienti')}
        `;
        // Il nome del cliente (dato pubblico, dal form senza login) non è
        // più interpolato negli onclick: i bottoni portano solo data-id, e
        // il gestore delegato ritrova il cliente qui per id — vedi il blocco
        // "AZIONI SU RIGHE" in cima al file per il perché (protezione XSS).
        clientiPerId = {};
        clienti.forEach(c => { clientiPerId[c.id] = c; });
        agganciaDelegato(container, gestisciAzioneCliente);
    } catch (error) {
        console.error('Errore clienti:', error);
    }
}

// ─── CANCELLAZIONE CLIENTE (diritto all'oblio, Art. 17 GDPR) ──
async function eliminaCliente(userId, nomeCliente) {
    // Conferma esplicita che elenca cosa verrà eliminato: l'azione cancella
    // anche prenotazioni, note e recensioni, ed è irreversibile.
    if (!confirm(`Eliminare definitivamente ${nomeCliente} e TUTTI i suoi dati (prenotazioni, note, recensioni, pacchetti)? L'azione non è reversibile.`)) return;

    try {
        const res = await fetch(`/admin/clienti/${userId}`, {
            method: 'DELETE',
            headers: authHeaders()
        });

        if (!res.ok) {
            const errore = await res.json();
            alert(errore.detail || 'Errore durante l\'eliminazione del cliente.');
            return;
        }

        caricaClienti(paginaCorrente.clienti);
    } catch (error) {
        console.error('Errore eliminazione cliente:', error);
        alert('Errore di connessione durante l\'eliminazione.');
    }
}

// ─── NOTE TECNICHE CLIENTE (mini-CRM) ─────────────────────────
async function apriNoteCliente(userId, nomeCliente) {
    // Il modale viene creato alla prima apertura e poi riusato.
    let overlay = document.getElementById('note-modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'note-modal-overlay';
        overlay.className = 'modal-overlay';
        document.body.appendChild(overlay);
    }

    overlay.innerHTML = `
        <div class="modal-card">
            <h3>📋 Note tecniche — ${escapeHtml(nomeCliente)}</h3>
            <div id="note-modal-lista"><p style="color:#aaa">Caricamento...</p></div>
            <textarea id="nuova-nota-testo" rows="3" placeholder="Es: Fatica a gestire i team Trick Room, rivedere i predict con Dondozo..."></textarea>
            <div class="modal-actions">
                <button class="btn-secondary" onclick="chiudiNoteCliente()">Chiudi</button>
                <button class="btn-primary" onclick="aggiungiNotaCliente(${userId})">+ Aggiungi nota</button>
            </div>
        </div>
    `;
    overlay.style.display = 'flex';

    await caricaNoteCliente(userId);
}

async function caricaNoteCliente(userId) {
    const container = document.getElementById('note-modal-lista');
    try {
        const res = await fetch(`/admin/clienti/${userId}/note`, { headers: authHeaders() });
        const note = await res.json();

        if (note.length === 0) {
            container.innerHTML = '<p style="color:#aaa">Nessuna nota ancora per questo cliente.</p>';
            return;
        }

        container.innerHTML = note.map(n => `
            <div class="nota-item">
                <div class="nota-data">${n.created_at.replace('T', ' ').slice(0, 16)}</div>
                <div class="nota-testo">${escapeHtml(n.nota)}</div>
            </div>
        `).join('');
        // Formattazione puramente testuale invece di ricostruire una data:
        // evita di reintrodurre l'ambiguità sul fuso orario.
    } catch (error) {
        container.innerHTML = '<p style="color:#e74c3c">Errore nel caricamento delle note.</p>';
    }
}

async function aggiungiNotaCliente(userId) {
    const campo = document.getElementById('nuova-nota-testo');
    const testo = campo.value.trim();
    if (!testo) return;

    try {
        const res = await fetch(`/admin/clienti/${userId}/note`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ nota: testo })
        });
        if (!res.ok) {
            alert('Errore durante il salvataggio della nota.');
            return;
        }
        campo.value = '';
        await caricaNoteCliente(userId);
        caricaClienti(paginaCorrente.clienti); // aggiorna il conteggio note nella tabella
    } catch (error) {
        alert('Errore di connessione durante il salvataggio.');
    }
}

function chiudiNoteCliente() {
    const overlay = document.getElementById('note-modal-overlay');
    if (overlay) overlay.style.display = 'none';
}

// ─── PACCHETTI ───────────────────────────────────────────────
// Stesso pattern del modale note tecniche sopra (apriNoteCliente):
// un overlay creato una sola volta con document.createElement e poi
// riusato, riempito ogni volta con contenuto fresco.
function apriAssegnaPacchetto(userId, nomeCliente) {
    let overlay = document.getElementById('pacchetto-modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'pacchetto-modal-overlay';
        overlay.className = 'modal-overlay';
        document.body.appendChild(overlay);
    }

    overlay.innerHTML = `
        <div class="modal-card">
            <h3>🎁 Assegna pacchetto — ${escapeHtml(nomeCliente)}</h3>
            <p style="font-size: 0.85rem; color: #888;">
                Assegna SOLO dopo aver ricevuto il pagamento (concordato privatamente). Sessioni, durata e prezzo sono fissi dal catalogo, non modificabili qui.
            </p>
            ${Object.entries(CATALOGO_PACCHETTI).map(([chiave, p]) => `
                <button class="action-btn action-note pacchetto-scelta" style="width:100%; margin-bottom:0.5rem; text-align:left;"
                    data-tipo="${chiave}">
                    ${p.nome} — ${p.sessioni} sessioni — €${p.prezzo}
                </button>
            `).join('')}
            <div class="modal-actions">
                <button class="btn-secondary" onclick="chiudiAssegnaPacchetto()">Chiudi</button>
            </div>
        </div>
    `;
    // I bottoni del catalogo portano solo data-tipo (una chiave fissa e
    // fidata: intro/team/tour); userId e nomeCliente restano in questa
    // funzione e arrivano ad assegnaPacchetto via JavaScript, senza mai
    // passare per un attributo HTML — così anche qui nessun dato del
    // cliente finisce dentro codice generato come stringa.
    overlay.querySelectorAll('.pacchetto-scelta').forEach(btn => {
        btn.addEventListener('click', () => assegnaPacchetto(userId, btn.dataset.tipo, nomeCliente));
    });
    overlay.style.display = 'flex';
}

async function assegnaPacchetto(userId, tipo, nomeCliente) {
    if (!confirm(`Confermi di aver già ricevuto il pagamento e vuoi assegnare "${CATALOGO_PACCHETTI[tipo].nome}" a ${nomeCliente}?`)) return;

    try {
        const res = await fetch('/admin/pacchetti', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ user_id: userId, tipo })
        });
        if (!res.ok) {
            alert('Errore durante l\'assegnazione del pacchetto.');
            return;
        }
        chiudiAssegnaPacchetto();
        alert('Pacchetto assegnato.');
    } catch (error) {
        alert('Errore di connessione durante l\'assegnazione.');
    }
}

function chiudiAssegnaPacchetto() {
    const overlay = document.getElementById('pacchetto-modal-overlay');
    if (overlay) overlay.style.display = 'none';
}

async function caricaPacchetti() {
    const container = document.getElementById('lista-pacchetti');
    try {
        const res = await fetch('/admin/pacchetti', { headers: authHeaders() });
        const pacchetti = await res.json();

        if (pacchetti.length === 0) {
            container.innerHTML = '<p style="color:#aaa; padding:1rem">Nessun pacchetto assegnato ancora.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>ID Cliente</th>
                        <th>Tipo</th>
                        <th>Sessioni</th>
                        <th>Prezzo</th>
                        <th>Assegnato il</th>
                    </tr>
                </thead>
                <tbody>
                    ${pacchetti.map(p => `
                        <tr>
                            <td>#${p.user_id}</td>
                            <td>${CATALOGO_PACCHETTI[p.tipo]?.nome || p.tipo}</td>
                            <td>${p.sessioni_usate}/${p.sessioni_totali}</td>
                            <td>€${(p.prezzo_cents / 100).toFixed(2)}</td>
                            <td>${p.created_at.replace('T', ' ').slice(0, 16)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore pacchetti:', error);
    }
}

// ─── RECENSIONI ──────────────────────────────────────────────
async function caricaRecensioni() {
    const container = document.getElementById('lista-recensioni');
    const filtro = document.getElementById('filtro-recensioni').value;
    try {
        const url = filtro ? `/admin/recensioni?approvata=${filtro}` : '/admin/recensioni';
        const res = await fetch(url, { headers: authHeaders() });
        const recensioni = await res.json();

        if (recensioni.length === 0) {
            container.innerHTML = '<p style="color:#aaa; padding:1rem">Nessuna recensione da mostrare.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>Cliente</th>
                        <th>Servizio</th>
                        <th>Voto</th>
                        <th>Commento</th>
                        <th>Data</th>
                        <th>Stato</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${recensioni.map(r => `
                        <tr>
                            <td>${escapeHtml(r.cliente.nome)}<br><small style="color:#888">${escapeHtml(r.cliente.email)}</small></td>
                            <td>${SERVICE_LABELS[r.servizio] || r.servizio}</td>
                            <td>${'⭐'.repeat(r.voto)}</td>
                            <td>${r.commento ? escapeHtml(r.commento) : '<span style="color:#aaa">—</span>'}</td>
                            <td>${r.created_at}</td>
                            <td>${r.approvata
                                ? '<span class="badge badge-confirmed">Approvata</span>'
                                : '<span class="badge badge-pending">In attesa</span>'}</td>
                            <td>
                                ${r.approvata
                                    ? `<button class="action-btn action-cancel" onclick="impostaApprovazioneRecensione(${r.id}, false)">Ritira</button>`
                                    : `<button class="action-btn action-confirm" onclick="impostaApprovazioneRecensione(${r.id}, true)">✓ Approva</button>`}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore recensioni:', error);
    }
}

async function impostaApprovazioneRecensione(id, approvata) {
    try {
        await fetch(`/admin/recensioni/${id}`, {
            method: 'PATCH',
            headers: authHeaders(),
            body: JSON.stringify({ approvata })
        });
        caricaRecensioni();
    } catch (error) {
        console.error('Errore approvazione recensione:', error);
    }
}

// ─── SLOTS ───────────────────────────────────────────────────
async function caricaSlots(pagina = 1) {
    paginaCorrente.slots = pagina;
    try {
        const res = await fetch(`/admin/slots?pagina=${pagina}&per_pagina=20`, { headers: authHeaders() });
        const dati = await res.json();
        const slots = dati.items;

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
                                    : s.bloccato_da_calendario
                                        ? '<span class="badge badge-cancelled">Bloccato (calendario)</span>'
                                        : s.bloccato_da_admin
                                            ? '<span class="badge badge-no-show">Bloccato (ferie)</span>'
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
            ${renderPaginazione(dati, 'caricaSlots')}
        `;
        // L'ordine dei casi conta: "prenotato" è il ramo residuo, quando
        // nessun flag di blocco è attivo.
    } catch (error) {
        console.error('Errore slots:', error);
    }
}

async function sincronizzaCalendario() {
    try {
        const res = await fetch('/admin/slots/sync-calendario', {
            method: 'POST',
            headers: authHeaders()
        });
        if (!res.ok) {
            alert('Errore durante la sincronizzazione con il calendario.');
            return;
        }
        const data = await res.json();
        alert(`Sincronizzazione completata: ${data.slot_bloccati} slot bloccati per eventi sul calendario.`);
        caricaSlots(paginaCorrente.slots);
    } catch (error) {
        console.error('Errore sync calendario:', error);
        alert('Errore di connessione durante la sincronizzazione.');
    }
}

// ─── DISPONIBILITÀ RICORRENTE ─────────────────────────────────
async function caricaRegole() {
    const container = document.getElementById('lista-regole');
    try {
        const res = await fetch('/admin/disponibilita/regole', { headers: authHeaders() });
        const regole = await res.json();

        if (regole.length === 0) {
            container.innerHTML = '<p style="color:#aaa; margin-top:1rem">Nessuna regola ricorrente.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table" style="margin-top:1rem">
                <thead>
                    <tr>
                        <th>Giorno</th>
                        <th>Orario</th>
                        <th>Durata slot</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${regole.map(r => `
                        <tr>
                            <td>${GIORNI_SETTIMANA[r.giorno_settimana]}</td>
                            <td>${r.ora_inizio.slice(0, 5)} – ${r.ora_fine.slice(0, 5)}</td>
                            <td>${r.durata_slot_ore}h</td>
                            <td>
                                <button class="action-btn action-delete" onclick="eliminaRegola(${r.id})">
                                    🗑 Elimina
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
            // L'orario arriva con i secondi, che qui non servono.
    } catch (error) {
        console.error('Errore caricamento regole:', error);
    }
}

async function creaRegolaDisponibilita() {
    const giorno = document.getElementById('regola-giorno').value;
    const oraInizio = document.getElementById('regola-ora-inizio').value;
    const oraFine = document.getElementById('regola-ora-fine').value;

    if (!oraInizio || !oraFine) {
        alert('Inserisci ora di inizio e fine.');
        return;
    }

    try {
        const res = await fetch('/admin/disponibilita/regole', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                giorno_settimana: parseInt(giorno),
                ora_inizio: oraInizio,
                ora_fine: oraFine,
                durata_slot_ore: 1
            })
        });

        if (!res.ok) {
            const errore = await res.json();
            alert(errore.detail || 'Errore durante la creazione della regola.');
            return;
        }

        const data = await res.json();
        alert(`Regola creata: ${data.slot_creati} slot generati fino a fine mese.`);
        caricaRegole();
        caricaSlots(paginaCorrente.slots);
    } catch (error) {
        console.error('Errore creazione regola:', error);
        alert('Errore di connessione.');
    }
}

async function eliminaRegola(id) {
    if (!confirm('Eliminare questa regola? Gli slot già generati restano invariati.')) return;

    try {
        await fetch(`/admin/disponibilita/regole/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        caricaRegole();
    } catch (error) {
        console.error('Errore eliminazione regola:', error);
    }
}

// ─── BLOCCHI ECCEZIONALI ───────────────────────────────────────
async function caricaBlocchi() {
    const container = document.getElementById('lista-blocchi');
    try {
        const res = await fetch('/admin/disponibilita/blocchi', { headers: authHeaders() });
        const blocchi = await res.json();

        if (blocchi.length === 0) {
            container.innerHTML = '<p style="color:#aaa; margin-top:1rem">Nessun blocco eccezionale.</p>';
            return;
        }

        container.innerHTML = `
            <table class="admin-table" style="margin-top:1rem">
                <thead>
                    <tr>
                        <th>Dal</th>
                        <th>Al</th>
                        <th>Motivo</th>
                        <th>Azioni</th>
                    </tr>
                </thead>
                <tbody>
                    ${blocchi.map(b => `
                        <tr>
                            <td>${b.data_inizio}</td>
                            <td>${b.data_fine}</td>
                            <td>${escapeHtml(b.motivo) || '—'}</td>
                            <td>
                                <button class="action-btn action-delete" onclick="eliminaBlocco(${b.id})">
                                    🗑 Elimina
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Errore caricamento blocchi:', error);
    }
}

async function creaBloccoEccezionale() {
    const dataInizio = document.getElementById('blocco-data-inizio').value;
    const dataFine = document.getElementById('blocco-data-fine').value;
    const motivo = document.getElementById('blocco-motivo').value.trim();

    if (!dataInizio || !dataFine) {
        alert('Inserisci data di inizio e fine.');
        return;
    }

    try {
        const res = await fetch('/admin/disponibilita/blocchi', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                data_inizio: dataInizio,
                data_fine: dataFine,
                motivo: motivo || null
            })
        });

        if (!res.ok) {
            const errore = await res.json();
            alert(errore.detail || 'Errore durante la creazione del blocco.');
            return;
        }

        const data = await res.json();
        alert(`Blocco creato: ${data.slot_bloccati} slot bloccati.`);
        document.getElementById('blocco-motivo').value = '';
        caricaBlocchi();
        caricaSlots(paginaCorrente.slots);
    } catch (error) {
        console.error('Errore creazione blocco:', error);
        alert('Errore di connessione.');
    }
}

async function eliminaBlocco(id) {
    if (!confirm('Eliminare questo blocco? Gli slot già bloccati restano bloccati.')) return;

    try {
        await fetch(`/admin/disponibilita/blocchi/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        caricaBlocchi();
    } catch (error) {
        console.error('Errore eliminazione blocco:', error);
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
        caricaSlots(paginaCorrente.slots);
    } catch (error) {
        console.error('Errore creazione slot:', error);
    }
}

async function eliminaSlot(id) {
    if (!confirm('Sei sicuro di voler eliminare questo slot?')) return;

    try {
        const res = await fetch(`/admin/slots/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });

        if (!res.ok) {
            const errore = await res.json();
            alert(errore.detail || 'Errore durante l\'eliminazione dello slot.');
            return;
        }

        caricaSlots(paginaCorrente.slots);
    } catch (error) {
        console.error('Errore eliminazione slot:', error);
        alert('Errore di connessione durante l\'eliminazione.');
    }
}

// ─── EXPORT CSV ──────────────────────────────────────────────
async function exportCSV() {
    // il token va nell'header Authorization, non nell'URL:
    // scarichiamo il file via fetch e lo salviamo lato client.
    try {
        const res = await fetch('/admin/export/csv', { headers: authHeaders() });
        if (!res.ok) {
            alert('Errore durante l\'esportazione.');
            return;
        }
        // Il CSV viene ricevuto come blob perché la richiesta deve portare
        // l'header di autenticazione: un link diretto non potrebbe farlo.
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        // Link temporaneo usato solo per avviare il download.
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prenotazioni.csv';
        document.body.appendChild(a);
        a.click();
        a.remove(); // il link non serve più, lo rimuoviamo subito dalla pagina
        // Rilascia la memoria occupata dal blob.
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Errore export CSV:', error);
        alert('Errore di connessione durante l\'esportazione.');
    }
}

// ─── AVVIO ───────────────────────────────────────────────────
// permette di fare login premendo Invio
document.addEventListener('DOMContentLoaded', () => {
    // Nulla da caricare prima del login: qui si abilita solo l'invio del
    // form con Invio.
    document.getElementById('login-password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });
});
