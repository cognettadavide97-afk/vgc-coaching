# Numeri riassuntivi per il pannello admin: la dashboard (poche cifre
# chiave) e gli analytics (andamento negli ultimi mesi). Vedi
# backend/routers/admin/__init__.py per la spiegazione generale di come
# questo pacchetto è organizzato e perché get_admin si importa da lì.

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
    """
    Restituisce i numeri principali per la dashboard:
    totale prenotazioni, prenotazioni di oggi,
    totale incassato, prossimi slot liberi.
    """
    totale_prenotazioni = db.query(Booking).count()

    # "oggi" è il giorno solare a Roma, non quello del server: calcoliamo
    # i confini del giorno in ora italiana e li convertiamo in UTC per il filtro.
    oggi_rome_inizio = datetime.now(timezone.utc).astimezone(ROME_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    oggi_utc_inizio = oggi_rome_inizio.astimezone(timezone.utc).replace(tzinfo=None)
    oggi_utc_fine = (oggi_rome_inizio + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)

    # .join(Booking.slot) e non solo ".join(Slot)": da quando Booking ha due
    # colonne che puntano a slots (slot_id e slot_id_secondario, vedi
    # backend/models/booking.py), un join generico sarebbe ambiguo.
    prenotazioni_oggi = db.query(Booking).join(Booking.slot).filter(
        Slot.start_time >= oggi_utc_inizio,
        Slot.start_time < oggi_utc_fine
    ).count()

    # func.sum(...) chiede al DATABASE di sommare la colonna price_cents,
    # invece di scaricare tutte le righe in Python e sommarle noi — molto
    # più efficiente quando i dati crescono. .scalar() estrae il singolo
    # numero risultante dalla query (che altrimenti restituirebbe una
    # struttura più complessa). "or 0" gestisce il caso "nessuna
    # prenotazione confermata ancora": la somma di zero righe è None, non 0.
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

@router.get("/analytics")
def analytics(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Analytics essenziali, tutte sulla stessa finestra degli ultimi 6 mesi
    (calendario italiano): sessioni e incasso per mese, servizi più
    richiesti, tasso di no-show, clienti nuovi vs ricorrenti. Niente
    grafici decorativi: solo numeri e semplici barre proporzionali,
    calcolate lato client dai valori qui.
    """
    # Calcola le "chiavi" (anno, mese) degli ultimi 6 mesi, dal più vecchio
    # al più recente. range(5, -1, -1) produce 5, 4, 3, 2, 1, 0 — il terzo
    # argomento -1 è il "passo" (si va all'indietro). Il ciclo while dentro
    # gestisce il caso in cui sottraendo mesi si scenda sotto gennaio: "m -=
    # 12" e "a -= 1" fanno tornare indietro di un anno, esattamente come
    # contare le ore oltre la mezzanotte. Calcolato PRIMA della query qui
    # sotto perché ci serve per costruire il filtro sulla finestra.
    oggi_rome = datetime.now(timezone.utc).astimezone(ROME_TZ)
    chiavi_mesi = []
    anno, mese = oggi_rome.year, oggi_rome.month
    for i in range(5, -1, -1):
        m = mese - i
        a = anno
        while m <= 0:
            m += 12
            a -= 1
        chiavi_mesi.append((a, m))

    # Primo giorno del mese più vecchio della finestra, in ora italiana
    # convertito in UTC naive (stesso formato di Slot.start_time) — tutte
    # le statistiche qui sotto (non solo sessioni/incasso per mese) sono
    # calcolate SOLO su questa finestra di 6 mesi, non sull'intera storia:
    # ANALISI_2026-08-31.md (Blocco B2) segnalava che senza questo filtro
    # la query scaricava in RAM tutte le prenotazioni di sempre, con un
    # costo che cresce senza limite mano a mano che lo storico si allunga.
    anno_inizio, mese_inizio = chiavi_mesi[0]
    inizio_finestra_rome = datetime(anno_inizio, mese_inizio, 1, tzinfo=ROME_TZ)
    inizio_finestra_utc = inizio_finestra_rome.astimezone(timezone.utc).replace(tzinfo=None)

    # A differenza della dashboard sopra (che usa query aggregate SQL come
    # func.sum), qui scarichiamo le prenotazioni della finestra in una volta
    # sola e facciamo i calcoli in Python. È una scelta deliberata: i
    # calcoli servono (mese per mese, per servizio, per stato...) sono
    # complessi da esprimere in SQL puro, e per un progetto di queste
    # dimensioni (poche centinaia di prenotazioni, non milioni) è più
    # semplice e leggibile farlo con un ciclo Python piuttosto che con SQL
    # molto elaborato.
    # contains_eager(Booking.slot): il .join(Booking.slot) qui sotto serve
    # comunque solo a FILTRARE/ordinare — senza dirlo esplicitamente a
    # SQLAlchemy, il ciclo poco più sotto (p.slot.start_time, due volte per
    # ogni prenotazione) farebbe ripartire una query separata per ogni
    # Slot, invece di riusare quello già preso col JOIN. Stessa tecnica già
    # usata per lo stesso motivo in backend/scheduler.py.
    prenotazioni = db.query(Booking).join(Booking.slot).options(contains_eager(Booking.slot)).filter(
        Slot.start_time >= inizio_finestra_utc
    ).all()
    ora_utc = ora_utc_naive()

    # Dizionari "accumulatori": inizializziamo ogni mese a 0, poi il ciclo
    # sotto li riempie mano a mano. {k: 0 for k in chiavi_mesi} è una "dict
    # comprehension" — come la list comprehension vista altrove, ma per
    # costruire un dizionario invece di una lista.
    sessioni_per_mese = {k: 0 for k in chiavi_mesi}
    incasso_per_mese = {k: 0 for k in chiavi_mesi}
    servizi_conteggio = {}
    no_show_count = 0
    confirmed_passate_count = 0
    prenotazioni_per_utente = {}

    # Un solo ciclo attraversa tutte le prenotazioni una volta sola,
    # aggiornando più statistiche insieme — più efficiente che fare cinque
    # cicli separati, uno per ogni statistica.
    for p in prenotazioni:
        rome_dt = utc_to_rome(p.slot.start_time)
        chiave_mese = (rome_dt.year, rome_dt.month)

        if p.status == "confirmed" and chiave_mese in sessioni_per_mese:
            sessioni_per_mese[chiave_mese] += 1
            incasso_per_mese[chiave_mese] += p.price_cents

        # .get(chiave, 0) legge un valore dal dizionario, o restituisce 0 se
        # la chiave non c'è ancora — evita un errore "KeyError" al primo
        # servizio mai incontrato, e permette di scrivere il conteggio in
        # una riga sola invece di un if/else.
        servizi_conteggio[p.service_type] = servizi_conteggio.get(p.service_type, 0) + 1

        if p.status == "no_show":
            no_show_count += 1
        elif p.status == "confirmed" and p.slot.start_time < ora_utc:
            confirmed_passate_count += 1

        prenotazioni_per_utente[p.user_id] = prenotazioni_per_utente.get(p.user_id, 0) + 1

    # Il "tasso di no-show" è calcolato solo sulle sessioni già CONCLUSE
    # (passate): una prenotazione confermata ma ancora nel futuro non è né
    # un successo né un no-show, è "in sospeso" — non ha senso includerla.
    totale_per_tasso = no_show_count + confirmed_passate_count
    # L'espressione condizionale "... if totale_per_tasso > 0 else 0" evita
    # una divisione per zero (che in Python solleverebbe un errore) quando
    # non c'è ancora nessuna sessione conclusa.
    tasso_no_show = round((no_show_count / totale_per_tasso) * 100, 1) if totale_per_tasso > 0 else 0

    # "sum(1 for c in ... if c == 1)" è una list comprehension usata dentro
    # sum(): per ogni valore che soddisfa la condizione, conta 1 — il
    # risultato è semplicemente "quanti elementi soddisfano la condizione".
    clienti_nuovi = sum(1 for c in prenotazioni_per_utente.values() if c == 1)
    clienti_ricorrenti = sum(1 for c in prenotazioni_per_utente.values() if c > 1)

    def etichetta_mese(chiave):
        # Una funzione "nidificata", definita dentro un'altra funzione: ha
        # senso qui perché serve solo qui dentro, per trasformare una
        # chiave (2026, 8) nel testo "Ago 2026" da mostrare nel grafico.
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
            # sorted(..., key=lambda x: -x["conteggio"]) ordina la lista in
            # base al conteggio, dal più alto al più basso. "lambda" è un
            # modo per scrivere una funzione piccola e "usa e getta", senza
            # doverla definire con "def" a parte — qui dice "per ordinare,
            # guarda x['conteggio']", e il meno davanti inverte l'ordine
            # (normalmente sorted() ordina dal più piccolo al più grande).
            key=lambda x: -x["conteggio"]
        ),
        "tasso_no_show_percento": tasso_no_show,
        "clienti_nuovi": clienti_nuovi,
        "clienti_ricorrenti": clienti_ricorrenti
    }
