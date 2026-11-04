"""Sistema di logging in italiano per il bot."""

import logging
import sys
from logging.handlers import RotatingFileHandler

_FORMATTER = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str, log_file: str = "logs/bot.log") -> logging.Logger:
    """Restituisce un logger configurato con output su console e file."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_FORMATTER)
    logger.addHandler(console_handler)

    # Handler file con rotazione
    try:
        import os
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(_FORMATTER)
        logger.addHandler(file_handler)
    except Exception:
        pass

    return logger


logger = get_logger("gold_ai_bot")
