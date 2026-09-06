"""Schemi Pydantic per gli slot.

Qui vive la conversione di fuso orario ai due confini dell'API: l'input
dell'amministratore viene interpretato come ora italiana e convertito in
UTC, l'output viene marcato con l'offset UTC esplicito.
"""

from pydantic import ConfigDict, BaseModel, field_validator, field_serializer
from datetime import datetime, timezone
from backend.services.timezone_service import ROME_TZ


class SlotCreate(BaseModel):
    start_time: datetime
    duration_hours: int = 1

    @field_validator("duration_hours")
    @classmethod
    def valida_durata(cls, v: int) -> int:
        """Ammette solo slot da 1 ora, come per le regole ricorrenti.

        Stesso vincolo di `AvailabilityRuleCreate.valida_durata`, e per lo
        stesso motivo: le sessioni da 2 ore nascono dall'unione di due slot
        da 1 ora al momento della prenotazione, dove viene applicato il
        vincolo sull'orario di inizio (15:00 o 17:00). Uno slot da 2 ore
        **salta quel controllo**, perché in `create_booking` vive nel ramo
        che confronta durata richiesta e durata dello slot: se coincidono,
        non viene mai eseguito.

        Fino al 2026-09-07 qui non c'era nessun controllo, e il vincolo era
        aggirabile dal pannello di amministrazione, che offriva "2 ore" fra
        le scelte. Uno slot così creato, oltretutto, non compariva mai ai
        clienti: il frontend mostra solo gli slot da 1 ora.

        Il controllo respinge anche 0 e i valori negativi, che passavano
        senza obiezioni, e le durate fuori listino, che facevano fallire la
        prenotazione con un 500 invece che con un errore leggibile.
        """
        if v != 1:
            raise ValueError(
                "Il calendario usa solo slot da 1 ora - le sessioni da 2h uniscono "
                "due slot da 1h adiacenti al momento della prenotazione"
            )
        return v

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
