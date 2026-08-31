# Copre backend/services/pagination_service.py: funzioni pure, senza
# dipendenze esterne (nessun db/client necessario) — usate da tutte le
# liste paginate del pannello admin (prenotazioni, clienti, slot). La
# copertura indiretta (passando dagli endpoint che le usano) non esercita
# mai i valori limite (pagina negativa, per_pagina fuori range), da cui
# questi test diretti.

from backend.services.pagination_service import pagina_e_offset, busta_paginazione


def test_pagina_negativa_viene_riportata_a_1():
    pagina, per_pagina, offset = pagina_e_offset(-5, 20)
    assert pagina == 1
    assert per_pagina == 20
    assert offset == 0


def test_pagina_zero_viene_riportata_a_1():
    pagina, per_pagina, offset = pagina_e_offset(0, 20)
    assert pagina == 1
    assert offset == 0


def test_per_pagina_troppo_grande_viene_limitata_a_100():
    pagina, per_pagina, offset = pagina_e_offset(1, 99999)
    assert per_pagina == 100
    assert offset == 0


def test_per_pagina_zero_o_negativa_viene_riportata_a_1():
    _, per_pagina, _ = pagina_e_offset(1, 0)
    assert per_pagina == 1

    _, per_pagina_neg, _ = pagina_e_offset(1, -10)
    assert per_pagina_neg == 1


def test_offset_calcolato_correttamente_per_pagine_successive():
    pagina, per_pagina, offset = pagina_e_offset(3, 20)
    assert pagina == 3
    assert per_pagina == 20
    assert offset == 40  # salta le prime 2 pagine da 20 elementi


def test_busta_paginazione_arrotonda_per_eccesso_le_pagine_totali():
    busta = busta_paginazione(items=[1, 2, 3], totale=25, pagina=1, per_pagina=20)
    assert busta["pagine_totali"] == 2  # 25 elementi, 20 per pagina → 2 pagine


def test_busta_paginazione_con_zero_elementi_ha_almeno_una_pagina():
    busta = busta_paginazione(items=[], totale=0, pagina=1, per_pagina=20)
    assert busta["pagine_totali"] == 1  # mai 0 pagine, anche a lista vuota
