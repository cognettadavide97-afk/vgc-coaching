"""Paginazione condivisa dalle liste del pannello di amministrazione."""

from typing import Any


def pagina_e_offset(pagina: int, per_pagina: int) -> tuple[int, int, int]:
    """Normalizza i parametri di paginazione e calcola l'offset.

    I valori arrivano dalla query string e non sono affidabili: il clamp
    impedisce offset negativi e pagine arbitrariamente grandi, che
    costringerebbero il database a leggere l'intera tabella.
    """
    pagina = max(pagina, 1)
    per_pagina = min(max(per_pagina, 1), 100)
    offset = (pagina - 1) * per_pagina
    return pagina, per_pagina, offset


def busta_paginazione(items: list[Any], totale: int, pagina: int, per_pagina: int) -> dict:
    """Costruisce la risposta paginata standard usata da tutte le liste admin."""
    return {
        "items": items,
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        # Divisione intera arrotondata per eccesso; almeno 1 pagina anche
        # quando non ci sono risultati, così il frontend non mostra "0 di 0".
        "pagine_totali": max((totale + per_pagina - 1) // per_pagina, 1)
    }
