"""Schemi Pydantic per la disponibilità: regole ricorrenti e blocchi."""

from pydantic import BaseModel, field_validator
from datetime import time, date, datetime
from typing import Optional


class AvailabilityRuleCreate(BaseModel):
    giorno_settimana: int  # 0=lunedì ... 6=domenica
    ora_inizio: time
    ora_fine: time
    durata_slot_ore: int = 1

    @field_validator("giorno_settimana")
    @classmethod
    def valida_giorno(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("giorno_settimana deve essere tra 0 (lunedì) e 6 (domenica)")
        return v

    @field_validator("durata_slot_ore")
    @classmethod
    def valida_durata(cls, v: int) -> int:
        """Ammette solo slot da 1 ora.

        Le sessioni da 2 ore nascono dall'unione di due slot da 1 ora al
        momento della prenotazione, dove vale il vincolo sull'orario di
        inizio. Uno slot da 2 ore generato qui aggirerebbe quel vincolo.
        Il controllo è lato server perché il form admin non è l'unica via:
        una richiesta HTTP diretta può inviare qualsiasi valore.
        """
        if v != 1:
            raise ValueError("Il calendario genera solo slot da 1 ora — le sessioni da 2h uniscono due slot da 1h adiacenti al momento della prenotazione")
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
