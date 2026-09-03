"""Conversioni e confronti di orario condivisi da router e servizi.

Convenzione del progetto: nel database gli orari sono sempre UTC *naive*
(senza `tzinfo`). La conversione a ora italiana appartiene al livello di
presentazione e avviene solo al momento di mostrare un valore all'utente,
mai nella logica di business.

Centralizzare qui queste quattro operazioni evita che la stessa conversione
venga reimplementata — e sbagliata in modo diverso — in ogni punto d'uso.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ZoneInfo (non un offset fisso) perché l'Italia alterna CET e CEST:
# un offset costante sbaglierebbe di un'ora per metà anno.
ROME_TZ = ZoneInfo("Europe/Rome")


def utc_to_rome(dt: datetime) -> datetime:
    """Converte un datetime UTC naive in ora di Roma, per la visualizzazione.

    Accetta anche datetime già "aware", che lascia invariati nel fuso di
    partenza prima di convertirli.
    """
    # `replace` etichetta il valore come UTC senza spostare i numeri;
    # `astimezone` esegue lo spostamento effettivo. Invertire i due passaggi
    # produce un orario sfalsato dell'offset corrente.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ROME_TZ)


def formatta_data_ora_rome(dt: datetime) -> tuple[str, str]:
    """Converte in ora di Roma e restituisce la coppia (data, ora) da mostrare.

    Formato: ("gg/mm/aaaa", "hh:mm"). È il formato usato da tutte le viste
    del pannello di amministrazione e dall'export CSV, così che restino
    allineate modificando un punto solo.
    """
    dt_rome = utc_to_rome(dt)
    return dt_rome.strftime("%d/%m/%Y"), dt_rome.strftime("%H:%M")


def ora_utc_naive() -> datetime:
    """Restituisce l'istante corrente come UTC naive.

    Da usare al posto di `datetime.now()` per qualsiasi confronto con una
    colonna datetime del database: confrontare un datetime aware con uno
    naive solleva `TypeError`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def intervalli_si_sovrappongono(inizio1: datetime, fine1: datetime, inizio2: datetime, fine2: datetime) -> bool:
    """Indica se due intervalli temporali si sovrappongono.

    Gli intervalli sono trattati come semiaperti [inizio, fine): due
    intervalli che si toccano soltanto sull'estremo (10:00-11:00 e
    11:00-12:00) non sono considerati sovrapposti, altrimenti ogni coppia di
    slot adiacenti risulterebbe in conflitto.
    """
    return inizio1 < fine2 and inizio2 < fine1
