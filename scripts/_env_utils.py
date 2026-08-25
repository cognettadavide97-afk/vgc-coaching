# Helper condiviso dagli script "una tantum" del progetto
# (reauth_gmail.py, reauth_drive.py, hash_admin_password.py): tutti e tre
# fanno la stessa cosa alla fine — ottengono un nuovo valore (un token, un
# hash) e devono scriverlo nel file .env locale, sostituendo la riga
# esistente se c'è già, o aggiungendola in fondo se è la prima volta.
# Prima di questo file la stessa logica (leggi, regex, sostituisci o
# aggiungi, scrivi) era ricopiata a mano in tutti e tre gli script.
#
# Il prefisso "_" nel nome del file segue la stessa convenzione di
# _decodifica in backend/services/auth_service.py: pensato per uso interno
# alla cartella scripts/, non un modulo pubblico del progetto.

import os
import re


def aggiorna_env_locale(env_path: str, nome_variabile: str, nuovo_valore: str) -> bool:
    """
    Sostituisce la riga "NOME_VARIABILE=..." in env_path col nuovo valore,
    oppure la aggiunge in fondo al file se non esiste ancora. Restituisce
    True se il file è stato aggiornato, False se env_path non esiste (nel
    qual caso stampa un messaggio e non fa nulla).
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
        # Prima volta: la riga non esiste ancora — la aggiungiamo in fondo
        # invece di segnalare un errore.
        if not contenuto.endswith("\n"):
            contenuto += "\n"
        nuovo_contenuto = contenuto + f"{nome_variabile}={nuovo_valore}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(nuovo_contenuto)
    print(".env locale aggiornato.")
    return True
