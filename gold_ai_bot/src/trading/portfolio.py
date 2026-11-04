"""Tracciamento posizioni e portafoglio (aperte e chiuse)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.utils.logger import logger

MAX_POSIZIONI_CONCORRENTI = 5


@dataclass
class Posizione:
    id: str
    asset: str
    direzione: str          # "LONG" o "SHORT"
    importo_usd: float
    quantita_asset: float
    prezzo_apertura: float
    stop_loss: float
    take_profit: float
    prezzo_corrente: float
    aperta_a: float         # timestamp
    chiusa_a: Optional[float] = None
    pnl_usd: float = 0.0
    vincente: Optional[bool] = None
    chiusa: bool = False


class Portafoglio:
    """Gestisce le posizioni aperte e lo storico dei trade chiusi."""

    def __init__(self, capitale_iniziale_usd: float):
        self.capitale_iniziale_usd = capitale_iniziale_usd
        self.disponibile_usd = capitale_iniziale_usd
        self.posizioni_aperte: Dict[str, Posizione] = {}
        self.storico: List[Posizione] = []
        self._contatore_id = 0

    def prossimo_id(self) -> str:
        self._contatore_id += 1
        return f"POS-{self._contatore_id:06d}"

    def apri(
        self,
        asset: str,
        direzione: str,
        importo_usd: float,
        quantita_asset: float,
        prezzo: float,
        stop_loss: float,
        take_profit: float,
    ) -> Optional[Posizione]:
        if len(self.posizioni_aperte) >= MAX_POSIZIONI_CONCORRENTI:
            logger.warning("Numero massimo di posizioni concorrenti raggiunto.")
            return None
        if importo_usd > self.disponibile_usd:
            logger.warning(f"Capitale insufficiente: disponibile {self.disponibile_usd:.2f} USD.")
            return None

        posizione = Posizione(
            id=self.prossimo_id(),
            asset=asset,
            direzione=direzione,
            importo_usd=importo_usd,
            quantita_asset=quantita_asset,
            prezzo_apertura=prezzo,
            stop_loss=stop_loss,
            take_profit=take_profit,
            prezzo_corrente=prezzo,
            aperta_a=time.time(),
        )
        self.posizioni_aperte[posizione.id] = posizione
        self.disponibile_usd -= importo_usd
        logger.info(
            f"Posizione APERTA {posizione.id}: {direzione} {asset} "
            f"{importo_usd:.2f} USD @ {prezzo:.2f} (SL {stop_loss:.2f}, TP {take_profit:.2f})"
        )
        return posizione

    def aggiorna_prezzi(self, prezzo: float) -> List[Posizione]:
        """Aggiorna il prezzo corrente di tutte le posizioni aperte."""
        chiuse: List[Posizione] = []
        for posizione in self.posizioni_aperte.values():
            posizione.prezzo_corrente = prezzo
            # Calcolo PnL non realizzato
            if posizione.direzione == "LONG":
                posizione.pnl_usd = (prezzo - posizione.prezzo_apertura) / posizione.prezzo_apertura * posizione.importo_usd
            else:
                posizione.pnl_usd = (posizione.prezzo_apertura - prezzo) / posizione.prezzo_apertura * posizione.importo_usd
        return chiuse

    def chiudi(self, posizione_id: str, prezzo_chiusura: float, motivo: str) -> Optional[Posizione]:
        """Chiude una posizione aperta e la sposta nello storico."""
        posizione = self.posizioni_aperte.pop(posizione_id, None)
        if posizione is None:
            return None

        posizione.chiusa = True
        posizione.chiusa_a = time.time()
        posizione.prezzo_corrente = prezzo_chiusura
        if posizione.direzione == "LONG":
            posizione.pnl_usd = (prezzo_chiusura - posizione.prezzo_apertura) / posizione.prezzo_apertura * posizione.importo_usd
        else:
            posizione.pnl_usd = (posizione.prezzo_apertura - prezzo_chiusura) / posizione.prezzo_apertura * posizione.importo_usd
        posizione.vincente = posizione.pnl_usd > 0

        self.disponibile_usd += posizione.importo_usd + posizione.pnl_usd
        self.storico.append(posizione)
        logger.info(
            f"Posizione CHIUSA {posizione.id}: {posizione.direzione} @ {prezzo_chiusura:.2f} "
            f"PnL {posizione.pnl_usd:+.2f} USD ({motivo})"
        )
        return posizione

    def controlla_stop_take(self, prezzo: float) -> List[Posizione]:
        """Ritorna le posizioni da chiudere per stop loss / take profit."""
        da_chiudere: List[Posizione] = []
        for posizione in list(self.posizioni_aperte.values()):
            motivo = None
            if posizione.direzione == "LONG":
                if prezzo <= posizione.stop_loss:
                    motivo = "Stop Loss"
                elif prezzo >= posizione.take_profit:
                    motivo = "Take Profit"
            else:  # SHORT
                if prezzo >= posizione.stop_loss:
                    motivo = "Stop Loss"
                elif prezzo <= posizione.take_profit:
                    motivo = "Take Profit"
            if motivo:
                da_chiudere.append((posizione, motivo))
        return [(p, m) for p, m in da_chiudere]

    def totale_pnl(self) -> float:
        """PnL totale (realizzato + non realizzato)."""
        realizzato = sum(p.pnl_usd for p in self.storico)
        non_realizzato = sum(p.pnl_usd for p in self.posizioni_aperte.values())
        return round(realizzato + non_realizzato, 2)

    def riepilogo(self) -> dict:
        return {
            "capitale_iniziale_usd": self.capitale_iniziale_usd,
            "disponibile_usd": round(self.disponibile_usd, 2),
            "posizioni_aperte": len(self.posizioni_aperte),
            "trade_chiusi": len(self.storico),
            "pnl_totale_usd": self.totale_pnl(),
            "valore_totale_usd": round(self.disponibile_usd + self.totale_pnl(), 2),
        }



