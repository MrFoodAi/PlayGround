"""Utilita per caricamento configurazione e variabili d'ambiente."""

import os
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


def carica_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Carica il file YAML di configurazione sostituendo le variabili ${VAR}."""
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        testo = f.read()

    # Sostituzione variabili d'ambiente ${VAR}
    import re

    def _sostituisci(match):
        var = match.group(1)
        return os.getenv(var, match.group(0))

    testo = re.sub(r"\$\{([A-Za-z0-9_]+)\}", _sostituisci, testo)
    return yaml.safe_load(testo)


def get(cfg: Dict[str, Any], percorso: str, default: Any = None) -> Any:
    """Accede a un valore annidato con notazione a punti, es. trading.asset_principale."""
    chiavi = percorso.split(".")
    nodo: Any = cfg
    for chiave in chiavi:
        if isinstance(nodo, dict) and chiave in nodo:
            nodo = nodo[chiave]
        else:
            return default
    return nodo
