from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.users import User
from backend.models.slots import Slot
from backend.services.auth_service import verifica_credenziali, crea_token, verifica_token
from typing import List, Optional
import csv
import io
from fastapi.responses import StreamingResponse
from datetime import datetime, date

router = APIRouter(prefix="/admin", tags=["Admin"])

# questo schema dice a FastAPI dove trovare il token
# nelle richieste HTTP — cercalo nell'header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

# ─── DIPENDENZA: VERIFICA ADMIN ──────────────────────────────
# questa funzione viene chiamata automaticamente su ogni
# endpoint protetto — se il token non è valido blocca tutto
def get_admin(token: str = Depends(oauth2_scheme)):
    username = verifica_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

# ─── LOGIN ───────────────────────────────────────────────────
@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Riceve username e password dal form di login.
    Se corretti restituisce un token JWT.
    """
    if not verifica_credenziali(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    token = crea_token(form.username)
    return {"access_token": token, "token_type": "bearer"}

# ─── DASHBOARD ───────────────────────────────────────────────
@router.get("/dashboard")
def dashboard(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Restituisce i numeri principali per la dashboard:
    totale prenotazioni, prenotazioni di oggi,
    totale incassato, prossimi slot liberi.
    """
    oggi = date.today()

    totale_prenotazioni = db.query(Booking).count()

    prenotazioni_oggi = db.query(Booking).join(Slot).filter(
        func.date(Slot.start_time) == oggi
    ).count()

    totale_incassato = db.query(
        func.sum(Booking.price_cents)
    ).filter(
        Booking.status == "confirmed"
    ).scalar() or 0

    prossimi_slot = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= datetime.now()
    ).order_by(Slot.start_time).limit(5).all()

    return {
        "totale_prenotazioni": totale_prenotazioni,
        "prenotazioni_oggi": prenotazioni_oggi,
        "totale_incassato_euro": totale_incassato / 100,
        "prossimi_slot_liberi": [
            {
                "id": s.id,
                "data": s.start_time.strftime("%d/%m/%Y"),
                "ora": s.start_time.strftime("%H:%M")
            }
            for s in prossimi_slot
        ]
    }

# ─── LISTA PRENOTAZIONI ──────────────────────────────────────
@router.get("/prenotazioni")
def get_prenotazioni(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db),
    stato: Optional[str] = None
):
    """
    Restituisce tutte le prenotazioni con i dati
    del cliente e dello slot associati.
    Il parametro 'stato' permette di filtrare
    per pending, confirmed o cancelled.
    """
    query = db.query(Booking).join(User).join(Slot)

    if stato:
        query = query.filter(Booking.status == stato)

    prenotazioni = query.order_by(Booking.created_at.desc()).all()

    risultato = []
    for p in prenotazioni:
        risultato.append({
            "id": p.id,
            "stato": p.status,
            "cliente": {
                "id": p.user.id,
                "nome": p.user.nome,
                "email": p.user.email,
                "showdown": p.user.showdown_username
            },
            "slot": {
                "data": p.slot.start_time.strftime("%d/%m/%Y"),
                "ora": p.slot.start_time.strftime("%H:%M")
            },
            "durata_ore": p.duration_hours,
            "prezzo_euro": p.price_cents / 100,
            "note_cliente": p.note_cliente,
            "note_admin": p.note_admin,
            "creata_il": p.created_at.strftime("%d/%m/%Y %H:%M")
        })

    return risultato

# ─── AGGIORNA STATO PRENOTAZIONE ─────────────────────────────
@router.patch("/prenotazioni/{booking_id}/stato")
def aggiorna_stato(
    booking_id: int,
    nuovo_stato: str,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Cambia lo stato di una prenotazione:
    pending → confirmed → cancelled
    """
    stati_validi = ["pending", "confirmed", "cancelled"]
    if nuovo_stato not in stati_validi:
        raise HTTPException(status_code=400, detail="Stato non valido")

    prenotazione = db.query(Booking).filter(Booking.id == booking_id).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    prenotazione.status = nuovo_stato

    # se cancellata, libera lo slot
    if nuovo_stato == "cancelled":
        slot = db.query(Slot).filter(Slot.id == prenotazione.slot_id).first()
        if slot:
            slot.is_available = True

    db.commit()
    return {"message": f"Stato aggiornato a {nuovo_stato}"}

# ─── AGGIORNA NOTE ADMIN ─────────────────────────────────────
@router.patch("/prenotazioni/{booking_id}/note")
def aggiorna_note(
    booking_id: int,
    note: str,
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

    prenotazione.note_admin = note
    db.commit()
    return {"message": "Note aggiornate"}

# ─── LISTA CLIENTI ───────────────────────────────────────────
@router.get("/clienti")
def get_clienti(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Restituisce tutti i clienti con il numero
    di sessioni effettuate e il totale speso.
    """
    clienti = db.query(User).all()
    risultato = []

    for c in clienti:
        sessioni = db.query(Booking).filter(
            Booking.user_id == c.id
        ).count()

        totale_speso = db.query(
            func.sum(Booking.price_cents)
        ).filter(
            Booking.user_id == c.id
        ).scalar() or 0

        risultato.append({
            "id": c.id,
            "nome": c.nome,
            "email": c.email,
            "showdown": c.showdown_username,
            "telefono": c.telefono,
            "sessioni_totali": sessioni,
            "totale_speso_euro": totale_speso / 100,
            "registrato_il": c.created_at.strftime("%d/%m/%Y")
        })

    return risultato

# ─── GESTIONE SLOT ───────────────────────────────────────────
@router.get("/slots")
def get_slots_admin(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce tutti gli slot, liberi e occupati."""
    slots = db.query(Slot).order_by(Slot.start_time).all()
    return [
        {
            "id": s.id,
            "data": s.start_time.strftime("%d/%m/%Y"),
            "ora": s.start_time.strftime("%H:%M"),
            "durata_ore": s.duration_hours,
            "disponibile": s.is_available
        }
        for s in slots
    ]

@router.delete("/slots/{slot_id}")
def elimina_slot(
    slot_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina uno slot. Se ha prenotazioni collegate
    (anche cancellate) non può essere eliminato fisicamente
    per preservare lo storico — viene invece disattivato.
    """
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")

    # controlla se esistono prenotazioni collegate a questo slot
    prenotazioni_collegate = db.query(Booking).filter(
        Booking.slot_id == slot_id
    ).count()

    if prenotazioni_collegate > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile eliminare: questo slot ha {prenotazioni_collegate} prenotazione/i collegate nello storico. Non può essere rimosso per preservare i dati."
        )

    db.delete(slot)
    db.commit()
    return {"message": "Slot eliminato"}

# ─── EXPORT CSV ──────────────────────────────────────────────
@router.get("/export/csv")
def export_csv(
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # verifica manuale del token passato come parametro URL
    if not token:
        raise HTTPException(status_code=401, detail="Token mancante")
    username = verifica_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Token non valido")
    """
    Genera e scarica un file CSV con tutte
    le prenotazioni — apribile in Excel.
    """
    prenotazioni = db.query(Booking).join(User).join(Slot).all()

    # crea il CSV in memoria senza salvarlo su disco
    output = io.StringIO()
    writer = csv.writer(output)

    # intestazione colonne
    writer.writerow([
        "ID", "Stato", "Nome Cliente", "Email",
        "Showdown Username", "Data", "Ora",
        "Durata (ore)", "Prezzo (€)",
        "Note Cliente", "Note Admin", "Creata il"
    ])

    # una riga per ogni prenotazione
    for p in prenotazioni:
        writer.writerow([
            p.id,
            p.status,
            p.user.nome,
            p.user.email,
            p.user.showdown_username or "",
            p.slot.start_time.strftime("%d/%m/%Y"),
            p.slot.start_time.strftime("%H:%M"),
            p.duration_hours,
            p.price_cents / 100,
            p.note_cliente or "",
            p.note_admin or "",
            p.created_at.strftime("%d/%m/%Y %H:%M")
        ])

    output.seek(0)

    # restituisce il file come download
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=prenotazioni.csv"
        }
    )