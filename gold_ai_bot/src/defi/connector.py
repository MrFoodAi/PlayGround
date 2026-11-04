"""Connettore DeFi (Web3) e esecuzione ordini su DEX per token oro (XAUT/PAXG).

In paper trading (default) tutte le operazioni sono simulate.
Per trading reale occorre configurare RPC, indirizzo wallet e chiave privata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from src.utils.logger import logger

try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
except Exception:  # web3 non installato
    Web3 = None  # type: ignore
    geth_poa_middleware = None  # type: ignore


@dataclass
class OrdineEseguito:
    successo: bool
    hash_transazione: Optional[str]
    importo_usd: float
    quantita_asset: float
    prezzo: float
    nota: str


# ABI minime (ERC20 + Uniswap V2 Router)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]

UNISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Indirizzi di esempio (mainnet Ethereum) - da sostituire con quelli reali della rete scelta
INDIRIZZI_TOKEN = {
    "ethereum": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "XAUT": "0x672e96c7068FC6350C8862438540728d68049C3b",  # Tether Gold (esempio)
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "UNISWAP_ROUTER": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    },
    "polygon": {
        "USDT": "0xc2132D05D31c914a87C6611Cf10e58A2662fC906",
        "XAUT": "0xTuoXAUTSuPolygon",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "UNISWAP_ROUTER": "0xa5E0829C3C8024425cFc86d4e99998Db72256b5",
    },
}


class ExecutorDeFi:
    """Esegue (o simula) ordini di acquisto/vendita su DEX."""

    def __init__(self, cfg: dict, paper_trading: bool = True):
        self.cfg = cfg
        self.paper_trading = paper_trading
        trading_cfg = cfg.get("trading", {})
        self.rete = trading_cfg.get("rete_blockchain", "ethereum")
        self.rpc_url = trading_cfg.get("rpc_url", "")
        self.indirizzo_wallet = trading_cfg.get("indirizzo_wallet", "")
        self.chiave_privata = trading_cfg.get("chiave_privata", "")
        self.asset_defi = trading_cfg.get("asset_defi", "XAUT")

        self.web3: Optional[object] = None
        self.router_contratto = None
        if not paper_trading:
            self._inizializza_web3()

    def _inizializza_web3(self) -> None:
        if Web3 is None:
            logger.error("web3.py non installato. Impossibile operare su blockchain reale.")
            return
        if not self.rpc_url:
            logger.error("RPC URL non configurato. Trading reale disabilitato.")
            return
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if geth_poa_middleware is not None:
                self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            indirizzi = INDIRIZZI_TOKEN.get(self.rete, {})
            router_addr = indirizzi.get("UNISWAP_ROUTER")
            if router_addr and self.web3.is_connected():
                self.router_contratto = self.web3.eth.contract(
                    address=Web3.to_checksum_address(router_addr), abi=UNISWAP_ROUTER_ABI
                )
                logger.info(f"Connesso alla rete {self.rete} via Web3.")
            else:
                logger.warning("Web3 connesso ma router non configurato.")
        except Exception as exc:
            logger.error(f"Errore inizializzazione Web3: {exc}")

    # ------------------------------------------------------------------ #
    # Esecuzione ordini
    # ------------------------------------------------------------------ #
    def esegui_compra(self, importo_usd: float, prezzo: float, slippage_percent: float = 0.5) -> OrdineEseguito:
        """Compra asset_defi usando USDT/USDC (simulato se paper trading)."""
        quantita = importo_usd / prezzo if prezzo > 0 else 0.0
        if self.paper_trading:
            logger.info(
                f"[PAPER] COMPRA {quantita:.6f} {self.asset_defi} per {importo_usd:.2f} USD @ {prezzo:.2f}"
            )
            return OrdineEseguito(
                successo=True,
                hash_transazione=None,
                importo_usd=importo_usd,
                quantita_asset=quantita,
                prezzo=prezzo,
                nota="Simulato (paper trading)",
            )
        return self._reale_compra(importo_usd, prezzo, slippage_percent)

    def esegui_vendita(self, quantita_asset: float, prezzo: float, slippage_percent: float = 0.5) -> OrdineEseguito:
        """Vende quantita_asset di asset_defi (simulato se paper trading)."""
        importo_usd = quantita_asset * prezzo
        if self.paper_trading:
            logger.info(
                f"[PAPER] VENDITA {quantita_asset:.6f} {self.asset_defi} per {importo_usd:.2f} USD @ {prezzo:.2f}"
            )
            return OrdineEseguito(
                successo=True,
                hash_transazione=None,
                importo_usd=importo_usd,
                quantita_asset=quantita_asset,
                prezzo=prezzo,
                nota="Simulato (paper trading)",
            )
        return self._reale_vendita(quantita_asset, prezzo, slippage_percent)

    # ------------------------------------------------------------------ #
    # Trading reale (placeholder - richiede firma transazioni)
    # ------------------------------------------------------------------ #
    def _reale_compra(self, importo_usd: float, prezzo: float, slippage: float) -> OrdineEseguito:
        logger.warning("Esecuzione reale su DEX non completamente implementata (richiede chiave privata sicura).")
        return OrdineEseguito(
            successo=False,
            hash_transazione=None,
            importo_usd=importo_usd,
            quantita_asset=0.0,
            prezzo=prezzo,
            nota="Trading reale non attivo: manca implementazione firma transazione",
        )

    def _reale_vendita(self, quantita: float, prezzo: float, slippage: float) -> OrdineEseguito:
        logger.warning("Esecuzione reale su DEX non completamente implementata.")
        importo_usd = quantita * prezzo
        return OrdineEseguito(
            successo=False,
            hash_transazione=None,
            importo_usd=importo_usd,
            quantita_asset=quantita,
            prezzo=prezzo,
            nota="Trading reale non attivo: manca implementazione firma transazione",
        )

    def saldo_wallet(self) -> dict:
        """Restituisce i saldi dei token configurati (simulato se paper)."""
        if self.paper_trading:
            return {"USDT": 1000.0, self.asset_defi: 0.0, "nota": "Paper trading"}
        # reale: leggere balanceOf dal contratto ERC20
        return {"nota": "Reale non implementato"}
