# Le tre liste paginate del pannello admin (prenotazioni, clienti, slot)
# ripetevano ciascuna, identica, la stessa sanificazione di pagina/per_pagina
# e lo stesso calcolo di pagine_totali — questo file le raccoglie in un
# punto solo.

from typing import Any


def pagina_e_offset(pagina: int, per_pagina: int) -> tuple[int, int, int]:
    """
    Sanifica pagina/per_pagina (qualcuno potrebbe mandare pagina=-5 o
    per_pagina=99999) e restituisce (pagina, per_pagina, offset) — l'offset
    è già pronto per .offset()/.limit() sulla query.
    """
    pagina = max(pagina, 1)
    per_pagina = min(max(per_pagina, 1), 100)
    offset = (pagina - 1) * per_pagina
    return pagina, per_pagina, offset


def busta_paginazione(items: list[Any], totale: int, pagina: int, per_pagina: int) -> dict:
    """
    Costruisce l'envelope standard {items, totale, pagina, per_pagina,
    pagine_totali} restituito da ogni endpoint admin con lista paginata.
    Formula per arrotondare per eccesso una divisione intera, senza usare
    numeri decimali: (totale + per_pagina - 1) // per_pagina. L'operatore
    "//" è la divisione intera di Python (scarta la parte decimale).
    Esempio: 25 prenotazioni, 20 per pagina → (25+19)//20 = 44//20 = 2
    pagine (la seconda con solo 5 elementi).
    """
    return {
        "items": items,
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        "pagine_totali": max((totale + per_pagina - 1) // per_pagina, 1)
    }
