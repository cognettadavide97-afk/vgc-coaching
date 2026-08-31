# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic e del pattern Create/Response.

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

# Literal è un tipo speciale di Python (dal modulo typing, non solo di
# Pydantic) che dice "questo valore può essere SOLO uno di questi testi
# esatti, nient'altro". A differenza di "str" (che accetterebbe qualunque
# stringa), Literal[...] fa sì che Pydantic rifiuti automaticamente
# qualunque servizio diverso da questi quattro — è un modo per avere
# nel codice Python l'equivalente di un "enum" senza dover creare una
# classe Enum a parte. Il valore effettivamente scelto arriva così già
# garantito valido a tutto il resto del programma.
ServiceType = Literal["vod_review", "team_building", "bo3_sparring", "tournament_prep"]


class BookingCreate(BaseModel):
    user_id: int
    # Usata per verificare, nel flusso guest (nessun login), che user_id
    # appartenga davvero a chi sta prenotando: senza questo controllo
    # user_id è un intero qualsiasi (in produzione una PK sequenziale,
    # banale da indovinare) che chiunque può scrivere in una richiesta HTTP
    # diretta per creare prenotazioni a nome di un altro cliente esistente.
    # Ignorata quando lo studente è loggato via Discord: in quel caso
    # l'identità arriva dal token verificato dal server, mai da qui (vedi
    # create_booking in backend/routers/booking.py).
    email: Optional[str] = None
    slot_id: int
    duration_hours: int = 1
    service_type: ServiceType  # deve essere uno dei 4 valori sopra, altrimenti 422 automatico
    note_cliente: Optional[str] = None
    vod_link: Optional[str] = None
    replay_code: Optional[str] = None

    # Se valorizzato, la sessione viene "pagata" scalando un credito da un
    # pacchetto attivo del cliente (vedi backend/models/package.py) invece
    # che con il prezzo normale — controllato e validato server-side in
    # create_booking, mai fidandosi solo di questo campo.
    package_id: Optional[int] = None

    # Nota una cosa che NON c'è qui: nessun campo "price". Il prezzo non lo
    # decide mai il client — viene sempre calcolato dal server (vedi
    # TABELLA_PREZZI in backend/routers/booking.py) in base a duration_hours.
    # Se permettessimo al client di mandare direttamente il prezzo,
    # chiunque potrebbe modificare la richiesta HTTP con gli strumenti
    # sviluppatore del browser e prenotare a prezzo zero: il server non
    # deve MAI fidarsi di dati sensibili calcolabili in autonomia.


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


class BookingResponseStudente(BaseModel):
    # Stessi campi di BookingResponse TRANNE note_admin — usato dagli
    # endpoint lato studente (es. cancella_prenotazione_cliente in
    # backend/routers/booking.py): note_admin è documentato come "visibile
    # solo al coach" (vedi STATO_PROGETTO.md), non deve mai arrivare in una
    # risposta che lo studente stesso può leggere.
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
