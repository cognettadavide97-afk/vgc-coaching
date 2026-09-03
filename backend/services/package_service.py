"""Catalogo dei pacchetti di sessioni.

Valori fissi e non modificabili da una richiesta: chi assegna un pacchetto
sceglie soltanto la chiave, tutto il resto viene letto da qui.
"""

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
