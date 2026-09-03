"""Richiesta di call conoscitiva gratuita.

Deliberatamente fuori dal sistema di slot e prenotazioni: il cliente
lascia solo i propri contatti e l'orario viene concordato in privato.
Nessuno slot viene occupato, nessuna prenotazione creata, nessun evento
sul calendario.
"""

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
    # Registra comunque il contatto: se in seguito prenoterà con la stessa
    # email verrà ritrovato invece di essere duplicato.
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
