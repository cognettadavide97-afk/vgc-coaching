// Sistema di traduzione condiviso tra tutte le pagine del sito pubblico
// (frontend/index.html, frontend/about.html) — vanilla JavaScript, nessuna
// libreria di i18n: coerente con lo stile "niente build step" del resto
// del progetto (vedi README). Il pannello admin (frontend/admin.html) non
// lo usa: resta solo in italiano, essendo per uso esclusivo del coach.
//
// Come funziona, in breve: ogni testo statico nell'HTML ha un attributo
// data-i18n="chiave" (es. <h2 data-i18n="step1_title">...</h2>) — questo
// file legge quell'attributo, cerca "chiave" nel dizionario TRANSLATIONS
// nella lingua corrente, e sostituisce il testo dell'elemento. I testi
// generati dinamicamente da app.js (alert, riepilogo prenotazione...)
// chiamano direttamente la funzione t("chiave") invece di leggere l'HTML.

const TRANSLATIONS = {
    en: {
        // Navigazione condivisa
        nav_book: 'Book a Session',
        nav_about: 'Meet the Coach',

        // Login Discord (frontend/js/app.js costruisce questo HTML a runtime)
        discord_login_btn: 'Log in with Discord (optional)',
        welcome_back: 'Welcome back,',
        your_bookings: 'Your bookings',
        log_out: 'Log out',
        discord_login_failed: 'Discord login failed. Please try again, or book as a guest without logging in.',
        cancel_booking: 'Cancel',
        confirm_cancel_booking: 'Cancel this booking? The time slot will be freed up and this cannot be undone.',

        // Consulenza gratuita
        consulenza_link: '🎁 Not sure? Ask for a free consultation!',
        label_name: 'Name *',
        label_email_required: 'Email *',
        label_discord_tag: 'Discord Tag',
        label_message_optional: 'Message (optional)',
        consulenza_message_placeholder: "E.g.: I'd like to know where to start...",
        consulenza_submit: 'Request the free call',

        // Barra degli step
        step_choose_slot: 'Choose slot',
        step_your_details: 'Your details',
        step_confirm: 'Confirm',

        // Step 1
        step1_title: 'Choose date and time',
        step1_subtitle: 'Select an available slot for your session',
        loading_slots: 'Loading available slots...',
        no_slots: 'No slots available for this duration. Try a different duration.',
        error_loading_slots: 'Error loading slots.',
        session_type: 'Session type',
        session_duration: 'Session duration',
        duration_1h: '1 hour — €20',
        duration_2h: '2 hours — €40',
        continue_btn: 'Continue →',

        // Servizi (stessa terminologia del materiale promozionale del coach)
        service_vod_review: 'VOD Review',
        service_team_building: 'Team Building',
        service_bo3_sparring: 'Bo3 Sparring',
        service_tournament_prep: 'Tournament Prep',

        // Step 2
        step2_title: 'Your details',
        step2_subtitle: 'Enter your information to complete the booking',
        label_full_name: 'Full name *',
        label_category: 'Category',
        label_notes: 'Notes (current team, goals...)',
        notes_placeholder: "E.g.: I use a Trick Room team with Indeedee-F, I struggle handling fast turns...",
        label_vod_link: 'VOD link (optional)',
        label_replay_code: 'Showdown replay code (optional)',
        back_btn: '← Back',

        // Step 3
        step3_title: 'Booking summary',
        step3_subtitle: 'Review your details before confirming',
        summary_date: 'Date and time',
        summary_service: 'Service',
        summary_duration: 'Duration',
        summary_name: 'Name',
        summary_email: 'Email',
        summary_total: 'Total',
        confirm_booking: '✓ Confirm booking',
        sending: 'Sending...',
        free_package: 'Free (package)',
        use_package_session: 'Use a session from the "{name}" package ({used}/{total} remaining) — Free',
        name_email_required: 'Name and email are required.',
        generic_error: 'An error occurred. Please try again.',
        at_time_connector: 'at',
        unit_hour: 'hour',
        unit_hours: 'hours',

        // Step 4 (successo)
        success_title: 'Booking confirmed!',
        success_text: "We've sent you a confirmation email with all the session details.",
        book_another: 'Book another session',

        // Pacchetti
        packages_title: 'Packages',
        packages_subtitle: 'More sessions, discounted price — select one below or message me on Discord',
        pkg_intro_details: '2 sessions, 2 hours each',
        pkg_team_details: '4 sessions, 2 hours each',
        pkg_tour_details: '6 sessions, 2 hours each',
        pkg_intro_li1: 'Game fundamentals',
        pkg_intro_li2: 'Replay analysis: mistakes and reads',
        pkg_intro_li3: 'Dynamic ladder sessions',
        pkg_team_li1: 'From concept to a finished team',
        pkg_team_li2: 'Testing sessions',
        pkg_team_li3: 'Final review and optimisation',
        pkg_tour_li1: 'Current meta analysis and team study',
        pkg_tour_li2: 'Flowcharts and working documents',
        pkg_tour_li3: 'Final check and review before the event',
        pkg_footer: 'Every session includes a written recap — on Discord, ENG/ITA',
        pkg_select_btn: 'Select this package',
        pkg_selected_label: 'Selected package:',
        pkg_request_submit: 'Request this package',
        request_sent: "Request sent! We'll contact you shortly.",

        // About the coach
        about_tagline: 'VGC competitor & coach',
        about_bio: "I've been competing in the Pokémon VGC scene since 2017, with results ranging from regional Top 8s to a national title. Today I split my time between tournament play and coaching — helping players of every level build better teams, sharpen their in-game decisions, and prepare with a clear plan for their next event.",
        about_results_tag: 'RESULTS',
        result_finalist: 'Finalist',
        result_champion: 'Champion',
        result_3rd: '3rd',
        reviews_title: 'Client Reviews',
        reviews_subtitle: 'Reviews from past students will appear here soon.',
        reviews_placeholder: 'No reviews to show yet.',

        status_confirmed: 'Confirmed',
        status_cancelled: 'Cancelled',
        status_no_show: 'No-show'
    },
    it: {
        nav_book: 'Prenota una sessione',
        nav_about: 'Conosci il coach',

        discord_login_btn: 'Accedi con Discord (opzionale)',
        welcome_back: 'Bentornato,',
        your_bookings: 'Le tue prenotazioni',
        log_out: 'Esci',
        discord_login_failed: 'Accesso con Discord non riuscito. Riprova, oppure prenota come ospite senza login.',
        cancel_booking: 'Cancella',
        confirm_cancel_booking: 'Cancellare questa prenotazione? Lo slot orario tornerà libero e l\'azione non è reversibile.',

        consulenza_link: '🎁 Indeciso? Chiedi una consulenza gratuita!',
        label_name: 'Nome *',
        label_email_required: 'Email *',
        label_discord_tag: 'Discord Tag',
        label_message_optional: 'Messaggio (opzionale)',
        consulenza_message_placeholder: 'Es: vorrei capire da dove iniziare...',
        consulenza_submit: 'Richiedi la call gratuita',

        step_choose_slot: 'Scegli slot',
        step_your_details: 'I tuoi dati',
        step_confirm: 'Conferma',

        step1_title: 'Scegli data e orario',
        step1_subtitle: 'Seleziona uno slot disponibile per la tua sessione',
        loading_slots: 'Caricamento slot disponibili...',
        no_slots: 'Nessuno slot disponibile per questa durata. Prova un\'altra durata.',
        error_loading_slots: 'Errore nel caricamento degli slot.',
        session_type: 'Tipo di sessione',
        session_duration: 'Durata sessione',
        duration_1h: '1 ora — €20',
        duration_2h: '2 ore — €40',
        continue_btn: 'Continua →',

        service_vod_review: 'Analisi Replay',
        service_team_building: 'Teambuilding',
        service_bo3_sparring: 'Bo3 Sparring',
        service_tournament_prep: 'Preparazione Torneo',

        step2_title: 'I tuoi dati',
        step2_subtitle: 'Inserisci le tue informazioni per completare la prenotazione',
        label_full_name: 'Nome completo *',
        label_category: 'Categoria',
        label_notes: 'Note (team attuale, obiettivi...)',
        notes_placeholder: 'Es: uso un team Trick Room con Indeedee-F, ho problemi con la gestione dei turni veloci...',
        label_vod_link: 'Link VOD (opzionale)',
        label_replay_code: 'Codice replay Showdown (opzionale)',
        back_btn: '← Indietro',

        step3_title: 'Riepilogo prenotazione',
        step3_subtitle: 'Controlla i dati prima di confermare',
        summary_date: 'Data e orario',
        summary_service: 'Servizio',
        summary_duration: 'Durata',
        summary_name: 'Nome',
        summary_email: 'Email',
        summary_total: 'Totale',
        confirm_booking: '✓ Conferma prenotazione',
        sending: 'Invio in corso...',
        free_package: 'Gratis (pacchetto)',
        use_package_session: 'Usa una sessione dal pacchetto "{name}" ({used}/{total} rimanenti) — Gratis',
        name_email_required: 'Nome e email sono obbligatori.',
        generic_error: 'Si è verificato un errore. Riprova.',
        at_time_connector: 'alle',
        unit_hour: 'ora',
        unit_hours: 'ore',

        success_title: 'Prenotazione confermata!',
        success_text: 'Ti abbiamo inviato una email di conferma con tutti i dettagli della sessione.',
        book_another: "Prenota un'altra sessione",

        packages_title: 'Pacchetti',
        packages_subtitle: 'Più sessioni, prezzo scontato — selezionane uno qui sotto oppure scrivimi su Discord',
        pkg_intro_details: '2 sessioni, 2 ore ciascuna',
        pkg_team_details: '4 sessioni, 2 ore ciascuna',
        pkg_tour_details: '6 sessioni, 2 ore ciascuna',
        pkg_intro_li1: 'Fondamentali di gioco',
        pkg_intro_li2: 'Analisi replay: errori e letture',
        pkg_intro_li3: 'Sessioni dinamiche in ladder',
        pkg_team_li1: 'Dal concept al team finito',
        pkg_team_li2: 'Sessioni di test',
        pkg_team_li3: 'Revisione e ottimizzazione finale',
        pkg_tour_li1: 'Analisi meta attuale e studio team',
        pkg_tour_li2: 'Flowchart e documenti di lavoro',
        pkg_tour_li3: "Check e revisione finale prima dell'evento",
        pkg_footer: 'Ogni sessione include un recap scritto — su Discord, ENG/ITA',
        pkg_select_btn: 'Seleziona questo pacchetto',
        pkg_selected_label: 'Pacchetto selezionato:',
        pkg_request_submit: 'Richiedi questo pacchetto',
        request_sent: 'Richiesta inviata! Ti contatteremo a breve.',

        about_tagline: 'Giocatore e coach VGC',
        about_bio: 'Gioco a livello competitivo nel circuito VGC di Pokémon dal 2017, con risultati che vanno da Top 8 nei regionali a un titolo nazionale. Oggi divido il mio tempo tra i tornei e il coaching — aiuto giocatori di ogni livello a costruire team più solidi, affinare le scelte in game e prepararsi con un piano chiaro per il prossimo evento.',
        about_results_tag: 'RISULTATI',
        result_finalist: 'Finalista',
        result_champion: 'Campione',
        result_3rd: '3°',
        reviews_title: 'Recensioni dei clienti',
        reviews_subtitle: 'Le recensioni degli studenti passati appariranno presto qui.',
        reviews_placeholder: 'Nessuna recensione da mostrare ancora.',

        status_confirmed: 'Confermato',
        status_cancelled: 'Cancellato',
        status_no_show: 'No-show'
    }
};

// Lingua corrente: quella salvata da una visita precedente (localStorage,
// stesso meccanismo usato per student_token in app.js), altrimenti quella
// del browser se è italiano, altrimenti inglese di default — un
// visitatore italiano vede subito il sito nella sua lingua senza dover
// toccare l'interruttore.
let currentLang = localStorage.getItem('lang') || (navigator.language.startsWith('it') ? 'it' : 'en');

// t("chiave") restituisce il testo tradotto nella lingua corrente. Se la
// chiave non esistesse nel dizionario (errore di battitura, dimenticanza),
// restituisce la chiave stessa invece di un testo vuoto: un bug del
// genere resta visibile e facile da notare, invece di sparire in
// silenzio.
function t(chiave) {
    return (TRANSLATIONS[currentLang] && TRANSLATIONS[currentLang][chiave]) || chiave;
}

// Sostituisce {segnaposto} dentro una stringa tradotta con valori veri —
// serve per frasi come "Usa una sessione dal pacchetto {name}..." dove
// una parte del testo è dinamica (vedi use_package_session sopra).
// L'equivalente di "Usa una sessione dal pacchetto {name}...".format(name=...)
// in Python.
function tf(chiave, valori) {
    let testo = t(chiave);
    for (const nomeSegnaposto in valori) {
        testo = testo.replace(`{${nomeSegnaposto}}`, valori[nomeSegnaposto]);
    }
    return testo;
}

// Applica la traduzione a ogni elemento con data-i18n nella pagina
// corrente. Va richiamata sia all'avvio sia ogni volta che la lingua
// cambia (vedi setLang più sotto).
function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    // data-i18n-placeholder: stesso meccanismo ma per il placeholder di
    // input/textarea, che non è "testo dentro l'elemento" (textContent
    // non lo tocca).
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.documentElement.lang = currentLang;

    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.lang === currentLang);
    });
}

function setLang(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    applyTranslations();
    // Alcuni testi (slot già caricati, riepilogo prenotazione già
    // compilato...) non hanno un elemento data-i18n da riapplicare: sono
    // stati scritti da app.js in un momento precedente. L'evento
    // "langchange" avvisa app.js (se presente in pagina) che la lingua è
    // cambiata, così può ridisegnare quei pezzi con il testo giusto.
    document.dispatchEvent(new CustomEvent('langchange'));
}

document.addEventListener('DOMContentLoaded', applyTranslations);
