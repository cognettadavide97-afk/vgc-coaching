"""Schemi Pydantic per la disponibilità: regole ricorrenti e blocchi."""

from pydantic import ConfigDict, BaseModel, field_validator
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

    @field_validator("ora_inizio", "ora_fine")
    @classmethod
    def valida_ora_piena(cls, v: time) -> time:
        """Ammette solo ore piene (18:00, non 18:30).

        La guardia contro la doppia vendita confronta inizi esatti
        (models/ora_prenotata.py): una sessione alle 18:00 e una alle 18:30
        si sovrappongono ma hanno inizi diversi, e passerebbero entrambe.
        Con regole a ore piene ogni prenotazione inizia all'ora piena e il
        caso non può nascere. Misurato in produzione il 2026-11-21: nessuna
        regola con minuti.
        """
        if v.minute or v.second or v.microsecond:
            raise ValueError("Le regole usano solo ore piene (es. 18:00, non 18:30)")
        return v

    @field_validator("durata_slot_ore")
    @classmethod
    def valida_durata(cls, v: int) -> int:
        """Ammette solo slot da 1 ora.

        Le sessioni da 2 ore nascono da due ore consecutive della regola,
        ogni 2 ore dal suo inizio (services/disponibilita_service.py), che
        ignora le regole con durata diversa. Fino al pezzo 4.3 il vincolo
        impediva anche di generare slot da 2 ore, che saltavano il controllo
        sull'orario d'inizio delle sessioni lunghe.
        Il controllo è lato server perché il form admin non è l'unica via:
        una richiesta HTTP diretta può inviare qualsiasi valore.
        """
        if v != 1:
            raise ValueError("Le regole usano solo durate da 1 ora: le sessioni da 2 ore uniscono due ore consecutive della regola")
        return v


class AvailabilityRuleResponse(BaseModel):
    id: int
    giorno_settimana: int
    ora_inizio: time
    ora_fine: time
    durata_slot_ore: int
    attiva: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)
