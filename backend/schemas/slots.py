"""Schema Pydantic per la lista pubblica degli slot (GET /slots/).

Resta fino al pezzo 4.6b per le pagine vecchie nella cache dei browser.
SlotCreate, lo schema della creazione a mano dal pannello, è sparito nel
4.6a con l'endpoint: interpretava come ora italiana l'orario digitato.
"""

from pydantic import ConfigDict, BaseModel, field_serializer
from datetime import datetime, timezone


class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    duration_hours: int
    is_available: bool

    model_config = ConfigDict(from_attributes=True)

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
