"""Motore AI autonomo per segnali di trading su XAU.

Combina:
1. Analisi tecnica (RSI, MACD, Bollinger, SMA).
2. Modello ML (Random Forest) addestrato sullo storico simulato/reale.
3. (Opzionale) LLM per rationale testuale.

Output: segnale "BUY" / "SELL" / "HOLD" con confidenza [0,1].
"""

from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from typing import Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.data.feed import Indicatori
from src.utils.logger import logger


@dataclass
class Segnale:
    azione: str          # "BUY", "SELL", "HOLD"
    confidenza: float    # 0.0 - 1.0
    prezzo: float
    motivo: str          # descrizione in italiano
    indicatori: dict


class ModelloML:
    """Modello Random Forest per classificare la direzione del prossimo periodo."""

    FEATURE_COLS = [
        "rsi", "macd", "macd_segnale", "macd_istogramma",
        "sma_breve", "sma_lungo", "bb_media", "bb_superiore", "bb_inferiore",
        "ritorno_1", "ritorno_3", "volatilita",
    ]

    def __init__(self, percorso_modello: str = "models/ai_model.pkl"):
        self.percorso_modello = percorso_modello
        self.modello: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.istruito = False
        self._carica_se_esiste()

    # ------------------------------------------------------------------ #
    # Caricamento / salvataggio
    # ------------------------------------------------------------------ #
    def _carica_se_esiste(self) -> None:
        if os.path.exists(self.percorso_modello):
            try:
                dati = joblib.load(self.percorso_modello)
                self.modello = dati["modello"]
                self.scaler = dati["scaler"]
                self.istruito = True
                logger.info("Modello ML caricato da disco.")
            except Exception as exc:
                logger.warning(f"Impossibile caricare modello ({exc}). Ne verrà creato uno nuovo.")

    def salva(self) -> None:
        os.makedirs(os.path.dirname(self.percorso_modello), exist_ok=True)
        joblib.dump({"modello": self.modello, "scaler": self.scaler}, self.percorso_modello)
        logger.info("Modello ML salvato su disco.")

    # ------------------------------------------------------------------ #
    # Preparazione feature
    # ------------------------------------------------------------------ #
    @staticmethod
    def _feature(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ritorno_1"] = df["chiusura"].pct_change(1)
        df["ritorno_3"] = df["chiusura"].pct_change(3)
        df["volatilita"] = df["chiusura"].rolling(5).std()
        return df

    @staticmethod
    def _target(df: pd.DataFrame, orizzonte: int = 3) -> pd.Series:
        """Target: 1 se il prezzo sale entro `orizzonte` candele, 0 altrimenti."""
        futuro = df["chiusura"].shift(-orizzonte)
        return (futuro > df["chiusura"]).astype(int)

    # ------------------------------------------------------------------ #
    # Addestramento
    # ------------------------------------------------------------------ #
    def istruisciti(self, df: pd.DataFrame) -> dict:
        """Addestra il modello sullo storico disponibile. Restituisce metriche."""
        df = Indicatori.completa(df, {})
        df = self._feature(df)
        df = df.dropna()

        if len(df) < 100:
            logger.warning("Storico insufficiente per addestrare il modello ML.")
            return {"stato": "insufficiente", "righe": len(df)}

        X = df[self.FEATURE_COLS].values
        y = self._target(df).values[:-3]  # allineamento con lo shift
        X = X[:-3]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False, random_state=42
        )

        self.scaler = StandardScaler()
        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s = self.scaler.transform(X_test)

        self.modello = RandomForestClassifier(
            n_estimators=200, max_depth=10, random_state=42, class_weight="balanced"
        )
        self.modello.fit(X_train_s, y_train)

        acc = float(self.modello.score(X_test_s, y_test))
        self.istruito = True
        self.salva()
        logger.info(f"Modello ML addestrato. Accuratezza test: {acc:.2%}")
        return {"stato": "istruito", "accuratezza": acc, "righe": len(df)}

    # ------------------------------------------------------------------ #
    # Predizione
    # ------------------------------------------------------------------ #
    def prevedi(self, df: pd.DataFrame) -> Tuple[Optional[int], Optional[float]]:
        """Restituisce (classe_predetta, probabilita_massima) o (None, None)."""
        if not self.istruito or self.modello is None or self.scaler is None:
            return None, None
        df = Indicatori.completa(df, {})
        df = self._feature(df)
        ultima = df.iloc[-1:]
        if ultima[self.FEATURE_COLS].isna().any().any():
            return None, None
        X = self.scaler.transform(ultima[self.FEATURE_COLS].values)
        classe = int(self.modello.predict(X)[0])
        proba = float(max(self.modello.predict_proba(X)[0]))
        return classe, proba


class MotoreAI:
    """Orchestra analisi tecnica + ML + (opzionale) LLM per generare segnali."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        ai_cfg = cfg.get("ai", {})
        self.soglia = float(ai_cfg.get("soglia_confidenza_minima", 0.65))
        self.attivo = bool(ai_cfg.get("attivo", True))
        self.modello = ModelloML()
        self.usa_llm = bool(ai_cfg.get("usa_llm", False))

    def istruisciti(self, df: pd.DataFrame) -> dict:
        return self.modello.istruisciti(df)

    def genera_segnale(self, df: pd.DataFrame, prezzo: float) -> Segnale:
        """Genera il segnale di trading corrente."""
        ind_cfg = self.cfg.get("indicatori_tecnici", {})
        df = Indicatori.completa(df, ind_cfg)
        ultima = df.iloc[-1]

        rsi = float(ultima["rsi"]) if pd.notna(ultima["rsi"]) else 50.0
        macd = float(ultima["macd"]) if pd.notna(ultima["macd"]) else 0.0
        macd_sig = float(ultima["macd_segnale"]) if pd.notna(ultima["macd_segnale"]) else 0.0
        sma_b = float(ultima["sma_breve"]) if pd.notna(ultima["sma_breve"]) else prezzo
        sma_l = float(ultima["sma_lungo"]) if pd.notna(ultima["sma_lungo"]) else prezzo
        bb_inf = float(ultima["bb_inferiore"]) if pd.notna(ultima["bb_inferiore"]) else prezzo
        bb_sup = float(ultima["bb_superiore"]) if pd.notna(ultima["bb_superiore"]) else prezzo

        # --- Analisi tecnica (punteggio da -1 a +1) ---
        punteggio = 0.0
        motivi: list[str] = []

        if rsi < ind_cfg.get("rsi_sovravenduto", 30):
            punteggio += 0.3
            motivi.append(f"RSI in ipervenduto ({rsi:.1f})")
        elif rsi > ind_cfg.get("rsi_sovraacquisto", 70):
            punteggio -= 0.3
            motivi.append(f"RSI in ipercomprato ({rsi:.1f})")

        if macd > macd_sig:
            punteggio += 0.2
            motivi.append("MACD sopra segnale")
        else:
            punteggio -= 0.2
            motivi.append("MACD sotto segnale")

        if prezzo > sma_b > sma_l:
            punteggio += 0.2
            motivi.append("Prezzo sopra SMA breve e lunga (trend rialzista)")
        elif prezzo < sma_b < sma_l:
            punteggio -= 0.2
            motivi.append("Prezzo sotto SMA breve e lunga (trend ribassista)")

        if prezzo <= bb_inf:
            punteggio += 0.2
            motivi.append("Prezzo sul bordo inferiore di Bollinger")
        elif prezzo >= bb_sup:
            punteggio -= 0.2
            motivi.append("Prezzo sul bordo superiore di Bollinger")

        # --- Predizione ML ---
        peso_ml = 0.4
        voto_ml = 0
        confidenza_ml = 0.5
        if self.attivo:
            classe, proba = self.modello.prevedi(df)
            if classe is not None:
                voto_ml = 1 if classe == 1 else -1
                confidenza_ml = proba
                punteggio += voto_ml * peso_ml
                motivi.append(f"ML prevede {'rialzo' if classe == 1 else 'ribasso'} (conf {proba:.0%})")

        # --- Decisione finale ---
        azione = "HOLD"
        confidenza = abs(punteggio)
        if punteggio >= self.soglia:
            azione = "BUY"
        elif punteggio <= -self.soglia:
            azione = "SELL"

        # Se la confidenza e' troppo bassa, forza HOLD
        if confidenza < self.soglia:
            azione = "HOLD"

        motivo_txt = "; ".join(motivi) if motivi else "Nessun segnale significativo"
        if self.usa_llm:
            motivo_txt += " | [LLM disattivato o senza chiave]"

        return Segnale(
            azione=azione,
            confidenza=round(min(confidenza, 1.0), 3),
            prezzo=round(prezzo, 2),
            motivo=motivo_txt,
            indicatori={
                "rsi": round(rsi, 2),
                "macd": round(macd, 4),
                "sma_breve": round(sma_b, 2),
                "sma_lungo": round(sma_l, 2),
            },
        )
