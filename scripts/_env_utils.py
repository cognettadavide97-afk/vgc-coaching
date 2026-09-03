"""Aggiornamento del .env locale, condiviso dagli script one-off.

Tutti gli script di questa cartella terminano scrivendo un valore ottenuto
(un token, un hash) nel .env. Il prefisso "_" segnala che il modulo è per
uso interno a scripts/, non parte dell'API del progetto.
"""

import os
import re


def aggiorna_env_locale(env_path: str, nome_variabile: str, nuovo_valore: str) -> bool:
    """Aggiorna o aggiunge una variabile nel file .env indicato.

    Restituisce False senza modificare nulla se il file non esiste.
    """
    if not os.path.exists(env_path):
        print(f"File .env non trovato in {env_path} — aggiornalo a mano.")
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        contenuto = f.read()

    nuovo_contenuto, sostituzioni = re.subn(
        rf"^{re.escape(nome_variabile)}=.*$",
        f"{nome_variabile}={nuovo_valore}",
        contenuto,
        count=1,
        flags=re.MULTILINE
    )

    if sostituzioni == 0:
        # Variabile non ancora presente: viene aggiunta in fondo.
        if not contenuto.endswith("\n"):
            contenuto += "\n"
        nuovo_contenuto = contenuto + f"{nome_variabile}={nuovo_valore}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(nuovo_contenuto)
    print(".env locale aggiornato.")
    return True
