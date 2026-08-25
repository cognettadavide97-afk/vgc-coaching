# Questo è il primo file "schema" che leggi, quindi spieghiamo per bene la
# libreria Pydantic e il pattern Create/Response — negli altri file di
# questa cartella troverai la stessa logica, con meno ripetizioni.
#
# Uno "schema" Pydantic descrive la forma di un pezzo di JSON che entra o
# esce dall'API — è diverso da un "model" SQLAlchemy (che descrive una riga
# di database, vedi backend/models/): uno schema non tocca mai il database
# direttamente, serve solo a validare e formattare i dati che viaggiano
# nelle richieste/risposte HTTP.
#
# Il motivo per cui servono DUE classi (UserCreate e UserResponse) e non una
# sola: quello che il client MANDA per creare un utente (nome, email...) non
# è identico a quello che il server RESTITUISCE (che include anche id e
# created_at, generati dal database, che il client non può conoscere in
# anticipo). Tenerli separati evita ambiguità su "questo campo è
# obbligatorio in input o solo in output?".

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, Literal

Categoria = Literal["junior", "senior", "master"]


class UserCreate(BaseModel):
    """
    Descrive cosa deve mandare il client per creare un utente. Quando un
    endpoint FastAPI ha un parametro tipo "user: UserCreate", FastAPI legge
    da solo il corpo JSON della richiesta, controlla che abbia esattamente
    questi campi con questi tipi, e se qualcosa non torna risponde con un
    errore 422 automatico — senza che tu debba scrivere nessun "if" di
    validazione a mano.
    """
    nome: str

    # EmailStr non è un tipo Python standard: è un tipo speciale di Pydantic
    # che, oltre a richiedere una stringa, controlla anche che abbia la
    # forma di un indirizzo email valido (con la @, un dominio...). Se il
    # client manda "email": "non-e-una-email", Pydantic rifiuta la
    # richiesta prima ancora che il tuo codice la veda.
    email: EmailStr

    # Optional[str] = None vuol dire "questo campo può essere una stringa,
    # oppure può mancare del tutto (e in quel caso vale None)". È
    # l'equivalente Pydantic di un parametro di funzione con valore di
    # default in Python normale (def f(x=None)).
    telefono: Optional[str] = None
    categoria: Optional[Categoria] = None
    discord_tag: Optional[str] = None


class UserIdResponse(BaseModel):
    """
    Risposta "minima" di POST /users/ — vedi il commento su create_user in
    backend/routers/users.py per il perché: quell'endpoint è "get or
    create" pubblico, quindi se l'email indicata corrisponde a un cliente
    ESISTENTE, response_model=UserResponse (sotto) restituirebbe il suo
    profilo completo (nome, telefono, discord_tag) a chiunque conoscesse o
    indovinasse la sua email, anche dichiarando un nome diverso nella
    richiesta. Al client serve solo l'id per procedere con la prenotazione
    (vedi frontend/js/app.js), quindi è tutto quello che restituiamo.
    """
    id: int

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """
    Descrive cosa restituisce l'API quando parla di un utente. Include
    campi che UserCreate non ha (id, created_at) perché li genera il
    database, non il client.
    """
    id: int
    nome: str
    email: str
    telefono: Optional[str]
    categoria: Optional[str]
    discord_tag: Optional[str]
    created_at: datetime

    class Config:
        # from_attributes=True è quello che permette a questo schema di
        # essere costruito direttamente a partire da un OGGETTO Python
        # (come un'istanza del model User di SQLAlchemy), leggendo i suoi
        # attributi (utente.nome, utente.email...) invece che da un
        # dizionario. Senza questa opzione, dovresti convertire manualmente
        # ogni oggetto User in un dizionario prima di restituirlo — con
        # questa, un endpoint può fare semplicemente "return utente" e
        # FastAPI/Pydantic si occupano del resto.
        from_attributes = True
