// Questo è il "cervello" del pannello admin (frontend/admin.html) — il file
// più grande del frontend, perché il pannello fa molte cose diverse. Vedi
// i commenti in frontend/js/app.js per la spiegazione dei concetti
// JavaScript di base (fetch, async/await, template literal, DOM,
// addEventListener...) — qui ci concentriamo sulle parti nuove.

// ─── TOKEN ───────────────────────────────────────────────────
// Il token JWT viene salvato in memoria — dura fino
// a quando la pagina è aperta
let token = null;
// Nota la differenza rispetto ad app.js, che salva il token studente in
// localStorage (persistente tra visite): qui invece "token" è solo una
// variabile JavaScript normale, che si azzera appena ricarichi la pagina
// o la chiudi — il coach deve rifare il login ogni volta che riapre il
// pannello. È una scelta di sicurezza deliberata: un token admin dà
// accesso a TUTTI i dati dei clienti, ha senso che sia meno "comodo" da
// mantenere rispetto a un token studente che dà accesso solo al proprio
// storico.

// ─── PAGINAZIONE (helper condiviso da prenotazioni/clienti/slot) ─
// tiene traccia della pagina corrente di ciascuna lista, cosi le azioni
// (nota, cambio stato, elimina...) possono ricaricare la stessa pagina
// invece di riportare sempre l'admin a pagina 1
const paginaCorrente = { prenotazioni: 1, clienti: 1, slots: 1 };

function renderPaginazione(dati, nomeFunzione) {
    // Se c'è una sola pagina di risultati, i controlli "Precedente/Successiva"
    // non servono a nulla — restituire una stringa vuota fa sì che
    // semplicemente non compaia nulla nella pagina.
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
    // ${nomeFunzione}(...) dentro la stringa è interessante: nomeFunzione è
    // un TESTO (es. "caricaPrenotazioni") passato come parametro, e viene
    // incollato dentro l'HTML generato — a runtime, quel testo diventa una
    // vera chiamata di funzione nell'attributo onclick. Questo è ciò che
    // rende renderPaginazione riusabile per tre liste diverse (prenotazioni,
    // clienti, slot) con un'unica funzione, invece di scriverne tre copie
    // quasi identiche.
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
        // OAuth2PasswordRequestForm richiede form-urlencoded
        // non JSON — è uno standard specifico di OAuth2
        // URLSearchParams costruisce dati nel formato "chiave=valore&chiave2=valore2"
        // (lo stesso formato che vedi nella query string di un URL) — qui
        // lo usiamo però come CORPO della richiesta, non come parte
        // dell'indirizzo, perché è il formato che l'endpoint
        // /admin/login (backend/routers/admin.py) si aspetta.
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
    // Questa funzione viene richiamata praticamente in ogni fetch() di
    // questo file — invece di ripetere ovunque "headers: {'Authorization':
    // ...}", la costruiamo qui una volta sola e la riusiamo. Se domani il
    // formato degli header cambiasse, basterebbe modificare questa unica
    // funzione.
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
    // Ogni volta che l'admin passa a una sezione, ricarichiamo i suoi dati
    // freschi dal server — così vede sempre lo stato più aggiornato,
    // invece di dati potenzialmente vecchi rimasti in pagina da prima.
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
// L'ordine di questo array non è casuale: la posizione 0 è Lunedì, la
// posizione 6 Domenica — deve combaciare esattamente con la numerazione
// usata nel backend (0=lunedì...6=domenica, vedi backend/models/availability_rule.py),
// così GIORNI_SETTIMANA[r.giorno_settimana] (che vedrai più sotto) traduce
// correttamente il numero che arriva dal server nel nome del giorno.

const SERVICE_LABELS = {
    vod_review: 'VOD Review',
    team_building: 'Team Building',
    bo3_sparring: 'Bo3 Sparring',
    tournament_prep: 'Tournament Prep'
};

// Duplicato minimale del catalogo fisso in
// backend/services/package_service.py — solo i campi che servono per
// mostrare le opzioni nel modale di assegnazione (backend resta l'unica
// fonte autoritativa per prezzi/sessioni reali, vedi POST /admin/pacchetti).
const CATALOGO_PACCHETTI = {
    intro: { nome: 'Competitive Intro', sessioni: 2, prezzo: 70 },
    team: { nome: 'Team Building Session', sessioni: 4, prezzo: 130 },
    tour: { nome: 'Tournament Prep', sessioni: 6, prezzo: 190 }
};

// sfugge caratteri HTML per evitare che testo inserito dallo studente
// (link VOD, codice replay, ecc.) venga interpretato come markup nel pannello
function escapeHtml(str) {
    // Identica a escapeHtmlPublic in frontend/js/app.js — vedi lì la
    // spiegazione completa del perché serve (protezione da XSS). Qui è
    // particolarmente importante perché il pannello admin mostra TANTI
    // dati inseriti da chi prenota (nome, note, link, codici replay...),
    // che un visitatore malintenzionato potrebbe in teoria provare a
    // manipolare.
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// mostra il link VOD come anchor cliccabile solo se è davvero un URL http/https,
// altrimenti come testo semplice (sempre sfuggito)
function renderVodLink(link) {
    const safe = escapeHtml(link);
    // Questa è una ESPRESSIONE REGOLARE (regex): un modo compatto per
    // descrivere "una forma di testo" da cercare o verificare. Non esiste
    // nulla di identico built-in in Python base (serve il modulo "re"),
    // ma il concetto è lo stesso. Leggendola pezzo per pezzo:
    // /.../ delimita la regex, "^" vuol dire "inizio della stringa",
    // "https?" vuol dire "http, con una 's' opzionale" (il "?" rende
    // opzionale il carattere prima), ":\/\/" è "://" (con gli slash
    // "protetti" da backslash perché altrimenti chiuderebbero la regex),
    // "i" alla fine vuol dire "case insensitive" (accetta anche "HTTP").
    // .test(link) restituisce true/false: "questa stringa rispetta questo
    // schema?". In pratica: "il link comincia per http:// o https://?" —
    // un controllo di sicurezza minimo prima di trasformarlo in un vero
    // link cliccabile (evita che qualcuno inserisca "javascript:..." come
    // link, che nel browser eseguirebbe codice invece di aprire una pagina).
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
    // Avviata subito, ma await SOLO alla fine (sotto): /admin/dashboard e
    // /admin/analytics sono due richieste indipendenti (nessuna delle due
    // ha bisogno del risultato dell'altra) — partire in parallelo invece
    // che una dopo l'altra dimezza il tempo di attesa a ogni apertura del
    // pannello. caricaAnalytics() gestisce già i propri errori al suo
    // interno (try/catch), quindi lasciarla "in volo" qui non rischia di
    // generare un errore non gestito.
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
    // Questa funzione disegna un "grafico a barre" senza NESSUNA libreria
    // di grafici: solo <div> con una larghezza calcolata in percentuale
    // via CSS. È un pattern sorprendentemente comune ed efficace per
    // grafici semplici: niente da scaricare, niente da imparare, solo
    // matematica di base e HTML/CSS.
    if (!container) return;
    // .every(...) restituisce true solo se TUTTI gli elementi dell'array
    // soddisfano la condizione — qui: "sono tutti i valori pari a zero?"
    // (cioè "non c'è ancora nessun dato interessante da mostrare").
    if (dati.length === 0 || dati.every(d => d[chiaveValore] === 0)) {
        container.innerHTML = '<p style="color:#aaa">Nessun dato ancora disponibile.</p>';
        return;
    }
    // Math.max(...dati.map(...), 1) trova il valore più alto tra tutti i
    // dati (ci serve per calcolare le percentuali delle barre: la barra
    // più alta deve arrivare al 100%). "..." qui è lo SPREAD OPERATOR:
    // trasforma un array in tanti argomenti separati — Math.max normalmente
    // vuole i numeri uno per uno (Math.max(3, 7, 2)), non un array intero,
    // quindi "..." fa da "ponte" tra i due mondi. Il ", 1" finale garantisce
    // che il massimo non sia mai 0 (eviterebbe una divisione per zero nel
    // calcolo delle percentuali sotto).
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
    // "formattatore" è un parametro FACOLTATIVO che, se passato, è esso
    // stesso una funzione (es. v => `€${v.toFixed(2)}` per l'incasso) —
    // JavaScript permette di passare funzioni come normali valori, esattamente
    // come in Python puoi passare una funzione come argomento di un'altra.
    // "formattatore ? formattatore(valore) : valore" vuol dire "se è stato
    // passato un formattatore, usalo per trasformare il valore prima di
    // mostrarlo, altrimenti mostra il valore grezzo".
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
            // .map(s => ({ ...s, servizio: ... })) crea un NUOVO array dove
            // ogni elemento è una copia dell'originale (grazie a "...s", lo
            // spread operator applicato qui a un OGGETTO invece che a un
            // array: copia tutti i suoi campi) con il campo "servizio"
            // sovrascritto dalla sua etichetta leggibile — serve perché
            // renderBarChart si aspetta di trovare il testo da mostrare
            // già dentro il campo "servizio", non il codice tecnico grezzo
            // (es. "vod_review") che arriva dal server.
            analytics.servizi_piu_richiesti.map(s => ({ ...s, servizio: SERVICE_LABELS[s.servizio] || s.servizio })),
            'servizio', 'conteggio'
        );
    } catch (error) {
        console.error('Errore analytics:', error);
    }
}

// ─── PRENOTAZIONI ────────────────────────────────────────────
async function caricaPrenotazioni(pagina = 1) {
    // "pagina = 1" nella firma della funzione è un PARAMETRO DI DEFAULT:
    // se chiami caricaPrenotazioni() senza argomenti, "pagina" vale 1
    // automaticamente — lo stesso identico concetto dei default nei
    // parametri delle funzioni Python (def f(pagina=1)).
    paginaCorrente.prenotazioni = pagina;
    const stato = document.getElementById('filtro-stato').value;
    const params = new URLSearchParams({ pagina: pagina, per_pagina: 20 });
    if (stato) params.set('stato', stato);

    try {
        // `/admin/prenotazioni?${params}` — quando un oggetto
        // URLSearchParams viene inserito dentro una template literal,
        // JavaScript lo converte automaticamente nella sua forma testuale
        // "pagina=1&per_pagina=20&stato=confirmed" — costruire la query
        // string così, invece che concatenando stringhe a mano, evita
        // errori con caratteri speciali che andrebbero "escapati".
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
                                        onclick="aggiornaStato(${p.id}, 'cancelled')">
                                        ✗ Cancella
                                    </button>
                                    <button class="action-btn action-no-show"
                                        onclick="aggiornaStato(${p.id}, 'no_show')">
                                        🚫 No-show
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
            ${renderPaginazione(dati, 'caricaPrenotazioni')}
        `;
        // .replace(/'/g, "\\'") qui è un altro uso di espressioni regolari:
        // /'/g significa "trova OGNI apice singolo (') nella stringa" (il
        // flag "g" = "global" vuol dire "non fermarti al primo trovato,
        // sostituiscili tutti"), e li sostituisce con \' (un apice
        // "protetto"). Serve perché stiamo per inserire questo testo
        // dentro un attributo onclick="...('...')" che usa apici singoli:
        // senza proteggerli, un apice dentro la nota chiuderebbe
        // prematuramente la stringa e romperebbe l'HTML generato.
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
        caricaPrenotazioni(paginaCorrente.prenotazioni);
    } catch (error) {
        console.error('Errore aggiornamento stato:', error);
    }
}

async function modificaNota(id, notaAttuale) {
    // prompt(messaggio, valoreIniziale) apre una piccola finestra di
    // dialogo nativa del browser con un campo di testo — un modo rapido
    // (anche se poco elegante graficamente) di chiedere un input veloce
    // senza costruire un form dedicato. Restituisce null se l'utente
    // annulla, altrimenti il testo inserito.
    const nuovaNota = prompt('Nota interna (non visibile al cliente):', notaAttuale);
    if (nuovaNota === null) return;

    try {
        // encodeURIComponent(...) "protegge" il testo per poterlo inserire
        // in un URL: trasforma spazi, accenti e caratteri speciali nella
        // loro forma sicura (es. lo spazio diventa %20) — necessario
        // perché "note" qui viaggia come parametro nell'URL, non nel
        // corpo della richiesta.
        await fetch(`/admin/prenotazioni/${id}/note?note=${encodeURIComponent(nuovaNota)}`, {
            method: 'PATCH',
            headers: authHeaders()
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
                                    onclick="apriNoteCliente(${c.id}, '${escapeHtml(c.nome).replace(/'/g, "\\'")}')">
                                    📋 Note (${c.note_totali})
                                </button>
                                <button class="action-btn action-note"
                                    onclick="apriAssegnaPacchetto(${c.id}, '${escapeHtml(c.nome).replace(/'/g, "\\'")}')">
                                    🎁 Pacchetto
                                </button>
                                <button class="action-btn action-delete"
                                    onclick="eliminaCliente(${c.id}, '${escapeHtml(c.nome).replace(/'/g, "\\'")}')">
                                    🗑️ Elimina
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${renderPaginazione(dati, 'caricaClienti')}
        `;
    } catch (error) {
        console.error('Errore clienti:', error);
    }
}

// ─── CANCELLAZIONE CLIENTE (diritto all'oblio, Art. 17 GDPR) ──
async function eliminaCliente(userId, nomeCliente) {
    // Doppia conferma testuale, non solo un confirm() generico: questa
    // azione cancella per sempre prenotazioni, note e recensioni del
    // cliente, non solo il suo profilo — meglio essere espliciti su cosa
    // sta per sparire prima di procedere (vedi eliminaSlot più sotto per
    // lo stesso pattern conferma+fetch DELETE, usato qui su un'azione
    // ancora più distruttiva).
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
    // A differenza degli altri "pannelli" di questa pagina (che esistono
    // già nell'HTML e vengono solo riempiti), questo modale viene creato
    // DA ZERO in JavaScript la prima volta che serve, con
    // document.createElement('div') — e riusato (non ricreato) alle
    // aperture successive, grazie al controllo "if (!overlay)".
    let overlay = document.getElementById('note-modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'note-modal-overlay';
        overlay.className = 'modal-overlay';
        // appendChild aggiunge davvero l'elemento appena creato dentro la
        // pagina (fino a questo momento esisteva solo "in memoria", non
        // era visibile) — di solito lo si aggiunge in fondo a <body>.
        document.body.appendChild(overlay);
    }

    overlay.innerHTML = `
        <div class="modal-card">
            <h3>📋 Note tecniche — ${nomeCliente}</h3>
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
        // n.created_at arriva dal server come testo tipo
        // "2026-08-12T18:00:00" — invece di ricostruirlo con new Date()
        // (che qui introdurrebbe di nuovo il problema "in che fuso lo
        // interpreto?"), lo trattiamo come semplice TESTO: .replace('T', ' ')
        // sostituisce la "T" di separazione con uno spazio, .slice(0, 16)
        // prende solo i primi 16 caratteri ("2026-08-12 18:00"), tagliando
        // via i secondi. Un modo volutamente "grezzo" ma senza ambiguità.
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
            <h3>🎁 Assegna pacchetto — ${nomeCliente}</h3>
            <p style="font-size: 0.85rem; color: #888;">
                Assegna SOLO dopo aver ricevuto il pagamento (concordato privatamente). Sessioni, durata e prezzo sono fissi dal catalogo, non modificabili qui.
            </p>
            ${Object.entries(CATALOGO_PACCHETTI).map(([chiave, p]) => `
                <button class="action-btn action-note" style="width:100%; margin-bottom:0.5rem; text-align:left;"
                    onclick="assegnaPacchetto(${userId}, '${chiave}', '${nomeCliente.replace(/'/g, "\\'")}')">
                    ${p.nome} — ${p.sessioni} sessioni — €${p.prezzo}
                </button>
            `).join('')}
            <div class="modal-actions">
                <button class="btn-secondary" onclick="chiudiAssegnaPacchetto()">Chiudi</button>
            </div>
        </div>
    `;
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
        // I tre operatori ternari annidati qui sopra (condizione ? A : condizione2 ? B : C)
        // sono l'equivalente di una catena if/elif/elif/else in Python:
        // "se disponibile mostra Libero, altrimenti se bloccato dal
        // calendario mostra quello, altrimenti se bloccato da admin mostra
        // quello, altrimenti (nessuno dei precedenti) deve essere
        // Prenotato".
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
        // r.ora_inizio arriva dal backend come testo tipo "18:00:00"
        // (formato Time di Pydantic/SQLAlchemy) — .slice(0, 5) prende solo
        // i primi 5 caratteri ("18:00"), tagliando via i secondi che qui
        // non interessano mostrare.
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
    // confirm(messaggio) apre una finestra di conferma nativa del browser
    // (Ok/Annulla) e restituisce true/false in base alla scelta — usata
    // qui per chiedere conferma prima di un'azione distruttiva.
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
        // Un "Blob" (Binary Large OBject) rappresenta dati grezzi (qui, il
        // contenuto del file CSV) che il browser sa maneggiare come se
        // fosse un file vero, anche se non è mai stato scaricato su disco.
        // res.blob() lo estrae dalla risposta HTTP, allo stesso modo in
        // cui res.json() estrae dati JSON.
        const blob = await res.blob();
        // createObjectURL crea un indirizzo temporaneo, valido solo in
        // questa pagina, che punta a quel Blob in memoria — un modo per
        // poterlo "linkare" con un normale tag <a>.
        const url = window.URL.createObjectURL(blob);
        // Creiamo un link <a> "invisibile" (mai mostrato nella pagina) solo
        // per sfruttare il suo comportamento nativo di download: impostando
        // a.download a un nome file, cliccarlo (anche via codice, con
        // a.click(), senza che l'utente lo clicchi davvero) fa partire il
        // download invece di navigare verso quell'indirizzo.
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prenotazioni.csv';
        document.body.appendChild(a);
        a.click();
        a.remove(); // il link non serve più, lo rimuoviamo subito dalla pagina
        // revokeObjectURL libera la memoria occupata dall'indirizzo
        // temporaneo creato sopra — buona pratica per non "sprecare"
        // risorse del browser una volta che il download è partito.
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Errore export CSV:', error);
        alert('Errore di connessione durante l\'esportazione.');
    }
}

// ─── AVVIO ───────────────────────────────────────────────────
// permette di fare login premendo Invio
document.addEventListener('DOMContentLoaded', () => {
    // A differenza di app.js (che ha diverso "avvio", caricando subito gli
    // slot), qui non c'è nulla da caricare finché l'admin non fa login —
    // l'unica cosa che serve subito è questo piccolo comfort: permettere
    // di premere Invio nel campo password invece di dover per forza
    // cliccare il bottone "Accedi".
    document.getElementById('login-password').addEventListener('keypress', (e) => {
        // "e" qui è l'oggetto evento passato automaticamente da
        // addEventListener alla funzione che gli assegni (a differenza di
        // "event" usato altrove in questo progetto, che è la variabile
        // globale implicita — sono due modi equivalenti di ottenere la
        // stessa informazione; usare il parametro esplicito "e" come qui è
        // considerato lo stile più moderno e corretto). e.key dice quale
        // tasto è stato premuto — controlliamo che sia "Enter" prima di
        // chiamare login().
        if (e.key === 'Enter') login();
    });
});
