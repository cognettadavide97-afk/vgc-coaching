"""Schemi Pydantic per le prenotazioni."""

from pydantic import ConfigDict, BaseModel, field_validator, model_validator
from datetime import datetime, timezone
from typing import Optional, Literal
from backend.schemas.users import EmailNormalizzata

# Literal al posto di str: un servizio non previsto viene respinto da
# Pydantic con un 422, senza controlli manuali nel router.
ServiceType = Literal["vod_review", "team_building", "bo3_sparring", "tournament_prep"]


class BookingCreate(BaseModel):
    """Dati accettati per creare una prenotazione.

    Non contiene il prezzo: lo calcola il server dalla durata. Accettarlo
    dal client permetterebbe di prenotare a importo arbitrario modificando
    la richiesta.
    """
    user_id: int

    # Obbligatoria solo nel flusso senza login, dove è l'unica prova che
    # `user_id` appartenga davvero a chi sta prenotando (gli id sono
    # sequenziali e facili da indovinare). Ignorata quando lo studente è
    # autenticato: in quel caso l'identità viene dal token. Stessa forma
    # minuscola della registrazione, così il confronto di booking.py:102
    # non dipende dalle maiuscole digitate (voce 9).
    email: Optional[EmailNormalizzata] = None

    # Inizio della sessione, uno degli orari di GET /disponibilita/, con il
    # suo fuso. Convertito in UTC naive qui, al confine (CLAUDE.md, Orari).
    start_time: Optional[datetime] = None

    # Solo per le pagine vecchie rimaste nella cache dei browser (voce 46),
    # che prenotano ancora per slot: il server ne ricava l'orario e lo
    # verifica come gli altri. Sparisce con la tabella slots (pezzo 4.6).
    slot_id: Optional[int] = None

    # `Literal` e non `int`: le uniche durate a listino sono 1 e 2 ore
    # (TABELLA_PREZZI in backend/routers/booking.py). Un valore fuori da
    # queste due arrivava fino al calcolo del prezzo e sollevava KeyError,
    # cioè un 500 al posto di un errore leggibile. Pydantic lo respinge
    # ora con un 422, prima che il router venga eseguito.
    duration_hours: Literal[1, 2] = 1
    service_type: ServiceType
    note_cliente: Optional[str] = None
    vod_link: Optional[str] = None
    replay_code: Optional[str] = None

    # Se valorizzato, la sessione scala un credito da un pacchetto attivo.
    # Proprietà e capienza del pacchetto sono comunque riverificate lato
    # server prima di applicarlo.
    package_id: Optional[int] = None

    @field_validator("start_time")
    @classmethod
    def in_utc_naive(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Porta l'orario in UTC naive, come nel database; rifiuta un orario senza fuso.

        Un orario senza fuso ("2026-12-01T18:00") è ambiguo: ora italiana o
        UTC? Gli orari di GET /disponibilita/ il fuso lo portano sempre.
        """
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("start_time must include a timezone offset")
        return v.astimezone(timezone.utc).replace(tzinfo=None)

    @model_validator(mode="after")
    def orario_o_slot(self):
        """Esattamente uno fra start_time e slot_id."""
        if (self.start_time is None) == (self.slot_id is None):
            raise ValueError("send either start_time or slot_id")
        return self


class BookingResponse(BaseModel):
    id: int
    user_id: int
    # None per le prenotazioni fatte per orario, che non hanno uno slot.
    slot_id: Optional[int]
    slot_id_secondario: Optional[int]
    duration_hours: int
    price_cents: int
    service_type: str
    status: str
    note_cliente: Optional[str]
    note_admin: Optional[str]
    vod_link: Optional[str]
    replay_code: Optional[str]
    package_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingStatoUpdate(BaseModel):
    # Nel corpo JSON e non come query param: gli stati finivano altrimenti
    # nei log di accesso del proxy e nella cronologia del browser.
    nuovo_stato: Literal["confirmed", "cancelled", "no_show"]


class BookingNoteUpdate(BaseModel):
    # Come sopra: una nota su un cliente è potenzialmente sensibile e non
    # deve comparire in un URL.
    note: str


class BookingResponseStudente(BaseModel):
    """Vista della prenotazione destinata allo studente.

    Identica a `BookingResponse` tranne `note_admin`, che è riservata al
    coach e non deve comparire in una risposta leggibile dal cliente.
    """
    id: int
    user_id: int
    slot_id: Optional[int]
    slot_id_secondario: Optional[int]
    duration_hours: int
    price_cents: int
    service_type: str
    status: str
    note_cliente: Optional[str]
    vod_link: Optional[str]
    replay_code: Optional[str]
    package_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
