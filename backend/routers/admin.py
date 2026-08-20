# Questo è il file più grande del progetto, perché il pannello admin fa
# davvero molte cose: login, dashboard, analytics, gestione prenotazioni,
# clienti, slot, regole ricorrenti, blocchi eccezionali, export CSV. Vedi
# backend/routers/users.py per la spiegazione generale di un router
# FastAPI — qui ci concentriamo sulle parti nuove: il login JWT vero e
# proprio, la paginazione, e le query aggregate.

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.users import User
from backend.models.slots import Slot
from backend.models.client_note import ClientNote
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.models.package import Package
from backend.models.review import Review
from backend.schemas.client_note import ClientNoteCreate, ClientNoteResponse
from backend.schemas.availability import (
    AvailabilityRuleCreate, AvailabilityRuleResponse,
    AvailabilityExceptionCreate, AvailabilityExceptionResponse
)
from backend.schemas.package import PackageCreate, PackageResponse
from backend.schemas.review import ReviewApprovazione
from backend.services.package_service import CATALOGO_PACCHETTI
from backend.services.auth_service import verifica_credenziali, crea_token, verifica_token
from typing import List, Optional
import csv
import io
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta, timezone
from backend.services.calendar_service import leggi_eventi_calendario, sincronizza_slot_con_calendario
from backend.services.booking_service import libera_slot_prenotazione
from backend.services.timezone_service import utc_to_rome, ROME_TZ
from backend.services.availability_service import genera_slot_da_regola, applica_blocco_eccezionale

router = APIRouter(prefix="/admin", tags=["Admin"])

# questo schema dice a FastAPI dove trovare il token
# nelle richieste HTTP — cercalo nell'header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

# ─── DIPENDENZA: VERIFICA ADMIN ──────────────────────────────
# questa funzione viene chiamata automaticamente su ogni
# endpoint protetto — se il token non è valido blocca tutto
def get_admin(token: str = Depends(oauth2_scheme)):
    # Questa è LA dependency più importante del progetto: quasi ogni
    # funzione in questo file ha "admin: str = Depends(get_admin)" tra i
    # parametri, ed è proprio questo che rende quell'endpoint "riservato al
    # coach". FastAPI, prima di eseguire l'endpoint vero, esegue sempre
    # get_admin(): se qui dentro viene sollevata un'eccezione, l'endpoint
    # non viene MAI raggiunto — il client riceve direttamente l'errore 401.
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
    # OAuth2PasswordRequestForm è una classe "pronta" di FastAPI che sa
    # leggere da sola un login username+password mandato in un formato
    # standard (non JSON, ma "form-urlencoded" — lo stesso formato che
    # userebbe un normale form HTML). Usato con Depends() (senza
    # argomenti), FastAPI costruisce automaticamente l'oggetto "form" con
    # form.username e form.password già pronti.
    if not verifica_credenziali(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    token = crea_token(form.username)
    # Il client (frontend/js/admin.js) salverà questo access_token e lo
    # userà in ogni richiesta successiva — è l'inizio della "sessione"
    # admin, anche se tecnicamente non esiste nessuna sessione salvata sul
    # server: il token stesso, come spiegato in auth_service.py, contiene
    # tutto il necessario per verificarsi da solo.
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
        Slot.start_time >= datetime.now(timezone.utc).replace(tzinfo=None)
    ).order_by(Slot.start_time).limit(5).all()

    media_voto = db.query(func.avg(Review.voto)).scalar()

    return {
        "totale_prenotazioni": totale_prenotazioni,
        "prenotazioni_oggi": prenotazioni_oggi,
        "totale_incassato_euro": totale_incassato / 100,
        "media_voto_recensioni": round(media_voto, 1) if media_voto is not None else None,
        "prossimi_slot_liberi": [
            {
                "id": s.id,
                "data": utc_to_rome(s.start_time).strftime("%d/%m/%Y"),
                "ora": utc_to_rome(s.start_time).strftime("%H:%M")
            }
            for s in prossimi_slot
        ]
    }

# ─── ANALYTICS ─────────────────────────────────────────────────
MESI_ITALIANI = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']

@router.get("/analytics")
def analytics(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Analytics essenziali: sessioni e incasso per mese (ultimi 6 mesi,
    calendario italiano), servizi più richiesti, tasso di no-show,
    clienti nuovi vs ricorrenti. Niente grafici decorativi: solo numeri
    e semplici barre proporzionali, calcolate lato client dai valori qui.
    """
    # A differenza della dashboard sopra (che usa query aggregate SQL come
    # func.sum), qui scarichiamo TUTTE le prenotazioni in una volta sola e
    # facciamo i calcoli in Python. È una scelta deliberata: i calcoli
    # servono (mese per mese, per servizio, per stato...) sono complessi da
    # esprimere in SQL puro, e per un progetto di queste dimensioni (poche
    # centinaia di prenotazioni, non milioni) è più semplice e leggibile
    # farlo con un ciclo Python piuttosto che con SQL molto elaborato.
    prenotazioni = db.query(Booking).join(Booking.slot).all()
    ora_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # Calcola le "chiavi" (anno, mese) degli ultimi 6 mesi, dal più vecchio
    # al più recente. range(5, -1, -1) produce 5, 4, 3, 2, 1, 0 — il terzo
    # argomento -1 è il "passo" (si va all'indietro). Il ciclo while dentro
    # gestisce il caso in cui sottraendo mesi si scenda sotto gennaio: "m -=
    # 12" e "a -= 1" fanno tornare indietro di un anno, esattamente come
    # contare le ore oltre la mezzanotte.
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

    # "Sanificazione" degli input: qualcuno potrebbe mandare pagina=-5 o
    # per_pagina=99999 — questi due max()/min() garantiscono che i valori
    # restino sempre in un intervallo sensato, indipendentemente da cosa
    # arriva dal client.
    pagina = max(pagina, 1)
    per_pagina = min(max(per_pagina, 1), 100)

    query = db.query(Booking).join(User).join(Booking.slot)

    if stato:
        query = query.filter(Booking.status == stato)

    # .count() qui conta il TOTALE di righe che soddisfano il filtro,
    # PRIMA di applicare la paginazione — ci serve per calcolare quante
    # pagine esistono in tutto (vedi "pagine_totali" più sotto).
    totale = query.count()

    # .offset(...) salta le prime N righe, .limit(...) ne prende al massimo
    # M — è così che si implementa la paginazione: pagina 1 con 20 per
    # pagina salta 0 righe e ne prende 20; pagina 2 salta 20 righe e ne
    # prende altre 20, e così via. Il simbolo "\" a fine riga permette di
    # spezzare una singola istruzione Python su più righe per leggibilità,
    # senza che Python la consideri "finita" a metà.
    prenotazioni = query.order_by(Booking.created_at.desc()) \
        .offset((pagina - 1) * per_pagina) \
        .limit(per_pagina) \
        .all()

    risultato = []
    for p in prenotazioni:
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
                "data": utc_to_rome(p.slot.start_time).strftime("%d/%m/%Y"),
                "ora": utc_to_rome(p.slot.start_time).strftime("%H:%M")
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

    return {
        "items": risultato,
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        # Formula per arrotondare per eccesso una divisione intera, senza
        # usare numeri decimali: (totale + per_pagina - 1) // per_pagina.
        # L'operatore "//" è la divisione intera di Python (scarta la parte
        # decimale). Esempio: 25 prenotazioni, 20 per pagina → (25+19)//20 =
        # 44//20 = 2 pagine (la seconda con solo 5 elementi).
        "pagine_totali": max((totale + per_pagina - 1) // per_pagina, 1)
    }

# ─── AGGIORNA STATO PRENOTAZIONE ─────────────────────────────
@router.patch("/prenotazioni/{booking_id}/stato")
def aggiorna_stato(
    booking_id: int,
    nuovo_stato: str,
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
    stati_validi = ["confirmed", "cancelled", "no_show"]
    if nuovo_stato not in stati_validi:
        raise HTTPException(status_code=400, detail="Stato non valido")

    prenotazione = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()
    if not prenotazione:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    # A differenza del claim atomico in create_booking (backend/routers/booking.py),
    # qui una semplice assegnazione basta: questa è un'azione manuale del
    # coach, non c'è nessun rischio di "gara" tra richieste concorrenti
    # sullo stesso oggetto.
    prenotazione.status = nuovo_stato

    if nuovo_stato == "cancelled":
        # libera_slot_prenotazione (backend/services/booking_service.py)
        # gestisce sia lo slot singolo sia, per le sessioni da 2 ore che ne
        # avevano uniti due, anche lo slot secondario — stessa funzione
        # riusata dalla cancellazione self-service del cliente.
        libera_slot_prenotazione(prenotazione, db)

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
    db: Session = Depends(get_db),
    pagina: int = 1,
    per_pagina: int = 20
):
    """
    Restituisce i clienti, paginati, con il numero di sessioni
    effettuate e il totale speso. Le statistiche per cliente sono
    calcolate con query aggregate (GROUP BY), non con un ciclo
    Python che interroga il DB una volta per cliente (N+1).
    """
    # Il problema "N+1" che il commento sopra nomina è un classico errore
    # di prestazioni: se per ogni cliente (N clienti) facessimo una query
    # separata per contare le sue prenotazioni, otterremmo 1 query per la
    # lista clienti PIÙ N query aggiuntive (una per cliente) — con 100
    # clienti, 101 query invece di poche. La soluzione sotto fa UNA query
    # che raggruppa e conta tutto insieme, per tutti i clienti della pagina
    # contemporaneamente.
    pagina = max(pagina, 1)
    per_pagina = min(max(per_pagina, 1), 100)

    totale = db.query(User).count()

    clienti = db.query(User).order_by(User.id) \
        .offset((pagina - 1) * per_pagina) \
        .limit(per_pagina) \
        .all()

    id_clienti_pagina = [c.id for c in clienti]

    # .group_by(Booking.user_id) raggruppa tutte le prenotazioni per
    # cliente, e func.count(Booking.id) conta quante righe ci sono in ogni
    # gruppo — è l'equivalente SQL di "per ogni cliente, quante
    # prenotazioni ha". Il risultato è una lista di coppie (user_id,
    # conteggio); dict(...) la trasforma in un dizionario {user_id:
    # conteggio}, comodo da consultare subito dopo con .get(cliente.id).
    #
    # .filter(Booking.user_id.in_(id_clienti_pagina)) limita il calcolo
    # solo ai clienti della pagina corrente — non ha senso calcolare le
    # statistiche di TUTTI i clienti se ne stiamo mostrando solo 20.
    stats_prenotazioni = dict(
        db.query(
            Booking.user_id,
            func.count(Booking.id)
        ).filter(Booking.user_id.in_(id_clienti_pagina))
        .group_by(Booking.user_id).all()
    )
    spesa_prenotazioni = dict(
        db.query(
            Booking.user_id,
            func.sum(Booking.price_cents)
        ).filter(Booking.user_id.in_(id_clienti_pagina))
        .group_by(Booking.user_id).all()
    )
    conteggio_note = dict(
        db.query(
            ClientNote.user_id,
            func.count(ClientNote.id)
        ).filter(ClientNote.user_id.in_(id_clienti_pagina))
        .group_by(ClientNote.user_id).all()
    )

    risultato = [
        {
            "id": c.id,
            "nome": c.nome,
            "email": c.email,
            "categoria": c.categoria,
            "discord": c.discord_tag,
            "telefono": c.telefono,
            # .get(c.id, 0): se questo cliente non compare nel dizionario
            # (perché non ha nessuna prenotazione, quindi group_by non
            # produce nessuna riga per lui), il default 0 evita un errore.
            "sessioni_totali": stats_prenotazioni.get(c.id, 0),
            "totale_speso_euro": (spesa_prenotazioni.get(c.id, 0) or 0) / 100,
            "note_totali": conteggio_note.get(c.id, 0),
            "registrato_il": c.created_at.strftime("%d/%m/%Y")
        }
        for c in clienti
    ]

    return {
        "items": risultato,
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        "pagine_totali": max((totale + per_pagina - 1) // per_pagina, 1)
    }

# ─── NOTE TECNICHE CLIENTE (MINI-CRM) ────────────────────────
@router.get("/clienti/{user_id}/note", response_model=List[ClientNoteResponse])
def get_note_cliente(
    user_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Restituisce lo storico delle note tecniche di un cliente,
    in ordine cronologico (dalla più vecchia alla più recente).
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    return db.query(ClientNote).filter(
        ClientNote.user_id == user_id
    ).order_by(ClientNote.created_at.asc()).all()

@router.post("/clienti/{user_id}/note", response_model=ClientNoteResponse)
def crea_nota_cliente(
    user_id: int,
    nota: ClientNoteCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Aggiunge una nuova nota tecnica allo storico di un cliente
    (es. "Fatica a gestire i team Trick Room") — non sostituisce
    le note precedenti, si accumulano nel tempo.
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    # .strip() rimuove spazi bianchi/a-capo all'inizio e alla fine di una
    # stringa — una nota fatta solo di spazi non deve contare come "non
    # vuota".
    if not nota.nota.strip():
        raise HTTPException(status_code=400, detail="La nota non può essere vuota")

    db_nota = ClientNote(user_id=user_id, nota=nota.nota.strip())
    db.add(db_nota)
    db.commit()
    db.refresh(db_nota)
    return db_nota

# ─── GESTIONE SLOT ───────────────────────────────────────────
@router.get("/slots")
def get_slots_admin(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db),
    pagina: int = 1,
    per_pagina: int = 20
):
    """Restituisce gli slot, liberi e occupati, paginati (più vicini nel tempo prima)."""
    pagina = max(pagina, 1)
    per_pagina = min(max(per_pagina, 1), 100)

    totale = db.query(Slot).count()

    slots = db.query(Slot).order_by(Slot.start_time) \
        .offset((pagina - 1) * per_pagina) \
        .limit(per_pagina) \
        .all()

    items = [
        {
            "id": s.id,
            "data": utc_to_rome(s.start_time).strftime("%d/%m/%Y"),
            "ora": utc_to_rome(s.start_time).strftime("%H:%M"),
            "durata_ore": s.duration_hours,
            "disponibile": s.is_available,
            "bloccato_da_calendario": s.blocked_external,
            "bloccato_da_admin": s.blocked_admin
        }
        for s in slots
    ]

    return {
        "items": items,
        "totale": totale,
        "pagina": pagina,
        "per_pagina": per_pagina,
        "pagine_totali": max((totale + per_pagina - 1) // per_pagina, 1)
    }

@router.post("/slots/sync-calendario")
def sincronizza_calendario(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Legge il calendario Google del coach e blocca automaticamente
    (is_available=False, blocked_external=True) gli slot liberi che si
    sovrappongono a un evento esterno (torneo, stream, altro impegno).
    La logica vera vive in sincronizza_slot_con_calendario
    (backend/services/calendar_service.py), riusata anche dal job
    automatico periodico in backend/scheduler.py — questo endpoint resta
    per il bottone manuale nel pannello admin, comportamento identico a
    prima.
    """
    bloccati = sincronizza_slot_con_calendario(db)
    return {"slot_bloccati": bloccati}

# ─── DISPONIBILITÀ RICORRENTE ─────────────────────────────────
@router.get("/disponibilita/regole", response_model=List[AvailabilityRuleResponse])
def lista_regole_disponibilita(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce tutte le regole di disponibilità ricorrente."""
    return db.query(AvailabilityRule).order_by(
        AvailabilityRule.giorno_settimana, AvailabilityRule.ora_inizio
    ).all()

@router.post("/disponibilita/regole")
def crea_regola_disponibilita(
    regola: AvailabilityRuleCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea una regola di disponibilità ricorrente (es. "ogni martedì 18-22,
    slot da 1h") e genera subito gli slot corrispondenti fino alla fine
    del mese corrente, saltando quelli già esistenti allo stesso orario.
    """
    if regola.ora_fine <= regola.ora_inizio:
        raise HTTPException(status_code=400, detail="L'ora di fine deve essere successiva all'ora di inizio")

    db_regola = AvailabilityRule(
        giorno_settimana=regola.giorno_settimana,
        ora_inizio=regola.ora_inizio,
        ora_fine=regola.ora_fine,
        durata_slot_ore=regola.durata_slot_ore
    )
    db.add(db_regola)
    db.commit()
    db.refresh(db_regola)

    # Dopo aver salvato LA REGOLA, chiamiamo la funzione di
    # availability_service.py che genera DAVVERO gli slot concreti a
    # partire da essa — vedi i commenti dettagliati in quel file per capire
    # come funziona il calcolo.
    slot_creati = genera_slot_da_regola(db_regola, db)

    return {
        # AvailabilityRuleResponse.model_validate(db_regola) trasforma
        # manualmente l'oggetto SQLAlchemy in uno schema Pydantic — di
        # solito questo lo fa FastAPI da solo tramite response_model, ma
        # qui la risposta è un dizionario con DUE cose diverse dentro
        # (la regola e il conteggio degli slot creati), quindi va costruito
        # a mano invece di lasciare che FastAPI usi un response_model
        # singolo.
        "regola": AvailabilityRuleResponse.model_validate(db_regola),
        "slot_creati": slot_creati
    }

@router.delete("/disponibilita/regole/{regola_id}")
def elimina_regola_disponibilita(
    regola_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina una regola di disponibilità ricorrente. Non tocca gli slot
    già generati in passato — restano come slot normali indipendenti.
    """
    regola = db.query(AvailabilityRule).filter(AvailabilityRule.id == regola_id).first()
    if not regola:
        raise HTTPException(status_code=404, detail="Regola non trovata")

    db.delete(regola)
    db.commit()
    return {"message": "Regola eliminata"}

# ─── BLOCCHI ECCEZIONALI (FERIE, ECC.) ────────────────────────
@router.get("/disponibilita/blocchi", response_model=List[AvailabilityExceptionResponse])
def lista_blocchi_eccezionali(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce tutti i blocchi eccezionali (ferie, indisponibilità), più recenti prima."""
    return db.query(AvailabilityException).order_by(
        AvailabilityException.data_inizio.desc()
    ).all()

@router.post("/disponibilita/blocchi")
def crea_blocco_eccezionale(
    blocco: AvailabilityExceptionCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea un blocco eccezionale (es. ferie) su un periodo di date e marca
    subito come non disponibili gli slot liberi che ci cadono dentro.
    """
    if blocco.data_fine < blocco.data_inizio:
        raise HTTPException(status_code=400, detail="La data di fine deve essere successiva o uguale alla data di inizio")

    db_blocco = AvailabilityException(
        data_inizio=blocco.data_inizio,
        data_fine=blocco.data_fine,
        motivo=blocco.motivo
    )
    db.add(db_blocco)
    db.commit()
    db.refresh(db_blocco)

    slot_bloccati = applica_blocco_eccezionale(db_blocco, db)

    return {
        "blocco": AvailabilityExceptionResponse.model_validate(db_blocco),
        "slot_bloccati": slot_bloccati
    }

@router.delete("/disponibilita/blocchi/{blocco_id}")
def elimina_blocco_eccezionale(
    blocco_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un blocco eccezionale. Non riapre automaticamente gli slot
    che aveva bloccato — va fatto manualmente se necessario.
    """
    blocco = db.query(AvailabilityException).filter(AvailabilityException.id == blocco_id).first()
    if not blocco:
        raise HTTPException(status_code=404, detail="Blocco non trovato")

    db.delete(blocco)
    db.commit()
    return {"message": "Blocco eliminato"}

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
        # Perché non permettere comunque l'eliminazione? Perché slot_id in
        # Booking è una ForeignKey (vedi backend/models/booking.py): il
        # database stesso impedirebbe di eliminare uno slot ancora
        # referenziato da qualche prenotazione (per non lasciare
        # prenotazioni "orfane", che puntano a uno slot inesistente).
        # Controllarlo qui PRIMA di provare a cancellare permette di dare
        # un messaggio d'errore chiaro, invece di un errore tecnico del
        # database poco comprensibile.
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile eliminare: questo slot ha {prenotazioni_collegate} prenotazione/i collegate nello storico. Non può essere rimosso per preservare i dati."
        )

    db.delete(slot)
    db.commit()
    return {"message": "Slot eliminato"}

# ─── PACCHETTI SESSIONI ────────────────────────────────────────
# Il pagamento di un pacchetto avviene fuori dall'app (come per le
# prenotazioni singole): l'admin lo assegna qui SOLO dopo aver ricevuto il
# pagamento privatamente (es. su Discord), scegliendo uno dei 3 tipi fissi
# del catalogo (backend/services/package_service.py). Da quel momento il
# cliente vede il pacchetto attivo sul form pubblico (GET /pacchetti/attivi
# in backend/routers/users.py) e può spenderne le sessioni prenotando slot.
@router.get("/pacchetti", response_model=List[PackageResponse])
def lista_pacchetti(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Tutti i pacchetti assegnati, più recenti prima."""
    return db.query(Package).order_by(Package.created_at.desc()).all()

@router.post("/pacchetti", response_model=PackageResponse)
def crea_pacchetto(
    pacchetto: PackageCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Assegna a un cliente esistente un pacchetto del catalogo fisso.
    Sessioni totali, durata e prezzo NON arrivano dal client: vengono presi
    dal catalogo in base a "tipo", esattamente come TABELLA_PREZZI in
    backend/routers/booking.py per le prenotazioni singole.
    """
    utente = db.query(User).filter(User.id == pacchetto.user_id).first()
    if not utente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    dati_catalogo = CATALOGO_PACCHETTI[pacchetto.tipo]

    db_pacchetto = Package(
        user_id=pacchetto.user_id,
        tipo=pacchetto.tipo,
        sessioni_totali=dati_catalogo["sessioni_totali"],
        durata_sessione_ore=dati_catalogo["durata_sessione_ore"],
        prezzo_cents=dati_catalogo["prezzo_cents"]
    )
    db.add(db_pacchetto)
    db.commit()
    db.refresh(db_pacchetto)
    return db_pacchetto

# ─── RECENSIONI ──────────────────────────────────────────────
# Una recensione lasciata dal cliente (vedi POST /bookings/{id}/recensione
# in backend/routers/booking.py) non è subito pubblica: il coach la vede
# qui, e decide se approvarla prima che compaia nella vetrina pubblica
# (GET /bookings/recensioni/pubbliche, mostrata in frontend/about.html).
@router.get("/recensioni")
def lista_recensioni(
    approvata: Optional[bool] = None,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Tutte le recensioni, più recenti prima — con il contesto del cliente e
    della sessione, per aiutare il coach a decidere se approvarle.
    approvata=true/false filtra solo quelle già approvate/in attesa; senza
    il parametro le mostra tutte.
    """
    query = db.query(Review)
    if approvata is not None:
        query = query.filter(Review.approvata == approvata)

    recensioni = query.order_by(Review.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "voto": r.voto,
            "commento": r.commento,
            "approvata": r.approvata,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M"),
            "cliente": {
                "nome": r.booking.user.nome,
                "email": r.booking.user.email
            },
            "servizio": r.booking.service_type
        }
        for r in recensioni
    ]


@router.patch("/recensioni/{recensione_id}")
def approva_recensione(
    recensione_id: int,
    dati: ReviewApprovazione,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Approva (o ritira l'approvazione di) una recensione."""
    recensione = db.query(Review).filter(Review.id == recensione_id).first()
    if not recensione:
        raise HTTPException(status_code=404, detail="Recensione non trovata")

    recensione.approvata = dati.approvata
    db.commit()
    db.refresh(recensione)
    return recensione

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
    prenotazioni = db.query(Booking).join(User).join(Booking.slot).all()

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
        writer.writerow([
            p.id,
            p.status,
            p.user.nome,
            p.user.email,
            p.user.categoria or "",
            p.service_type,
            utc_to_rome(p.slot.start_time).strftime("%d/%m/%Y"),
            utc_to_rome(p.slot.start_time).strftime("%H:%M"),
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
