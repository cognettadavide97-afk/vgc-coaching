"""Schemi Pydantic per le prenotazioni."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

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
    # autenticato: in quel caso l'identità viene dal token.
    email: Optional[str] = None

    slot_id: int
    duration_hours: int = 1
    service_type: ServiceType
    note_cliente: Optional[str] = None
    vod_link: Optional[str] = None
    replay_code: Optional[str] = None

    # Se valorizzato, la sessione scala un credito da un pacchetto attivo.
    # Proprietà e capienza del pacchetto sono comunque riverificate lato
    # server prima di applicarlo.
    package_id: Optional[int] = None


class BookingResponse(BaseModel):
    id: int
    user_id: int
    slot_id: int
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

    class Config:
        from_attributes = True


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
    slot_id: int
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

    class Config:
        from_attributes = True
