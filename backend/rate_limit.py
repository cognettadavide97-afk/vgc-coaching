# Questo file esiste per un motivo molto pratico, non solo organizzativo:
# evitare un "import circolare". Se main.py definisse il limiter e i router
# dovessero importarlo da main.py, e main.py a sua volta importasse i router,
# Python andrebbe in confusione (A ha bisogno di B che ha bisogno di A).
# La soluzione standard è mettere l'oggetto condiviso in un terzo file,
# piccolo e senza altre dipendenze, che sia sicuro importare da entrambe le
# parti. Questo pattern lo rivedrai spesso in progetti più grandi.

from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter è l'oggetto che, quando lo colleghi a un endpoint (lo vedrai nei
# router come decoratore: @limiter.limit("5/minute")), conta quante
# richieste arrivano e da chi, per bloccare chi ne manda troppe in poco
# tempo. key_func=get_remote_address dice "identifica chi sta chiamando in
# base al suo indirizzo IP" — è così che il limite è "5 richieste al minuto
# PER indirizzo IP", non 5 in totale per tutti gli utenti insieme.
limiter = Limiter(key_func=get_remote_address)
