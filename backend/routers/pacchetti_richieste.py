"""Richiesta di attivazione di un pacchetto dal sito pubblico.

Non crea alcun pacchetto: i pagamenti non passano dall'applicazione,
quindi l'endpoint si limita a inoltrare la richiesta di contatto. Il
pacchetto viene assegnato dal pannello di amministrazione una volta
incassato.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.pacchetto_richiesta import PacchettoRichiestaCreate
from backend.schemas.users import UserCreate
from backend.routers.users import get_or_create_user
from backend.services.package_service import CATALOGO_PACCHETTI
from backend.services.email_service import (
    invia_conferma_richiesta_pacchetto,
    invia_notifica_richiesta_pacchetto_admin
)
from backend.services.discord_service import invia_richiesta_pacchetto_discord
from backend.rate_limit import limiter

router = APIRouter(prefix="/pacchetti-richieste", tags=["Pacchetti"])


@router.post("/")
@limiter.limit("5/minute")
def richiedi_pacchetto(request: Request, richiesta: PacchettoRichiestaCreate, db: Session = Depends(get_db)):
    # Registra il contatto, come per la richiesta di consulenza.
    get_or_create_user(db, UserCreate(nome=richiesta.nome, email=richiesta.email, discord_tag=richiesta.discord_tag))

    nome_pacchetto = CATALOGO_PACCHETTI[richiesta.tipo]["nome"]

    invia_conferma_richiesta_pacchetto(
        email_cliente=richiesta.email,
        nome_cliente=richiesta.nome,
        nome_pacchetto=nome_pacchetto
    )

    invia_notifica_richiesta_pacchetto_admin(
        nome_cliente=richiesta.nome,
        email_cliente=richiesta.email,
        discord_tag=richiesta.discord_tag,
        nome_pacchetto=nome_pacchetto,
        messaggio=richiesta.messaggio
    )

    invia_richiesta_pacchetto_discord(
        nome_cliente=richiesta.nome,
        email_cliente=richiesta.email,
        discord_tag=richiesta.discord_tag,
        nome_pacchetto=nome_pacchetto,
        messaggio=richiesta.messaggio
    )

    return {"message": "Request received, we'll contact you shortly."}
