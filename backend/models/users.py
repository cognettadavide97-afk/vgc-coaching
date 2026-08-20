# Questo è il primo model che leggi, quindi spieghiamo per bene il pattern
# generale — negli altri file di questa cartella troverai la stessa identica
# logica, con meno ripetizioni nei commenti.
#
# Un "model" SQLAlchemy è una normale classe Python che, invece di
# rappresentare "qualcosa" a caso, rappresenta UNA TABELLA del database.
# Ogni attributo di classe (le righe con "= Column(...)") diventa UNA
# COLONNA di quella tabella. Quando più avanti farai:
#
#     nuovo_utente = User(nome="Ash", email="ash@pokemon.com")
#
# non stai "solo" creando un oggetto Python in memoria: SQLAlchemy sa come
# trasformare quell'oggetto in una riga vera dentro la tabella "users" di
# MySQL, quando gli dirai di salvarlo (con db.add() + db.commit(), che vedrai
# nei file dei router). Questo meccanismo si chiama ORM — Object-Relational
# Mapping: fa da "traduttore" tra oggetti Python e righe di un database
# relazionale, così puoi lavorare con classi e oggetti invece che scrivere
# query SQL a mano.

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class User(Base):
    # Ereditare da Base (definita in backend/database.py) è quello che dice
    # a SQLAlchemy "questa classe è un model, tienine traccia".
    __tablename__ = "users"  # il nome vero della tabella dentro MySQL

    # Column(TIPO, opzioni...) definisce una colonna. I "tipi" (Integer,
    # String, DateTime...) sono gli stessi concetti che conosci da Python
    # (int, str, datetime), solo che qui dicono a SQLAlchemy che TIPO SQL
    # usare quando crea la tabella vera.
    #
    # primary_key=True vuol dire "questa colonna identifica in modo univoco
    # ogni riga" (è la "chiave primaria" della tabella — non possono
    # esistere due righe con lo stesso id). index=True dice al database di
    # costruire una struttura interna che rende le ricerche per id più
    # veloci (un "indice", un po' come l'indice di un libro).
    id = Column(Integer, primary_key=True, index=True)

    # String(100) vuol dire "testo, lungo al massimo 100 caratteri" — in SQL
    # diventa una colonna VARCHAR(100). nullable=False vuol dire "questo
    # campo è obbligatorio": se provi a salvare uno User senza nome, il
    # database rifiuta l'operazione.
    nome = Column(String(100), nullable=False)

    # unique=True aggiunge un vincolo: il database stesso impedisce che
    # esistano due righe con la stessa email, anche se per errore il codice
    # Python provasse a inserirle. È una protezione "a livello di dati", più
    # affidabile di un semplice controllo scritto a mano nel codice.
    email = Column(String(100), unique=True, nullable=False)

    # nullable=True (il default, ma qui esplicito) vuol dire "questo campo è
    # opzionale" — un utente può non avere il telefono, va bene lo stesso.
    telefono = Column(String(20), nullable=True)
    # junior / senior / master — sostituisce il vecchio campo showdown_username:
    # per la valutazione del percorso di coaching conta di più la fascia di
    # esperienza del cliente che il suo username sulla piattaforma di gioco.
    categoria = Column(String(20), nullable=True)
    discord_tag = Column(String(100), nullable=True)

    # discord_id è diverso da discord_tag: è l'identificativo numerico
    # permanente che Discord assegna a ogni account (non cambia mai, a
    # differenza del "tag" che l'utente può cambiare). Viene popolato solo
    # se lo studente fa login con Discord (vedi backend/routers/discord_auth.py);
    # per chi prenota come ospite resta vuoto (nullable=True).
    discord_id = Column(String(30), nullable=True, unique=True)

    # func.now() non calcola la data "adesso" quando Python legge questa
    # riga (che viene eseguita una sola volta, all'avvio del programma) —
    # dice invece a SQLAlchemy "ogni volta che inserisci una nuova riga, se
    # non specifichi created_at, chiedi al database di mettere la sua ora
    # attuale". Il calcolo lo fa MySQL stesso al momento del salvataggio,
    # non Python.
    created_at = Column(DateTime, default=func.now())
