"""Gestione del rischio e del dimensionamento delle posizioni."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LimitiRischio:
    capitale_totale_usd: float
    rischio_per_operazione_percent: float
    stop_loss_percent: float
    take_profit_percent: float
    trailing_stop_percent: float
    max_drawdown_giornaliero_percent: float
    max_perdite_consecutive: int
    dimensione_minima_ordine_usd: float
    slippage_tolleranza_percent: float


class GestioneRischio:
    """Calcola dimensioni di ordine, stop loss e verifica i limiti di rischio."""

    def __init__(self, cfg: dict):
        rm = cfg.get("risk_management", {})
        self.limiti = LimitiRischio(
            capitale_totale_usd=float(rm.get("capitale_totale_usd", 1000.0)),
            rischio_per_operazione_percent=float(rm.get("rischio_per_operazione_percent", 1.0)),
            stop_loss_percent=float(rm.get("stop_loss_percent", 2.0)),
            take_profit_percent=float(rm.get("take_profit_percent", 4.0)),
            trailing_stop_percent=float(rm.get("trailing_stop_percent", 1.0)),
            max_drawdown_giornaliero_percent=float(rm.get("max_drawdown_giornaliero_percent", 5.0)),
            max_perdite_consecutive=int(rm.get("max_perdite_consecutive", 3)),
            dimensione_minima_ordine_usd=float(rm.get("dimensione_minima_ordine_usd", 10.0)),
            slippage_tolleranza_percent=float(rm.get("slippage_tolleranza_percent", 0.5)),
        )
        self.perdite_consecutive = 0
        self.drawdown_giornaliero_usd = 0.0
        self.bloccato_per_drawdown = False

    def dimensione_posizione_usd(self, prezzo: float, stop_loss_prezzo: float) -> float:
        """Dimensione della posizione in USD basata sul rischio per operazione."""
        if prezzo <= 0 or stop_loss_prezzo <= 0:
            return 0.0
        distanza_sl = abs(prezzo - stop_loss_prezzo)
        if distanza_sl == 0:
            return 0.0
        rischio_usd = self.limiti.capitale_totale_usd * (self.limiti.rischio_per_operazione_percent / 100.0)
        dimensione = rischio_usd / (distanza_sl / prezzo)  # USD esposti
        return max(dimensione, self.limiti.dimensione_minima_ordine_usd)

    def prezzi_stop(self, prezzo: float, direzione: str) -> dict:
        """Calcola prezzi di stop loss e take profit."""
        if direzione == "BUY":
            sl = prezzo * (1 - self.limiti.stop_loss_percent / 100.0)
            tp = prezzo * (1 + self.limiti.take_profit_percent / 100.0)
        else:  # SELL
            sl = prezzo * (1 + self.limiti.stop_loss_percent / 100.0)
            tp = prezzo * (1 - self.limiti.take_profit_percent / 100.0)
        return {"stop_loss": round(sl, 2), "take_profit": round(tp, 2)}

    def puo_operare(self) -> tuple[bool, str]:
        """Verifica se il bot puo aprire nuove posizioni (limiti drawdown/perdite)."""
        if self.bloccato_per_drawdown:
            return False, "Bloccato: drawdown giornaliero raggiunto."
        if self.perdite_consecutive >= self.limiti.max_perdite_consecutive:
            return False, f"Bloccato: {self.perdite_consecutive} perdite consecutive."
        return True, "OK"

    def registra_esito(self, vincente: bool, pnl_usd: float) -> None:
        """Aggiorna statistiche di rischio dopo un trade chiuso."""
        if vincente:
            self.perdite_consecutive = 0
        else:
            self.perdite_consecutive += 1
            self.drawdown_giornaliero_usd += abs(pnl_usd)

        if self.drawdown_giornaliero_usd >= self.limiti.capitale_totale_usd * (
            self.limiti.max_drawdown_giornaliero_percent / 100.0
        ):
            self.bloccato_per_drawdown = True
