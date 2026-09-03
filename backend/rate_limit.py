"""Istanza condivisa del rate limiter.

Vive in un modulo a sé, e non in `main.py`, per evitare un import
circolare: i router hanno bisogno del limiter e `main.py` importa i router.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Il conteggio è per indirizzo IP: il limite applicato agli endpoint
# (@limiter.limit("5/minute")) vale per chiamante, non globalmente.
limiter = Limiter(key_func=get_remote_address)
