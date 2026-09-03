"""Genera l'hash bcrypt della password di amministrazione.

    python scripts/hash_admin_password.py

Da eseguire in locale ogni volta che si cambia la password. Chiede la
password da tastiera senza mostrarla e senza lasciarla nella cronologia
della shell, stampa l'hash e propone di scriverlo nel .env locale.

Aggiorna solo l'ambiente locale: la variabile in produzione va cambiata a
mano dalla dashboard dell'hosting, per non modificarla senza conferma.
"""

import os
import re
import sys
import getpass
import bcrypt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env_utils import aggiorna_env_locale as aggiorna_env_locale_helper


def main():
    # getpass non fa eco dei caratteri digitati.
    password = getpass.getpass("Nuova password admin (non verrà mostrata): ")
    conferma = getpass.getpass("Ripetila per conferma: ")

    if password != conferma:
        print("Le due password non coincidono. Riprova.")
        sys.exit(1)

    if not password:
        print("La password non può essere vuota.")
        sys.exit(1)

    # Il sale generato da gensalt() resta incorporato nell'hash: per la
    # verifica successiva basta conservare l'hash, non il sale a parte.
    hash_bcrypt = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    print("\nNuovo ADMIN_PASSWORD_HASH ottenuto:")
    print(hash_bcrypt)

    risposta = input("\nAggiornarlo subito nel .env locale? [s/N] ").strip().lower()
    if risposta == "s":
        aggiorna_env_locale(hash_bcrypt)
    else:
        print("Nessuna modifica al .env locale.")

    print(
        "\nRicordati di aggiornare la variabile anche su Railway "
        "(Dashboard del progetto -> Variables): rimuovi ADMIN_PASSWORD (se "
        "presente) e imposta ADMIN_PASSWORD_HASH con l'hash sopra. Questo "
        "script aggiorna SOLO il .env locale, mai l'ambiente di produzione."
    )


def aggiorna_env_locale(nuovo_hash: str):
    if not os.path.exists(ENV_PATH):
        print(f"File .env non trovato in {ENV_PATH} — aggiornalo a mano.")
        return

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        contenuto = f.read()

    # Migrazione dal vecchio ADMIN_PASSWORD in chiaro: se quella riga
    # esiste ancora viene sostituita, per non lasciare entrambe nel file.
    # Negli altri casi si usa l'helper condiviso.
    nuovo_contenuto, sostituzioni_vecchia = re.subn(
        r"^ADMIN_PASSWORD=.*$",
        f"ADMIN_PASSWORD_HASH={nuovo_hash}",
        contenuto,
        count=1,
        flags=re.MULTILINE
    )

    if sostituzioni_vecchia > 0:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(nuovo_contenuto)
        print(".env locale aggiornato.")
        return

    aggiorna_env_locale_helper(ENV_PATH, "ADMIN_PASSWORD_HASH", nuovo_hash)


if __name__ == "__main__":
    main()
