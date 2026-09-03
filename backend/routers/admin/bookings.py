"""Gestione delle prenotazioni: elenco, stato, note interne ed export CSV."""

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
    """Elenca le prenotazioni paginate, con i dati di cliente e slot.

    `stato` filtra per confirmed / cancelled / no_show.
    """
    pagina, per_pagina, offset = pagina_e_offset(pagina, per_pagina)

    # I join da soli non impediscono a SQLAlchemy di rileggere user e slot
    # riga per riga nel ciclo: contains_eager glieli fa riusare. La
    # recensione usa joinedload perché è opzionale e non è nel join.
    query = db.query(Booking).join(User).join(Booking.slot).options(
        contains_eager(Booking.user),
        contains_eager(Booking.slot),
        joinedload(Booking.review)
    )

    if stato:
        query = query.filter(Booking.status == stato)

    # Conteggio prima della paginazione: serve per il numero di pagine.
    totale = query.count()

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
            # None se la sessione non è ancora stata recensita.
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
    """Cambia lo stato di una prenotazione.

    La cancellazione libera lo slot ed elimina l'evento sul calendario.
    Lo stato no_show non tocca né slot né calendario: la sessione è già
    passata. Uno stato non ammesso viene respinto dallo schema con un 422.
    """
    prenotazione = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    # Assegnazione diretta: è un'azione manuale del coach, senza richieste
    # concorrenti sullo stesso oggetto da cui difendersi.
    prenotazione.status = dati.nuovo_stato

    if dati.nuovo_stato == "cancelled":
        # Gestisce anche lo slot secondario delle sessioni da 2 ore.
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
    """Imposta le note interne su una prenotazione, non visibili al cliente."""
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
    """Esporta tutte le prenotazioni in CSV.

    Deliberatamente non paginato: un export parziale non servirebbe.
    """
    prenotazioni = db.query(Booking).join(User).join(Booking.slot).options(
        contains_eager(Booking.user),
        contains_eager(Booking.slot)
    ).all()

    # Il CSV viene costruito in memoria e spedito subito: non serve
    # scriverlo su disco.
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

    # Riporta il cursore all'inizio prima della lettura.
    output.seek(0)

    # restituisce il file come download
    return StreamingResponse(
        # utf-8-sig e non utf-8: il BOM iniziale è ciò che fa interpretare
        # correttamente gli accenti a Excel.
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        # Forza il download invece della visualizzazione nel browser.
        headers={
            "Content-Disposition": "attachment; filename=prenotazioni.csv"
        }
    )
