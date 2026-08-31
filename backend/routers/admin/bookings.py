# Gestione delle prenotazioni dal pannello admin: lista paginata, cambio
# stato, note interne, ed export CSV (che riguarda comunque i dati delle
# prenotazioni, per questo vive nello stesso file). Vedi
# backend/routers/admin/__init__.py per la spiegazione generale del
# pacchetto.

import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, contains_eager, joinedload
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.users import User
from backend.schemas.booking import BookingStatoUpdate, BookingNoteUpdate
from backend.routers.admin import get_admin
from backend.services.booking_service import libera_slot_prenotazione
from backend.services.timezone_service import formatta_data_ora_rome
from backend.services.pagination_service import pagina_e_offset, busta_paginazione
from typing import Optional

router = APIRouter()


# ─── LISTA PRENOTAZIONI ──────────────────────────────────────
@router.get("/prenotazioni")
def get_prenotazioni(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db),
    stato: Optional[str] = None,
    pagina: int = 1,
    per_pagina: int = 20
):
    """
    Restituisce le prenotazioni con i dati del cliente e dello slot
    associati, paginate. Il parametro 'stato' permette di filtrare
    per confirmed / cancelled / no_show.
    """
    # stato, pagina e per_pagina non arrivano dal "corpo" della richiesta,
    # ma dalla parte finale dell'URL, tipo /admin/prenotazioni?stato=confirmed&pagina=2
    # — sono "query parameter". FastAPI li riconosce da solo perché non
    # compaiono nel percorso dell'endpoint tra graffe (come {slot_id}), e
    # li converte già al tipo giusto (int per pagina/per_pagina).

    pagina, per_pagina, offset = pagina_e_offset(pagina, per_pagina)

    # contains_eager(Booking.user)/(Booking.slot): i due .join(...) qui sotto
    # servivano già a filtrare, ma da soli non bastano a evitare che il
    # ciclo poco più sotto (p.user.*, p.slot.*, per OGNI prenotazione della
    # pagina) faccia una query separata a riga per ripescare user e slot —
    # un classico N+1. joinedload(Booking.review) aggiunge un JOIN a parte
    # per lo stesso motivo (niente da unire alla query principale, dato che
    # non tutte le prenotazioni hanno una recensione).
    query = db.query(Booking).join(User).join(Booking.slot).options(
        contains_eager(Booking.user),
        contains_eager(Booking.slot),
        joinedload(Booking.review)
    )

    if stato:
        query = query.filter(Booking.status == stato)

    # .count() qui conta il TOTALE di righe che soddisfano il filtro,
    # PRIMA di applicare la paginazione — ci serve per calcolare quante
    # pagine esistono in tutto.
    totale = query.count()

    # .offset(...) salta le prime N righe, .limit(...) ne prende al massimo
    # M — è così che si implementa la paginazione: pagina 1 con 20 per
    # pagina salta 0 righe e ne prende 20; pagina 2 salta 20 righe e ne
    # prende altre 20, e così via. Il simbolo "\" a fine riga permette di
    # spezzare una singola istruzione Python su più righe per leggibilità,
    # senza che Python la consideri "finita" a metà.
    prenotazioni = query.order_by(Booking.created_at.desc()) \
        .offset(offset) \
        .limit(per_pagina) \
        .all()

    risultato = []
    for p in prenotazioni:
        data_slot, ora_slot = formatta_data_ora_rome(p.slot.start_time)
        risultato.append({
            "id": p.id,
            "stato": p.status,
            "cliente": {
                "id": p.user.id,
                "nome": p.user.nome,
                "email": p.user.email,
                "categoria": p.user.categoria,
                "discord": p.user.discord_tag
            },
            "slot": {
                "data": data_slot,
                "ora": ora_slot
            },
            "servizio": p.service_type,
            "durata_ore": p.duration_hours,
            "prezzo_euro": p.price_cents / 100,
            "vod_link": p.vod_link,
            "replay_code": p.replay_code,
            "note_cliente": p.note_cliente,
            "note_admin": p.note_admin,
            # p.review è disponibile "gratis" grazie a backref="review" su
            # Review.booking (vedi backend/models/review.py) — None se il
            # cliente non ha ancora recensito questa sessione.
            "voto": p.review.voto if p.review else None,
            "creata_il": p.created_at.strftime("%d/%m/%Y %H:%M")
        })

    return busta_paginazione(risultato, totale, pagina, per_pagina)

# ─── AGGIORNA STATO PRENOTAZIONE ─────────────────────────────
@router.patch("/prenotazioni/{booking_id}/stato")
def aggiorna_stato(
    booking_id: int,
    dati: BookingStatoUpdate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Cambia lo stato di una prenotazione (confirmed / cancelled / no_show).
    Se cancellata → elimina evento da Google Calendar e libera lo slot.
    No-show non tocca calendario o slot: la sessione è già passata.
    """
    # @router.patch (non get/post): PATCH è il metodo HTTP pensato per
    # "modifica parziale" di qualcosa che esiste già — qui, cambiare solo
    # il campo status di una prenotazione, senza toccare il resto.
    # nuovo_stato arriva nel body JSON (BookingStatoUpdate), non più come
    # query param: uno stato non ammesso è già rifiutato da Pydantic (422)
    # prima ancora che questa funzione venga eseguita, nessun controllo
    # manuale da ripetere qui.
    prenotazione = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    # A differenza del claim atomico in create_booking (backend/routers/booking.py),
    # qui una semplice assegnazione basta: questa è un'azione manuale del
    # coach, non c'è nessun rischio di "gara" tra richieste concorrenti
    # sullo stesso oggetto.
    prenotazione.status = dati.nuovo_stato

    if dati.nuovo_stato == "cancelled":
        # libera_slot_prenotazione (backend/services/booking_service.py)
        # gestisce sia lo slot singolo sia, per le sessioni da 2 ore che ne
        # avevano uniti due, anche lo slot secondario — stessa funzione
        # riusata dalla cancellazione self-service del cliente.
        libera_slot_prenotazione(prenotazione, db)

    db.commit()
    return {"message": f"Stato aggiornato a {dati.nuovo_stato}"}

# ─── AGGIORNA NOTE ADMIN ─────────────────────────────────────
@router.patch("/prenotazioni/{booking_id}/note")
def aggiorna_note(
    booking_id: int,
    dati: BookingNoteUpdate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Aggiunge o modifica le note interne dell'admin
    su una prenotazione — non visibili al cliente.
    """
    prenotazione = db.query(Booking).filter(Booking.id == booking_id).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    prenotazione.note_admin = dati.note
    db.commit()
    return {"message": "Note aggiornate"}

# ─── EXPORT CSV ──────────────────────────────────────────────
@router.get("/export/csv")
def export_csv(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Genera e scarica un file CSV con tutte
    le prenotazioni — apribile in Excel.
    """
    prenotazioni = db.query(Booking).join(User).join(Booking.slot).options(
        contains_eager(Booking.user),
        contains_eager(Booking.slot)
    ).all()

    # io.StringIO() crea un "file finto" che vive solo in memoria, non sul
    # disco — utile qui perché non ci serve conservare questo CSV da
    # nessuna parte, ci serve solo generarlo al volo e spedirlo subito al
    # browser. csv.writer(output) è la libreria standard di Python per
    # scrivere file CSV: si occupa da sola di mettere le virgole al posto
    # giusto e di "proteggere" i valori che contengono virgole o virgolette.
    output = io.StringIO()
    writer = csv.writer(output)

    # intestazione colonne
    writer.writerow([
        "ID", "Stato", "Nome Cliente", "Email",
        "Categoria", "Servizio", "Data", "Ora",
        "Durata (ore)", "Prezzo (€)",
        "Note Cliente", "Note Admin", "Creata il"
    ])

    # una riga per ogni prenotazione
    for p in prenotazioni:
        data_slot, ora_slot = formatta_data_ora_rome(p.slot.start_time)
        writer.writerow([
            p.id,
            p.status,
            p.user.nome,
            p.user.email,
            p.user.categoria or "",
            p.service_type,
            data_slot,
            ora_slot,
            p.duration_hours,
            p.price_cents / 100,
            p.note_cliente or "",
            p.note_admin or "",
            p.created_at.strftime("%d/%m/%Y %H:%M")
        ])

    # Il "cursore" del nostro file finto è arrivato in fondo (dopo tutte le
    # scritture sopra) — seek(0) lo riporta all'inizio, altrimenti leggerlo
    # subito dopo (come facciamo sotto con .getvalue()) darebbe risultati
    # vuoti o parziali.
    output.seek(0)

    # restituisce il file come download
    return StreamingResponse(
        # .getvalue() legge tutto il contenuto testuale accumulato.
        # .encode("utf-8-sig") lo converte in byte (necessario perché HTTP
        # trasmette byte, non testo Python), aggiungendo anche un piccolo
        # marcatore iniziale (il "BOM") che aiuta Excel a riconoscere
        # correttamente gli accenti quando si apre il file.
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        # Questo header è quello che dice al browser "non mostrare questo
        # contenuto nella pagina, scaricalo come file" — con il nome
        # suggerito "prenotazioni.csv".
        headers={
            "Content-Disposition": "attachment; filename=prenotazioni.csv"
        }
    )
