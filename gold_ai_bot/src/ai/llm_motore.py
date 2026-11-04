"""Motore LLM gratuito specializzato in analisi trading oro (XAU/USD) e DeFi.

Provider supportati (gratuiti):
- Ollama (locale, gratuito, richiede Ollama installato: https://ollama.ai)
- HuggingFace Inference API (tier gratuito, richiede API key HF)
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any

import requests

from src.utils.logger import logger


class LLMManager:
    """Interfaccia a modelli LLM gratuiti per analisi tecnica specializzata su oro."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        ai_cfg = cfg.get("ai", {})
        self.attivo = bool(ai_cfg.get("usa_llm", False))
        self.provider = ai_cfg.get("llm_provider", "ollama")  # ollama | hf | disabled
        self.modello = ai_cfg.get("llm_modello", "llama3")
        self.endpoint = ai_cfg.get("llm_endpoint", "http://localhost:11434")
        self.api_key = ai_cfg.get("llm_api_key") or ""
        self.timeout = int(ai_cfg.get("llm_timeout_secondi", 30))

    def disponibile(self) -> bool:
        """Verifica se il provider LLM è raggiungibile/configurato."""
        if not self.attivo or self.provider == "disabled":
            return False
        if self.provider == "ollama":
            try:
                r = requests.get(f"{self.endpoint}/api/tags", timeout=5)
                return r.status_code == 200
            except Exception:
                return False
        if self.provider == "hf":
            return bool(self.api_key)
        return False

    def chiedi_segnale(self, dati_tecnici: dict) -> Optional[dict]:
        """
        Chiede al LLM un parere sul segnale di trading.
        Ritorna un dizionario con segnale, confidenza, motivo, rischio oppure None.
        """
        if not self.disponibile():
            return None

        prompt = self._costruisci_prompt(dati_tecnici)

        try:
            if self.provider == "ollama":
                return self._chiedi_ollama(prompt)
            if self.provider == "hf":
                return self._chiedi_hf(prompt)
        except Exception as exc:
            logger.warning(f"LLM non disponibile ({exc}), uso solo analisi tecnica.")

        return None

    # ------------------------------------------------------------------ #
    # Prompt specializzato oro / trading
    # ------------------------------------------------------------------ #
    def _costruisci_prompt(self, d: dict) -> str:
        return f"""
Sei un analista finanziario esperto specializzato in oro (XAU/USD) e asset tokenizzati DeFi.
Analizza i dati tecnici e rispondi ESCLUSIVAMENTE con un oggetto JSON valido, senza testo extra.

Campi richiesti:
- segnale: "BUY", "SELL" o "HOLD"
- confidenza: numero intero 0-100
- motivo: stringa breve in italiano (max 200 caratteri)
- rischio: "BASSO", "MEDIO" o "ALTO"

Dati tecnici:
- Prezzo XAU/USD: {d.get('prezzo', 0)} USD/oncia
- RSI (14): {d.get('rsi', 50)}
- MACD: {d.get('macd', 0)}
- Segnale MACD: {d.get('macd_segnale', 0)}
- SMA breve (20): {d.get('sma_breve', 0)}
- SMA lunga (50): {d.get('sma_lungo', 0)}
- Bollinger inferiore: {d.get('bb_inferiore', 0)}
- Bollinger superiore: {d.get('bb_superiore', 0)}
- Trend rilevato: {d.get('trend', 'laterale')}

Regole:
1. Se RSI > 70 e prezzo vicino a Bollinger superiore → tendenzialmente SELL.
2. Se RSI < 30 e prezzo vicino a Bollinger inferiore → tendenzialmente BUY.
3. Se i segnali sono contrastanti → HOLD.
4. Non fornire consigli finanziari diretti; questa è solo analisi tecnica di supporto.
5. Rispondi solo con JSON.
"""

    # ------------------------------------------------------------------ #
    # Provider Ollama (locale, gratuito)
    # ------------------------------------------------------------------ #
    def _chiedi_ollama(self, prompt: str) -> Optional[dict]:
        payload = {
            "model": self.modello,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        r = requests.post(f"{self.endpoint}/api/generate", json=payload, timeout=self.timeout)
        r.raise_for_status()
        testo = r.json().get("response", "")
        return self._parsi_json(testo)

    # ------------------------------------------------------------------ #
    # Provider HuggingFace Inference API (tier gratuito)
    # ------------------------------------------------------------------ #
    def _chiedi_hf(self, prompt: str) -> Optional[dict]:
        url = f"https://api-inference.huggingface.co/models/{self.modello}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 300, "temperature": 0.3},
        }
        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()
        dati = r.json()
        testo = dati[0].get("generated_text", "") if isinstance(dati, list) else str(dati)
        return self._parsi_json(testo)

    @staticmethod
    def _parsi_json(testo: str) -> Optional[dict]:
        try:
            inizio = testo.find("{")
            fine = testo.rfind("}") + 1
            if inizio == -1 or fine == 0:
                return None
            obj = json.loads(testo[inizio:fine])
            return {
                "segnale": str(obj.get("segnale", "HOLD")).upper(),
                "confidenza": int(obj.get("confidenza", 50)),
                "motivo": str(obj.get("motivo", ""))[:200],
                "rischio": str(obj.get("rischio", "MEDIO")).upper(),
            }
        except Exception:
            return None


def conferma_con_llm(segnale_tecnico: str, parere_llm: Optional[dict]) -> bool:
    """
    Restituisce True se il LLM conferma il segnale tecnico.
    Blocca se LLM dice HOLD, direzione opposta, o rischio ALTO.
    """
    if parere_llm is None:
        return True  # se LLM non disponibile, lascia decidere al tecnico

    direzione_llm = parere_llm.get("segnale", "HOLD")
    rischio = parere_llm.get("rischio", "MEDIO")

    if direzione_llm == "HOLD":
        logger.info(f"LLM ha rigettato il segnale (HOLD): {parere_llm.get('motivo', '')}")
        return False

    if direzione_llm != segnale_tecnico:
        logger.info(
            f"LLM in disaccordo: tecnico={segnale_tecnico}, LLM={direzione_llm} "
            f"({parere_llm.get('motivo', '')})"
        )
        return False

    if rischio == "ALTO":
        logger.info(f"LLM segnala rischio ALTO, operazione bloccata: {parere_llm.get('motivo', '')}")
        return False

    logger.info(f"LLM conferma {segnale_tecnico} (conf {parere_llm.get('confidenza', 0)}%).")
    return True
