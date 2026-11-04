"""Punto d'ingresso del bot GoldAI XAU.

Esecuzione: python -m src.main   (dalla cartella gold_ai_bot)
"""

from __future__ import annotations

import asyncio
import signal
import sys

# Assicura che la cartella del progetto sia nel path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.engine import TradingEngine
from src.utils.config import carica_config
from src.utils.logger import logger


async def main() -> None:
    cfg = carica_config("config.yaml")
    engine = TradingEngine(cfg)

    loop = asyncio.get_running_loop()

    def gestisci_segnale(_sig, _frame):
        logger.info("Segnale di interruzione ricevuto. Arresto...")
        asyncio.create_task(engine.ferma())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, gestisci_segnale)
        except NotImplementedError:
            # Windows: i signal handler non sono supportati su asyncio in questo modo
            signal.signal(sig, gestisci_segnale)

    try:
        await engine.avvia()
    except asyncio.CancelledError:
        pass
    finally:
        await engine.ferma()
        logger_bye = logger
        logger_bye.info("Uscita completata.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
