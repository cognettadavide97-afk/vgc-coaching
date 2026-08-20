# Gestisce la richiesta di una call conoscitiva gratuita di 20 minuti.
# Deliberatamente NON passa dal sistema di slot/prenotazioni (backend/
# routers/booking.py): "da accordare in privato" vuol dire che il cliente
# non sceglie un orario fisso sul sito, manda solo i suoi contatti e il
# coach lo ricontatta per fissare l'orario a mano — nessuno Slot bloccato,
# nessuna riga in "bookings", nessun evento sul calendario.

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.consulenza import ConsulenzaCreate
from backend.schemas.users import UserCreate
from backend.routers.users import get_or_create_user
from backend.services.email_service import (
    invia_conferma_richiesta_consulenza,
    invia_notifica_richiesta_consulenza_admin
)
from backend.services.discord_service import invia_richiesta_consulenza_discord
from backend.rate_limit import limiter

router = APIRouter(prefix="/consulenze", tags=["Consulenze"])


@router.post("/")
@limiter.limit("5/minute")
def richiedi_consulenza(request: Request, richiesta: ConsulenzaCreate, db: Session = Depends(get_db)):
    # get_or_create_user (backend/routers/users.py) tiene traccia del
    # cliente anche per questo canale — se in futuro prenota una sessione
    # vera con la stessa email, lo ritrova invece di duplicarlo.
    get_or_create_user(db, UserCreate(nome=richiesta.nome, email=richiesta.email, discord_tag=richiesta.discord_tag))

    invia_conferma_richiesta_consulenza(email_cliente=richiesta.email, nome_cliente=richiesta.nome)

    invia_notifica_richiesta_consulenza_admin(
        nome_cliente=richiesta.nome,
        email_cliente=richiesta.email,
        discord_tag=richiesta.discord_tag,
        messaggio=richiesta.messaggio
    )

    invia_richiesta_consulenza_discord(
        nome_cliente=richiesta.nome,
        email_cliente=richiesta.email,
        discord_tag=richiesta.discord_tag,
        messaggio=richiesta.messaggio
    )

    return {"message": "Request received, we'll contact you shortly."}
