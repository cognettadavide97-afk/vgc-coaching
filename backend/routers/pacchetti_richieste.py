# Gestisce la richiesta di attivazione di un pacchetto di sessioni dal
# sito pubblico (bottone "Select this package" su ogni card in
# frontend/index.html). Stesso spirito di backend/routers/consulenza.py:
# il progetto non gestisce pagamenti in-app (vedi TABELLA_PREZZI in
# booking.py e CATALOGO_PACCHETTI in package_service.py), quindi questo
# endpoint NON crea un pacchetto vero — manda solo i contatti del cliente
# al coach, che poi lo assegna davvero da POST /admin/pacchetti
# (backend/routers/admin/packages.py) dopo aver ricevuto il pagamento concordato
# privatamente.

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
    # get_or_create_user (backend/routers/users.py) tiene traccia del
    # cliente anche per questo canale, come già fa consulenza.py.
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
