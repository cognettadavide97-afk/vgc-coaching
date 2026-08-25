# Script "una tantum" per migrare il login admin dalla vecchia password in
# chiaro (ADMIN_PASSWORD nel .env) al nuovo ADMIN_PASSWORD_HASH (vedi
# backend/services/auth_service.py). Va eseguito A MANO dal computer del
# coach: chiede la password a tastiera (senza mostrarla a schermo, e senza
# lasciarla nella cronologia della shell come farebbe passarla come
# argomento) e stampa l'hash bcrypt corrispondente.
#
# QUANDO SERVE
# Una volta, al momento di attivare la nuova verifica con hash. Si può
# rilanciare in seguito ogni volta che si vuole cambiare la password admin:
# basta generare un nuovo hash e sostituirlo.
#
# COME SI USA
#   python scripts/hash_admin_password.py
# Poi:
#   1. stampa il nuovo hash
#   2. chiede se aggiornarlo subito nel .env locale (sostituendo la riga
#      ADMIN_PASSWORD_HASH=... o, se ancora presente, la vecchia
#      ADMIN_PASSWORD=... in chiaro)
#   3. ricorda di aggiornare la stessa variabile su Railway (produzione) —
#      quello NON lo fa questo script, va fatto a mano dalla dashboard
#      Railway (Variables: rimuovi ADMIN_PASSWORD, aggiungi
#      ADMIN_PASSWORD_HASH), per non toccare l'ambiente di produzione senza
#      conferma esplicita.

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
    # getpass.getpass(), a differenza di input(), non mostra a schermo i
    # caratteri digitati — la stessa esperienza di un prompt "sudo password".
    password = getpass.getpass("Nuova password admin (non verrà mostrata): ")
    conferma = getpass.getpass("Ripetila per conferma: ")

    if password != conferma:
        print("Le due password non coincidono. Riprova.")
        sys.exit(1)

    if not password:
        print("La password non può essere vuota.")
        sys.exit(1)

    # bcrypt.gensalt() genera un "sale" casuale diverso ogni volta: due
    # utenti con la stessa password ottengono hash diversi, e lo stesso sale
    # resta incorporato nell'hash finale (per questo basta salvare l'hash,
    # non il sale a parte, per poi verificare la password in futuro).
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

    # Caso di migrazione one-shot, specifico di questo script: se esiste
    # ancora la vecchia riga ADMIN_PASSWORD= (password in chiaro), la
    # sostituisce del tutto con la nuova ADMIN_PASSWORD_HASH=, invece di
    # lasciarle entrambe nel file. Per ogni altro caso (nessuna vecchia
    # riga da migrare: aggiorna o aggiungi ADMIN_PASSWORD_HASH) riusa lo
    # stesso helper condiviso degli altri script "una tantum" del progetto
    # (scripts/_env_utils.py).
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
