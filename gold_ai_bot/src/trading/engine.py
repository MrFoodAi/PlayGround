"""Motore di trading: coordina feed, AI, rischio, portafoglio ed esecuzione."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from src.ai.motore import MotoreAI, Segnale
from src.ai.llm_motore import LLMManager, conferma_con_llm
from src.data.feed import FeedPrezzi, Indicatori
from src.defi.connector import ExecutorDeFi, OrdineEseguito
from src.trading.portfolio import Portafoglio, Posizione
from src.trading.risk import GestioneRischio
from src.utils.config import get
from src.utils.logger import logger
from src.utils.notifications import Notifiche


class TradingEngine:
    """Loop principale del bot. Gira H24, multi-trade, con gestione rischio."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        bot_cfg = cfg.get("bot", {})
        dati_cfg = cfg.get("dati", {})
        trading_cfg = cfg.get("trading", {})

        self.paper_trading = bool(bot_cfg.get("modalita_paper_trading", True))
        self.h24 = bool(bot_cfg.get("operativita_h24", True))
        self.multi_trade = bool(bot_cfg.get("multi_trade", True))

        self.simbolo = trading_cfg.get("asset_principale", "XAU/USD")
        self.asset_defi = trading_cfg.get("asset_defi", "XAUT")
        self.timeframe = dati_cfg.get("timeframe", "15m")
        self.intervallo_secondi = int(dati_cfg.get("aggiornamento_prezzi_secondi", 60))

        self.feed = FeedPrezzi(
            fonte=dati_cfg.get("prezzo_reale_api", "mock"), simbolo=self.simbolo
        )
        self.ai = MotoreAI(cfg)
        self.rischio = GestioneRischio(cfg)
        self.portafoglio = Portafoglio(
            capitale_iniziale_usd=float(cfg.get("risk_management", {}).get("capitale_totale_usd", 1000.0))
        )
        self.executor = ExecutorDeFi(cfg, paper_trading=self.paper_trading)
        self.notifiche = Notifiche(
            token=cfg.get("notifiche", {}).get("telegram_bot_token"),
            chat_id=cfg.get("notifiche", {}).get("telegram_chat_id"),
            attive=bool(cfg.get("notifiche", {}).get("attive", False)),
        )

        # LLM gratuito professionale
        self.llm = LLMManager(cfg)

        self.in_esecuzione = False
        self.loop_task: Optional[asyncio.Task] = None
        self.storico_segnali: list[Segnale] = []
        self.max_posizioni_concorrenti = int(bot_cfg.get("max_posizioni_concorrenti", 5))
        self.trade_size_forzato_usd: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Ciclo vitale
    # ------------------------------------------------------------------ #
    async def avvia(self) -> None:
        """Avvia il loop H24."""
        if self.in_esecuzione:
            logger.warning("Il motore è già in esecuzione.")
            return
        self.in_esecuzione = True
        modalita = "PAPER TRADING (simulazione)" if self.paper_trading else "REALE"
        logger.info(f"=== Avvio GoldAI XAU Bot [{modalita}] ===")
        logger.info(f"Asset: {self.simbolo} | DeFi: {self.asset_defi} | Multi-trade: {self.multi_trade}")
        logger.info(f"Paper trading: {self.paper_trading} | H24: {self.h24}")

        # Addestramento iniziale del modello AI sullo storico
        storico = self.feed.storico(n_candele=500, timeframe=self.timeframe)
        if not storico.empty:
            res = self.ai.istruisciti(storico)
            logger.info(f"Inizializzazione AI: {res}")

        self.loop_task = asyncio.create_task(self._loop())
        await self.loop_task

    async def ferma(self) -> None:
        """Ferma il loop in modo sicuro."""
        self.in_esecuzione = False
        if self.loop_task:
            self.loop_task.cancel()
        logger.info("=== Bot fermato ===")

    # ------------------------------------------------------------------ #
    # Loop principale
    # ------------------------------------------------------------------ #
    async def _loop(self) -> None:
        while self.in_esecuzione:
            try:
                await self._ciclo_trading()
            except Exception as exc:
                logger.error(f"Errore nel ciclo di trading: {exc}")
            await asyncio.sleep(self.intervallo_secondi)

    async def _ciclo_trading(self) -> None:
        prezzo = self.feed.prezzo_attuale()
        storico = self.feed.storico(n_candele=500, timeframe=self.timeframe)

        if storico.empty:
            logger.warning("Nessun dato di storico disponibile.")
            return

        # Aggiorna prezzi e gestisci stop/take su posizioni aperte
        self.portafoglio.aggiorna_prezzi(prezzo)
        da_chiudere = self.portafoglio.controlla_stop_take(prezzo)
        for posizione, motivo in da_chiudere:
            self._chiudi_posizione(posizione, prezzo, motivo)

        # Genera segnale AI
        segnale = self.ai.genera_segnale(storico, prezzo)
        self.storico_segnali.append(segnale)
        if len(self.storico_segnali) > 1000:
            self.storico_segnali = self.storico_segnali[-1000:]

        logger.info(
            f"Segnale AI: {segnale.azione} (conf {segnale.confidenza:.0%}) @ {segnale.prezzo:.2f} | {segnale.motivo}"
        )

        # Se c'è un segnale BUY/SELL con confidenza sufficiente, apri posizione
        if segnale.azione in ("BUY", "SELL") and segnale.confidenza >= self.ai.soglia:
            self._valuta_apertura(segnale)

    # ------------------------------------------------------------------ #
    # Applicazione impostazioni da interfaccia
    # ------------------------------------------------------------------ #
    def applica_impostazioni(self, imp: dict) -> None:
        """Applica le impostazioni ricevute dalla dashboard (trade size, strategia, rischio, ecc.)."""
        if "trade_size_usd" in imp and imp["trade_size_usd"]:
            self.trade_size_forzato_usd = float(imp["trade_size_usd"])
        else:
            self.trade_size_forzato_usd = None

        if "rischio_per_operazione_percent" in imp:
            self.rischio.limiti.rischio_per_operazione_percent = float(imp["rischio_per_operazione_percent"])
        if "stop_loss_percent" in imp:
            self.rischio.limiti.stop_loss_percent = float(imp["stop_loss_percent"])
        if "take_profit_percent" in imp:
            self.rischio.limiti.take_profit_percent = float(imp["take_profit_percent"])
        if "soglia_confidenza_minima" in imp:
            self.ai.soglia = float(imp["soglia_confidenza_minima"])
        if "max_posizioni_concorrenti" in imp:
            self.max_posizioni_concorrenti = int(imp["max_posizioni_concorrenti"])
        if "modalita_paper_trading" in imp:
            self.paper_trading = bool(imp["modalita_paper_trading"])

        if "llm_provider" in imp:
            self.llm.provider = imp["llm_provider"]
        if "llm_modello" in imp:
            self.llm.modello = imp["llm_modello"]
        if "llm_endpoint" in imp:
            self.llm.endpoint = imp["llm_endpoint"]
        if "llm_api_key" in imp:
            self.llm.api_key = imp["llm_api_key"]
        if "usa_llm" in imp:
            self.llm.attivo = bool(imp["usa_llm"])

        logger.info("Impostazioni applicate dal pannello di controllo.")

    # ------------------------------------------------------------------ #
    # Apertura / chiusura posizioni
    # ------------------------------------------------------------------ #
    def _valuta_apertura(self, segnale: Segnale) -> None:
        if len(self.portafoglio.posizioni_aperte) >= self.max_posizioni_concorrenti:
            logger.warning("Numero massimo di posizioni concorrenti raggiunto.")
            return

        puo, motivo_rischio = self.rischio.puo_operare()
        if not puo:
            logger.warning(f"Blocco rischio: {motivo_rischio}")
            return

        prezzo = segnale.prezzo
        direzione = "LONG" if segnale.azione == "BUY" else "SHORT"
        stop = self.rischio.prezzi_stop(prezzo, segnale.azione)

        # Dimensione posizione: trade size forzato (impostazioni) oppure calcolo rischio
        if self.trade_size_forzato_usd:
            importo_usd = self.trade_size_forzato_usd
        else:
            importo_usd = self.rischio.dimensione_posizione_usd(prezzo, stop["stop_loss"])

        if importo_usd < self.rischio.limiti.dimensione_minima_ordine_usd:
            logger.warning(f"Importo calcolato {importo_usd:.2f} USD sotto il minimo.")
            return

        # --- Conferma LLM (AI professionale gratuita) ---
        parere_llm = None
        if self.llm.disponibile():
            parere_llm = self.llm.chiedi_segnale({
                "prezzo": prezzo,
                "rsi": segnale.indicatori.get("rsi", 50),
                "macd": segnale.indicatori.get("macd", 0),
                "macd_segnale": segnale.indicatori.get("macd_segnale", 0),
                "sma_breve": segnale.indicatori.get("sma_breve", prezzo),
                "sma_lungo": segnale.indicatori.get("sma_lungo", prezzo),
                "bb_inferiore": segnale.indicatori.get("bb_inferiore", prezzo),
                "bb_superiore": segnale.indicatori.get("bb_superiore", prezzo),
                "trend": "rialzista" if prezzo > segnale.indicatori.get("sma_breve", prezzo) else "ribassista",
            })
            logger.info(f"Parere LLM: {parere_llm}")

        if not conferma_con_llm(segnale.azione, parere_llm):
            logger.info("Operazione bloccata dal filtro LLM o mancata conferma.")
            return

        # --- Esecuzione ordine (simulata se paper trading, reale firmata altrimenti) ---
        if segnale.azione == "BUY":
            ordine = self.executor.esegui_compra(importo_usd, prezzo)
        else:
            quantita = importo_usd / prezzo
            ordine = self.executor.esegui_vendita(quantita, prezzo)

        if not ordine.successo:
            logger.error(f"Ordine fallito: {ordine.nota}")
            return

        # Apri posizione nel portafoglio
        self.portafoglio.apri(
            asset=self.asset_defi,
            direzione=direzione,
            importo_usd=importo_usd,
            quantita_asset=ordine.quantita_asset,
            prezzo=prezzo,
            stop_loss=stop["stop_loss"],
            take_profit=stop["take_profit"],
        )
        self.notifiche.invia(
            f"🤖 <b>GoldAI Bot</b>\n"
            f"Posizione aperta: {direzione} {self.asset_defi}\n"
            f"Importo: {importo_usd:.2f} USD @ {prezzo:.2f}\n"
            f"SL: {stop['stop_loss']:.2f} | TP: {stop['take_profit']:.2f}\n"
            f"Modalita: {'PAPER' if self.paper_trading else 'REALE'}"
        )

    def _chiudi_posizione(self, posizione: Posizione, prezzo: float, motivo: str) -> None:
        chiusa = self.portafoglio.chiudi(posizione.id, prezzo, motivo)
        if chiusa:
            self.rischio.registra_esito(chiusa.vincente or False, chiusa.pnl_usd)
            self.notifiche.invia(
                f"📉 <b>GoldAI Bot - Chiusura</b>\n"
                f"{chiusa.direzione} {self.asset_defi}\n"
                f"PnL: {chiusa.pnl_usd:+.2f} USD ({motivo})"
            )

    # ------------------------------------------------------------------ #
    # Stato per dashboard / API esterne
    # ------------------------------------------------------------------ #
    def stato(self) -> dict:
        ultimo_prezzo = self.feed.prezzo_attuale()
        ultimo_segnale = self.storico_segnali[-1] if self.storico_segnali else None
        return {
            "bot": "GoldAI XAU",
            "versione": "1.0.0",
            "in_esecuzione": self.in_esecuzione,
            "modalita": "PAPER TRADING" if self.paper_trading else "REALE",
            "prezzo_attuale_usd": round(ultimo_prezzo, 2),
            "asset_defi": self.asset_defi,
            "ai_attivo": self.ai.attivo,
            "llm_attivo": self.llm.attivo and self.llm.disponibile(),
            "llm_provider": self.llm.provider,
            "llm_modello": self.llm.modello,
            "trading_reale": not self.paper_trading,
            "signer_connesso": self.executor.signer.è_connesso() if self.executor.signer else False,
            "ultimo_segnale": {
                "azione": ultimo_segnale.azione if ultimo_segnale else "N/D",
                "confidenza": ultimo_segnale.confidenza if ultimo_segnale else 0.0,
                "motivo": ultimo_segnale.motivo if ultimo_segnale else "",
            } if ultimo_segnale else None,
            "portafoglio": self.portafoglio.riepilogo(),
            "rischio": {
                "perdite_consecutive": self.rischio.perdite_consecutive,
                "bloccato_drawdown": self.rischio.bloccato_per_drawdown,
            },
        }

    def ultimi_segnali(self, n: int = 10) -> list[dict]:
        return [
            {
                "azione": s.azione,
                "confidenza": s.confidenza,
                "prezzo": s.prezzo,
                "motivo": s.motivo,
                "indicatori": s.indicatori,
            }
            for s in self.storico_segnali[-n:]
        ]


# alias per compatibilita
Engine = TradingEngine
