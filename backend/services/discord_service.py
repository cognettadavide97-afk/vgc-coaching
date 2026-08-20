# Questo file manda messaggi al canale Discord del coach usando un
# "webhook" — il modo più semplice per un programma di mandare messaggi in
# un canale Discord, SENZA dover creare e gestire un vero bot Discord (che
# richiederebbe login persistenti, gestione di eventi, ecc.). Un webhook è
# semplicemente un URL segreto: qualunque richiesta HTTP mandata a
# quell'indirizzo diventa un messaggio nel canale collegato.

import os
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Un piccolo dizionario che traduce i valori "tecnici" salvati nel database
# (es. "vod_review") in etichette leggibili da un umano (es. "VOD Review").
# .get(chiave, default) restituisce il valore "grazioso" se lo trova nel
# dizionario, altrimenti restituisce la chiave originale così com'è — non
# fallisce mai, anche se in futuro comparisse un valore non previsto qui.
SERVICE_LABELS = {
    "vod_review": "VOD Review",
    "team_building": "Team Building",
    "bo3_sparring": "Bo3 Sparring",
    "tournament_prep": "Tournament Prep"
}


def invia_notifica_discord(
    nome_cliente: str,
    discord_tag: str,
    service_type: str,
    data_slot: str,
    ora_slot: str,
    durata_ore: int,
    note_cliente: str = None
):
    """
    Invia una notifica sul canale Discord del coach (via webhook)
    a ogni nuova prenotazione. Non blocca la prenotazione in caso
    di errore o se il webhook non è configurato.
    """
    # Se il coach non ha ancora configurato un webhook (DISCORD_WEBHOOK_URL
    # mancante in .env), non ha senso nemmeno provare: usciamo subito dalla
    # funzione con "return" senza argomenti, che in una funzione che non
    # deve restituire nulla vuol dire semplicemente "fermati qui".
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL non configurato — salto notifica Discord")
        return

    servizio_label = SERVICE_LABELS.get(service_type, service_type)

    # "embed" è il formato che Discord usa per i messaggi con un aspetto più
    # curato (un riquadro colorato con titolo e campi separati, invece di
    # un semplice testo). Anche qui, come per Google Calendar, è "solo" un
    # dizionario con la struttura che Discord si aspetta — non c'è nessuna
    # libreria Discord coinvolta, mandiamo direttamente una richiesta HTTP.
    # 0xE74C3C è un numero scritto in esadecimale (il prefisso 0x lo dice a
    # Python): rappresenta un colore, lo stesso sistema usato nei codici
    # colore CSS (#E74C3C) che vedrai nel frontend.
    embed = {
        "title": "📅 Nuova prenotazione",
        "color": 0xE74C3C,
        "fields": [
            {"name": "Cliente", "value": nome_cliente, "inline": True},
            {"name": "Discord", "value": discord_tag or "non specificato", "inline": True},
            {"name": "Servizio", "value": servizio_label, "inline": True},
            {"name": "Data", "value": data_slot, "inline": True},
            {"name": "Orario", "value": ora_slot, "inline": True},
            {"name": "Durata", "value": f"{durata_ore} ora{'e' if durata_ore > 1 else ''}", "inline": True},
            {"name": "Note", "value": note_cliente or "nessuna", "inline": False},
        ]
    }

    try:
        # requests.post(url, json=..., timeout=5) manda una richiesta HTTP
        # POST con il nostro dizionario convertito automaticamente in JSON.
        # timeout=5 vuol dire "se Discord non risponde entro 5 secondi,
        # considera la richiesta fallita" — senza un timeout, un servizio
        # esterno lento potrebbe far restare il nostro programma "in attesa"
        # per un tempo indefinito, bloccando anche il resto della richiesta
        # di prenotazione in corso.
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        # raise_for_status() controlla il codice di risposta HTTP: se è un
        # codice di errore (4xx o 5xx), solleva un'eccezione da sola — così
        # non serve controllare manualmente "if response.status_code >= 400".
        response.raise_for_status()
        print("Notifica Discord inviata")
    except Exception as e:
        # Stessa filosofia di email_service.py e calendar_service.py: un
        # problema con Discord non deve mai bloccare la prenotazione,
        # quindi cattura l'errore e limitati a segnalarlo.
        print(f"Errore invio notifica Discord: {e}")


def invia_promemoria_discord(
    nome_cliente: str,
    discord_tag: str,
    data_slot: str,
    ora_slot: str
):
    """
    Avvisa il coach sul suo canale Discord che una sessione prenotata
    si avvicina. Non blocca nulla in caso di errore o webhook mancante.
    """
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL non configurato — salto promemoria Discord")
        return

    embed = {
        "title": "⏰ Promemoria sessione in arrivo",
        "color": 0xF39C12,
        "fields": [
            {"name": "Cliente", "value": nome_cliente, "inline": True},
            {"name": "Discord", "value": discord_tag or "non specificato", "inline": True},
            {"name": "Data", "value": data_slot, "inline": True},
            {"name": "Orario", "value": ora_slot, "inline": True},
        ]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        response.raise_for_status()
        print("Promemoria Discord inviato")
    except Exception as e:
        print(f"Errore invio promemoria Discord: {e}")


def invia_richiesta_consulenza_discord(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    messaggio: str = None
):
    """
    Avvisa il coach sul suo canale Discord di una richiesta di call
    conoscitiva gratuita (20 minuti) — vedi backend/routers/consulenza.py.
    A differenza di invia_notifica_discord, qui non c'è nessuno slot/data:
    l'orario va accordato privatamente col cliente dopo questo avviso.
    """
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL non configurato — salto notifica Discord")
        return

    embed = {
        "title": "🎁 Richiesta call gratuita (20 min)",
        "color": 0xF5C518,
        "fields": [
            {"name": "Cliente", "value": nome_cliente, "inline": True},
            {"name": "Email", "value": email_cliente, "inline": True},
            {"name": "Discord", "value": discord_tag or "non specificato", "inline": True},
            {"name": "Messaggio", "value": messaggio or "nessuno", "inline": False},
        ]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        response.raise_for_status()
        print("Notifica Discord richiesta consulenza inviata")
    except Exception as e:
        print(f"Errore invio notifica Discord richiesta consulenza: {e}")


def invia_richiesta_pacchetto_discord(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    nome_pacchetto: str,
    messaggio: str = None
):
    """
    Avvisa il coach sul suo canale Discord di una richiesta di attivazione
    pacchetto — vedi backend/routers/pacchetti_richieste.py. Nessun
    pagamento avviene qui: il pacchetto vero va assegnato a mano da
    /admin/pacchetti dopo aver ricevuto il pagamento.
    """
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL non configurato — salto notifica Discord")
        return

    embed = {
        "title": f"📦 Richiesta pacchetto — {nome_pacchetto}",
        "color": 0xF5C518,
        "fields": [
            {"name": "Cliente", "value": nome_cliente, "inline": True},
            {"name": "Email", "value": email_cliente, "inline": True},
            {"name": "Discord", "value": discord_tag or "non specificato", "inline": True},
            {"name": "Messaggio", "value": messaggio or "nessuno", "inline": False},
        ]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        response.raise_for_status()
        print("Notifica Discord richiesta pacchetto inviata")
    except Exception as e:
        print(f"Errore invio notifica Discord richiesta pacchetto: {e}")
