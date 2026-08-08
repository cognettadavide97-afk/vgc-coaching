# Vedi backend/schemas/users.py per la spiegazione generale di cosa sia uno
# schema Pydantic e perché esistono le coppie Create/Response. Questo file
# aggiunge un concetto nuovo: i "validator" e i "serializer" personalizzati,
# usati qui per risolvere il problema dei fusi orari.

from pydantic import BaseModel, field_validator, field_serializer
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ZoneInfo è la libreria standard di Python (dalla versione 3.9) per
# lavorare con i fusi orari "veri" — cioè che conoscono anche le regole di
# cambio ora legale di ogni paese, non solo un offset fisso. "Europe/Rome"
# è un identificatore standard (IANA) che rappresenta l'Italia con tutte le
# sue regole (CET in inverno, CEST/ora legale in estate).
ROME_TZ = ZoneInfo("Europe/Rome")


class SlotCreate(BaseModel):
    start_time: datetime
    duration_hours: int = 1

    # @field_validator("start_time") è un decoratore: dice a Pydantic "prima
    # di accettare il valore di start_time, fallo passare da questa
    # funzione". @classmethod è necessario perché Pydantic chiama questa
    # funzione sulla CLASSE (cls), non su un'istanza già creata — il campo
    # non esiste ancora come oggetto quando il validator gira.
    #
    # Il PROBLEMA che risolve: quando il coach crea uno slot dal pannello
    # admin, il browser manda un orario "grezzo" (es. "2026-08-12T18:00"),
    # senza dire a quale fuso orario si riferisce. Se lo salvassimo così
    # com'è, un domani un altro pezzo di codice potrebbe interpretarlo nel
    # fuso sbagliato. La SOLUZIONE: appena arriva, decidiamo noi
    # esplicitamente che va interpretato come ora italiana, e lo convertiamo
    # subito in UTC — così nel database (vedi il commento su start_time in
    # backend/models/slots.py) tutto è sempre nello stesso fuso, senza
    # ambiguità.
    @field_validator("start_time")
    @classmethod
    def interpreta_come_rome_e_converti_in_utc(cls, v: datetime) -> datetime:
        # v.tzinfo è None quando il datetime è "naive" (senza fuso). In quel
        # caso, .replace(tzinfo=ROME_TZ) non SPOSTA l'orario — gli attacca
        # solo l'etichetta "questo è ora italiana", senza cambiare i numeri.
        if v.tzinfo is None:
            v = v.replace(tzinfo=ROME_TZ)
        # .astimezone(timezone.utc) invece QUESTO sposta davvero l'orario,
        # convertendolo nell'equivalente UTC (es. le 18:00 italiane in
        # estate diventano le 16:00 UTC). .replace(tzinfo=None) toglie di
        # nuovo l'etichetta del fuso, per tornare "naive" prima di salvare
        # nel database, che si aspetta sempre valori senza tzinfo.
        return v.astimezone(timezone.utc).replace(tzinfo=None)


class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    duration_hours: int
    is_available: bool

    class Config:
        from_attributes = True

    # @field_serializer è l'opposto concettuale di @field_validator: invece
    # di controllare/trasformare un valore IN ENTRATA, decide come
    # trasformare un valore in USCITA, quando lo schema viene convertito in
    # JSON per la risposta. Qui risolve un problema simmetrico a quello del
    # validator sopra: il valore nel database è "naive" (senza fuso
    # esplicito), ma noi SAPPIAMO che è sempre UTC — quindi prima di
    # mandarlo al browser, gli riattacchiamo esplicitamente l'etichetta UTC,
    # così il JavaScript del frontend (in formatDate/formatTime, dentro
    # frontend/js/app.js) può interpretarlo correttamente senza doverlo
    # indovinare.
    @field_serializer("start_time")
    def serializza_con_offset_utc_esplicito(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        # .isoformat() trasforma il datetime in una stringa standard tipo
        # "2026-08-12T16:00:00+00:00" — il "+00:00" finale è l'offset UTC
        # esplicito di cui parlavamo, che rende inequivocabile a chiunque
        # legga questa stringa (browser compreso) a quale istante nel tempo
        # corrisponde, indipendentemente da dove si trovi chi la legge.
        return v.isoformat()
