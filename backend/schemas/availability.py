# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic, e backend/schemas/slots.py per @field_validator. Questo file
# contiene gli schemi sia per le regole ricorrenti sia per i blocchi
# eccezionali (due funzionalità diverse, ma abbastanza piccole da stare
# comodamente in un solo file).

from pydantic import BaseModel, field_validator
from datetime import time, date, datetime
from typing import Optional


class AvailabilityRuleCreate(BaseModel):
    giorno_settimana: int  # 0=lunedì ... 6=domenica
    ora_inizio: time
    ora_fine: time
    durata_slot_ore: int = 1

    # A differenza di ServiceType in booking.py (che usa Literal per
    # limitare i valori possibili), qui usiamo un validator scritto a mano:
    # è utile quando la regola di validazione è più complessa di "deve
    # essere uno di questi valori" — qui è "deve essere un numero in un
    # certo intervallo". raise ValueError(...) dentro un validator è il modo
    # standard per far fallire la validazione con un messaggio d'errore
    # personalizzato, che Pydantic include nella risposta 422 al client.
    @field_validator("giorno_settimana")
    @classmethod
    def valida_giorno(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("giorno_settimana deve essere tra 0 (lunedì) e 6 (domenica)")
        return v


class AvailabilityRuleResponse(BaseModel):
    id: int
    giorno_settimana: int
    ora_inizio: time
    ora_fine: time
    durata_slot_ore: int
    attiva: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AvailabilityExceptionCreate(BaseModel):
    data_inizio: date
    data_fine: date
    motivo: Optional[str] = None


class AvailabilityExceptionResponse(BaseModel):
    id: int
    data_inizio: date
    data_fine: date
    motivo: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
