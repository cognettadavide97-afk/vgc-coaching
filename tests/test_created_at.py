# Le date di creazione (created_at) devono essere UTC come ogni altro orario
# del database, e deciderle Python, non il database.
#
# Con default=func.now() la data la scriveva MySQL con NOW(), che usa il fuso
# del server: su Railway è UTC (misurato il 2026-11-11), ma sul MySQL di
# sviluppo è l'ora italiana, e ogni created_at risultava avanti di 1-2 ore.
# Bastava un database configurato diversamente, per esempio un ripristino del
# backup, per spostare in silenzio tutte le date nuove.
#
# Perché il test guarda il default delle colonne invece di inserire righe:
# SQLite, il database dei test, è già in UTC, quindi una riga inserita qui
# avrebbe la data giusta anche col codice vecchio. La prova sul MySQL vero è
# nel commit che ha introdotto questo file.

from datetime import datetime, timedelta, timezone

import backend.models  # noqa: F401  registra tutte le tabelle su Base
from backend.database import Base


def test_ogni_created_at_e_calcolato_da_python_in_utc():
    colonne = [t.c.created_at for t in Base.metadata.sorted_tables if "created_at" in t.c]
    assert colonne

    for colonna in colonne:
        tabella = colonna.table.name
        # Un'espressione SQL come func.now() la valuterebbe il database.
        assert colonna.default is not None and colonna.default.is_callable, tabella

        valore = colonna.default.arg(None)
        adesso_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        assert valore.tzinfo is None, tabella
        assert abs(valore - adesso_utc) < timedelta(seconds=5), tabella
