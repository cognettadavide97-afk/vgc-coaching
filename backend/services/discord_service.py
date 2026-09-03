"""Notifiche verso il canale Discord del coach, tramite webhook.

Il webhook è un URL segreto su cui una semplice richiesta HTTP diventa un
messaggio nel canale: evita di dover registrare e mantenere un bot.

Nessuna funzione di questo modulo solleva eccezioni verso il chiamante: le
notifiche sono accessorie e un problema con Discord non deve mai far
fallire l'operazione che le ha generate.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

logger = logging.getLogger(__name__)

# Etichette leggibili per i valori salvati nel database. La lettura usa
# .get(chiave, chiave), quindi un servizio non previsto viene mostrato con
# il suo valore grezzo invece di sollevare un errore.
SERVICE_LABELS = {
    "vod_review": "VOD Review",
    "team_building": "Team Building",
    "bo3_sparring": "Bo3 Sparring",
    "tournament_prep": "Tournament Prep"
}


def _invia_embed(embed: dict, msg_ok: str, msg_errore: str):
    """Invia un embed al webhook. Punto unico di uscita verso Discord.

    Le funzioni pubbliche costruiscono solo il proprio embed: modifiche al
    trasporto (timeout, retry, formato) si fanno qui una volta sola.
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning(f"DISCORD_WEBHOOK_URL non configurato — salto: {msg_ok}")
        return

    try:
        # Il timeout è obbligatorio: questa chiamata avviene dentro la
        # richiesta di prenotazione, e senza limite un Discord lento la
        # terrebbe appesa a tempo indeterminato.
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        response.raise_for_status()
        logger.info(msg_ok)
    except Exception:
        logger.exception(msg_errore)


def invia_notifica_discord(
    nome_cliente: str,
    discord_tag: str,
    service_type: str,
    data_slot: str,
    ora_slot: str,
    durata_ore: int,
    note_cliente: str = None
):
    """Notifica il coach di una nuova prenotazione."""
    servizio_label = SERVICE_LABELS.get(service_type, service_type)

    # "embed" è il formato dei messaggi formattati di Discord; il colore è
    # un intero esadecimale, come i codici colore CSS.
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
    _invia_embed(embed, "Notifica Discord inviata", "Errore invio notifica Discord")


def invia_promemoria_discord(
    nome_cliente: str,
    discord_tag: str,
    data_slot: str,
    ora_slot: str
):
    """Notifica il coach che una sessione prenotata si avvicina."""
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
    _invia_embed(embed, "Promemoria Discord inviato", "Errore invio promemoria Discord")


def invia_richiesta_consulenza_discord(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    messaggio: str = None
):
    """Notifica il coach di una richiesta di call conoscitiva gratuita.

    Non esiste né slot né data: l'orario viene concordato privatamente
    dopo questo avviso.
    """
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
    _invia_embed(embed, "Notifica Discord richiesta consulenza inviata", "Errore invio notifica Discord richiesta consulenza")


def invia_alert_sistema(titolo: str, descrizione: str):
    """Avviso tecnico al coach su un problema che richiede un intervento.

    Usato per credenziali scadute o migrazioni fallite. Condivide il canale
    delle notifiche ordinarie, ma colore e icona lo rendono distinguibile.
    """
    embed = {
        "title": f"🚨 {titolo}",
        "description": descrizione,
        "color": 0xFF0000
    }
    _invia_embed(embed, f"Alert di sistema Discord inviato: {titolo}", "Errore invio alert di sistema Discord")


def invia_richiesta_pacchetto_discord(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    nome_pacchetto: str,
    messaggio: str = None
):
    """Notifica il coach di una richiesta di attivazione pacchetto.

    Nessun pagamento passa dall'applicazione: il pacchetto va assegnato a
    mano dal pannello dopo averlo incassato.
    """
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
    _invia_embed(embed, "Notifica Discord richiesta pacchetto inviata", "Errore invio notifica Discord richiesta pacchetto")
