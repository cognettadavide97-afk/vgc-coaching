# Catalogo fisso dei pacchetti di sessioni, ripreso 1:1 dal materiale
# grafico promozionale del coach (Desktop\Grafiche Coaching). Non è
# personalizzabile da chi crea un pacchetto: admin/packages.py sceglie solo la
# "chiave" (intro/team/tour) e uno User a cui assegnarlo, tutti gli altri
# valori vengono presi da qui — così il prezzo/contenuto reale del
# pacchetto non può mai essere alterato da una richiesta HTTP malformata.
CATALOGO_PACCHETTI = {
    "intro": {
        "nome": "Competitive Intro",
        "sessioni_totali": 2,
        "durata_sessione_ore": 2,
        "prezzo_cents": 7000,
        "prezzo_pieno_cents": 8000,
    },
    "team": {
        "nome": "Team Building Session",
        "sessioni_totali": 4,
        "durata_sessione_ore": 2,
        "prezzo_cents": 13000,
        "prezzo_pieno_cents": 16000,
    },
    "tour": {
        "nome": "Tournament Prep",
        "sessioni_totali": 6,
        "durata_sessione_ore": 2,
        "prezzo_cents": 19000,
        "prezzo_pieno_cents": 24000,
    },
}
