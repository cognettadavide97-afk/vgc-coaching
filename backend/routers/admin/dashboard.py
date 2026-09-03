"""Metriche del pannello: dashboard sintetica e analytics sugli ultimi mesi."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.review import Review
from backend.routers.admin import get_admin
from backend.services.timezone_service import utc_to_rome, ROME_TZ, ora_utc_naive, formatta_data_ora_rome

router = APIRouter()


# ─── DASHBOARD ───────────────────────────────────────────────
@router.get("/dashboard")
def dashboard(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Numeri di sintesi: prenotazioni, incassato, media voti, prossimi slot.

    La media dei voti considera tutte le recensioni ricevute, comprese
    quelle non ancora approvate: è un dato interno, diverso da quello
    mostrato nella vetrina pubblica.
    """
    totale_prenotazioni = db.query(Booking).count()

    # "Oggi" è il giorno solare italiano, non quello del server: i confini
    # si calcolano in ora locale e si convertono in UTC per il confronto.
    oggi_rome_inizio = datetime.now(timezone.utc).astimezone(ROME_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    oggi_utc_inizio = oggi_rome_inizio.astimezone(timezone.utc).replace(tzinfo=None)
    oggi_utc_fine = (oggi_rome_inizio + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)

    # .join(Booking.slot) e non .join(Slot): con due colonne verso slots il
    # join generico è ambiguo.
    prenotazioni_oggi = db.query(Booking).join(Booking.slot).filter(
        Slot.start_time >= oggi_utc_inizio,
        Slot.start_time < oggi_utc_fine
    ).count()

    # Somma calcolata dal database invece che in Python. "or 0" copre il
    # caso senza prenotazioni: la somma di zero righe è None.
    totale_incassato = db.query(
        func.sum(Booking.price_cents)
    ).filter(
        Booking.status == "confirmed"
    ).scalar() or 0

    prossimi_slot = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora_utc_naive()
    ).order_by(Slot.start_time).limit(5).all()

    media_voto = db.query(func.avg(Review.voto)).scalar()

    def slot_liberi_dict(s):
        data, ora = formatta_data_ora_rome(s.start_time)
        return {"id": s.id, "data": data, "ora": ora}

    return {
        "totale_prenotazioni": totale_prenotazioni,
        "prenotazioni_oggi": prenotazioni_oggi,
        "totale_incassato_euro": totale_incassato / 100,
        "media_voto_recensioni": round(media_voto, 1) if media_voto is not None else None,
        "prossimi_slot_liberi": [slot_liberi_dict(s) for s in prossimi_slot]
    }

# ─── ANALYTICS ─────────────────────────────────────────────────
MESI_ITALIANI = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']

# Finestra mobile: "12 mesi da oggi", non l'anno solare corrente.
MESI_FINESTRA_ANALYTICS = 12

@router.get("/analytics")
def analytics(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Metriche sull'ultimo anno: sessioni, incassi, servizi, no-show, clienti.

    Tutte condividono la stessa finestra temporale, così i numeri restano
    confrontabili fra loro. Restituisce valori grezzi: la resa grafica è
    responsabilità del frontend.
    """
    # Chiavi (anno, mese) della finestra, dalla più vecchia. Il while
    # gestisce il passaggio all'anno precedente. Calcolate prima della
    # query perché servono a costruirne il filtro.
    oggi_rome = datetime.now(timezone.utc).astimezone(ROME_TZ)
    chiavi_mesi = []
    anno, mese = oggi_rome.year, oggi_rome.month
    for i in range(MESI_FINESTRA_ANALYTICS - 1, -1, -1):
        m = mese - i
        a = anno
        while m <= 0:
            m += 12
            a -= 1
        chiavi_mesi.append((a, m))

    # Il filtro sulla finestra vale per tutte le metriche, non solo per
    # quelle mensili: senza, la query caricherebbe in memoria l'intero
    # storico delle prenotazioni, con un costo che cresce senza limite.
    anno_inizio, mese_inizio = chiavi_mesi[0]
    inizio_finestra_rome = datetime(anno_inizio, mese_inizio, 1, tzinfo=ROME_TZ)
    inizio_finestra_utc = inizio_finestra_rome.astimezone(timezone.utc).replace(tzinfo=None)

    # Qui, a differenza della dashboard, i calcoli avvengono in Python su
    # un solo caricamento: le aggregazioni richieste (per mese, servizio e
    # stato insieme) sarebbero SQL elaborato, e su questi volumi il ciclo
    # è più leggibile. contains_eager evita che il ciclo rilegga lo slot
    # riga per riga.
    prenotazioni = db.query(Booking).join(Booking.slot).options(contains_eager(Booking.slot)).filter(
        Slot.start_time >= inizio_finestra_utc
    ).all()
    ora_utc = ora_utc_naive()

    # Accumulatori inizializzati a zero su tutti i mesi della finestra: i
    # mesi senza attività devono comparire comunque nel risultato.
    sessioni_per_mese = {k: 0 for k in chiavi_mesi}
    incasso_per_mese = {k: 0 for k in chiavi_mesi}
    servizi_conteggio = {}
    no_show_count = 0
    confirmed_passate_count = 0
    prenotazioni_per_utente = {}

    # Un solo passaggio aggiorna tutte le metriche insieme.
    for p in prenotazioni:
        rome_dt = utc_to_rome(p.slot.start_time)
        chiave_mese = (rome_dt.year, rome_dt.month)

        if p.status == "confirmed" and chiave_mese in sessioni_per_mese:
            sessioni_per_mese[chiave_mese] += 1
            incasso_per_mese[chiave_mese] += p.price_cents

        servizi_conteggio[p.service_type] = servizi_conteggio.get(p.service_type, 0) + 1

        if p.status == "no_show":
            no_show_count += 1
        elif p.status == "confirmed" and p.slot.start_time < ora_utc:
            confirmed_passate_count += 1

        prenotazioni_per_utente[p.user_id] = prenotazioni_per_utente.get(p.user_id, 0) + 1

    # Il tasso considera solo le sessioni già concluse: una prenotazione
    # futura non è né un successo né un no-show.
    totale_per_tasso = no_show_count + confirmed_passate_count
    tasso_no_show = round((no_show_count / totale_per_tasso) * 100, 1) if totale_per_tasso > 0 else 0

    clienti_nuovi = sum(1 for c in prenotazioni_per_utente.values() if c == 1)
    clienti_ricorrenti = sum(1 for c in prenotazioni_per_utente.values() if c > 1)

    def etichetta_mese(chiave):
        # Trasforma una chiave (2026, 8) nell'etichetta "Ago 2026".
        a, m = chiave
        return f"{MESI_ITALIANI[m - 1]} {a}"

    return {
        "sessioni_per_mese": [
            {"mese": etichetta_mese(k), "conteggio": sessioni_per_mese[k]}
            for k in chiavi_mesi
        ],
        "incasso_per_mese": [
            {"mese": etichetta_mese(k), "euro": incasso_per_mese[k] / 100}
            for k in chiavi_mesi
        ],
        "servizi_piu_richiesti": sorted(
            [{"servizio": k, "conteggio": v} for k, v in servizi_conteggio.items()],
            # Ordine decrescente per conteggio.
            key=lambda x: -x["conteggio"]
        ),
        "tasso_no_show_percento": tasso_no_show,
        "clienti_nuovi": clienti_nuovi,
        "clienti_ricorrenti": clienti_ricorrenti
    }
