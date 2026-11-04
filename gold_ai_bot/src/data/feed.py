"""Feed di prezzi e indicatori tecnici per XAU/USD.

Fonti supportate: coingecko (gratuito), binance (CCXT), mock (simulazione).
Tutti i prezzi sono in USD per oncia d'oro (XAU/USD).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from src.utils.logger import logger


@dataclass
class Candela:
    """Singola candela OHLCV."""
    timestamp: int
    apertura: float
    massimo: float
    minimo: float
    chiusura: float
    volume: float


class FeedPrezzi:
    """Fornisce lo storico e il prezzo attuale di XAU/USD."""

    def __init__(self, fonte: str = "mock", simbolo: str = "XAU/USD"):
        self.fonte = fonte
        self.simbolo = simbolo
        self._ultimo_prezzo: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Prezzo attuale
    # ------------------------------------------------------------------ #
    def prezzo_attuale(self) -> float:
        """Restituisce l'ultimo prezzo noto (USD/oncia)."""
        if self._ultimo_prezzo is not None:
            return self._ultimo_prezzo
        prezzo = self._recupera_prezzo()
        self._ultimo_prezzo = prezzo
        return prezzo

    def _recupera_prezzo(self) -> float:
        if self.fonte == "coingecko":
            return self._da_coingecko()
        if self.fonte == "binance":
            return self._da_binance()
        # mock: prezzo intorno a 2000-2400 USD/oncia con piccola variazione
        base = 2150.0
        return round(base + random.uniform(-30, 30), 2)

    def _da_coingecko(self) -> float:
        import requests

        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "tether-gold", "vs_currencies": "usd"}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            dati = r.json()
            prezzo = dati["tether-gold"]["usd"]
            self._ultimo_prezzo = float(prezzo)
            return self._ultimo_prezzo
        except Exception as exc:
            logger.warning(f"Coingecko non disponibile ({exc}), uso mock.")
            return self._da_mock()

    def _da_binance(self) -> float:
        try:
            import ccxt

            exchange = ccxt.binance({"enableRateLimit": True})
            ticker = exchange.fetch_ticker("XAU/USDT")
            prezzo = float(ticker["last"])
            self._ultimo_prezzo = prezzo
            return prezzo
        except Exception as exc:
            logger.warning(f"Binance non disponibile ({exc}), uso mock.")
            return self._da_mock()

    def _da_mock(self) -> float:
        base = 2150.0
        prezzo = round(base + random.uniform(-40, 40), 2)
        self._ultimo_prezzo = prezzo
        return prezzo

    # ------------------------------------------------------------------ #
    # Storico candele
    # ------------------------------------------------------------------ #
    def storico(self, n_candele: int = 500, timeframe: str = "15m") -> pd.DataFrame:
        """Restituisce uno storico di candele (DataFrame con colonne OHLCV)."""
        if self.fonte == "binance":
            df = self._storico_binance(n_candele, timeframe)
            if df is not None and not df.empty:
                return df
        # fallback: storico simulato realistico
        return self._storico_mock(n_candele)

    def _storico_binance(self, n_candele: int, timeframe: str) -> Optional[pd.DataFrame]:
        try:
            import ccxt

            exchange = ccxt.binance({"enableRateLimit": True})
            ohlcv = exchange.fetch_ohlcv("XAU/USDT", timeframe=timeframe, limit=n_candele)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "apertura", "massimo", "minimo", "chiusura", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as exc:
            logger.warning(f"Storico binance fallito ({exc}), uso mock.")
            return None

    def _storico_mock(self, n_candele: int) -> pd.DataFrame:
        """Genera uno storico realistico con random walk + tendenza."""
        ora = int(time.time())
        passo_secondi = 900  # 15 minuti
        prezzo = 2150.0
        righe: List[dict] = []
        for i in range(n_candele):
            ts = ora - (n_candele - i) * passo_secondi
            variazione = random.gauss(0, 8)
            prezzo += variazione
            apertura = prezzo
            massimo = max(apertura, prezzo) + random.uniform(0, 5)
            minimo = min(apertura, prezzo) - random.uniform(0, 5)
            chiusura = prezzo + random.uniform(-4, 4)
            volume = random.uniform(100, 1000)
            righe.append(
                {
                    "timestamp": pd.to_datetime(ts, unit="s"),
                    "apertura": round(apertura, 2),
                    "massimo": round(massimo, 2),
                    "minimo": round(minimo, 2),
                    "chiusura": round(chiusura, 2),
                    "volume": round(volume, 2),
                }
            )
            prezzo = chiusura
        return pd.DataFrame(righe)


# ========================================================================= #
# Indicatori tecnici
# ========================================================================= #


class Indicatori:
    """Calcola indicatori tecnici su un DataFrame OHLCV."""

    @staticmethod
    def rsi(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
        delta = df["chiusura"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(periodo).mean()
        avg_loss = loss.rolling(periodo).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(
        df: pd.DataFrame, veloce: int = 12, lento: int = 26, segnale: int = 9
    ) -> dict:
        ema_veloce = df["chiusura"].ewm(span=veloce, adjust=False).mean()
        ema_lento = df["chiusura"].ewm(span=lento, adjust=False).mean()
        macd_line = ema_veloce - ema_lento
        segnale_line = macd_line.ewm(span=segnale, adjust=False).mean()
        istogramma = macd_line - segnale_line
        return {"macd": macd_line, "segnale": segnale_line, "istogramma": istogramma}

    @staticmethod
    def sma(df: pd.DataFrame, periodo: int) -> pd.Series:
        return df["chiusura"].rolling(periodo).mean()

    @staticmethod
    def bollinger(df: pd.DataFrame, periodo: int = 20, deviazioni: float = 2.0) -> dict:
        media = df["chiusura"].rolling(periodo).mean()
        std = df["chiusura"].rolling(periodo).std()
        return {
            "media": media,
            "superiore": media + deviazioni * std,
            "inferiore": media - deviazioni * std,
        }

    @staticmethod
    def completa(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
        """Aggiunge tutti gli indicatori al DataFrame."""
        ind = cfg.get("indicatori_tecnici", {})
        df = df.copy()
        df["rsi"] = Indicatori.rsi(df, ind.get("rsi_periodo", 14))

        macd = Indicatori.macd(
            df,
            ind.get("macd_veloce", 12),
            ind.get("macd_lento", 26),
            ind.get("macd_segnale", 9),
        )
        df["macd"] = macd["macd"]
        df["macd_segnale"] = macd["segnale"]
        df["macd_istogramma"] = macd["istogramma"]

        df["sma_breve"] = Indicatori.sma(df, ind.get("sma_breve", 20))
        df["sma_lungo"] = Indicatori.sma(df, ind.get("sma_lungo", 50))

        bb = Indicatori.bollinger(
            df, ind.get("bollinger_periodo", 20), ind.get("bollinger_deviazioni", 2.0)
        )
        df["bb_media"] = bb["media"]
        df["bb_superiore"] = bb["superiore"]
        df["bb_inferiore"] = bb["inferiore"]

        return df
