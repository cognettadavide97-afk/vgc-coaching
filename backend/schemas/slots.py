"""Schemi Pydantic per gli slot.

Qui vive la conversione di fuso orario ai due confini dell'API: l'input
dell'amministratore viene interpretato come ora italiana e convertito in
UTC, l'output viene marcato con l'offset UTC esplicito.
"""

from pydantic import BaseModel, field_validator, field_serializer
from datetime import datetime, timezone
from backend.services.timezone_service import ROME_TZ


class SlotCreate(BaseModel):
    start_time: datetime
    duration_hours: int = 1

    @field_validator("start_time")
    @classmethod
    def interpreta_come_rome_e_converti_in_utc(cls, v: datetime) -> datetime:
        """Interpreta l'orario ricevuto come ora italiana e lo salva in UTC.

        Il browser invia un orario privo di fuso ("2026-08-12T18:00"):
        senza questa conversione il valore finirebbe nel database in un
        fuso ambiguo. Facendola qui, il resto del codice riceve sempre UTC.
        """
        if v.tzinfo is None:
            v = v.replace(tzinfo=ROME_TZ)
        return v.astimezone(timezone.utc).replace(tzinfo=None)


class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    duration_hours: int
    is_available: bool

    class Config:
        from_attributes = True

    @field_serializer("start_time")
    def serializza_con_offset_utc_esplicito(self, v: datetime) -> str:
        """Serializza con offset UTC esplicito.

        Il valore nel database è naive: senza reintrodurre l'offset, il
        JavaScript del frontend lo interpreterebbe come ora locale del
        browser, sbagliando l'orario mostrato.
        """
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()
