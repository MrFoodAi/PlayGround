"""Notifiche opzionali (Telegram) in italiano."""

from typing import Optional

import requests


class Notifiche:
    """Invia notifiche tramite Telegram (opzionale)."""

    def __init__(self, token: Optional[str], chat_id: Optional[str], attive: bool):
        self.token = token
        self.chat_id = chat_id
        self.attive = attive and bool(token) and bool(chat_id)

    def invia(self, messaggio: str) -> None:
        if not self.attive:
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": messaggio,
                "parse_mode": "HTML",
            }
            requests.post(url, json=payload, timeout=10)
        except Exception:
            # Non bloccare il bot per una notifica fallita
            pass
