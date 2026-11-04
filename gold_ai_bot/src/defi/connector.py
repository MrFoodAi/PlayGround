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
    try:
        from web3.middleware import geth_poa_middleware
    except Exception:
        from web3.middleware.geth_poa import geth_poa_middleware
except Exception:  # web3 non installato
    Web3 = None  # type: ignore
    geth_poa_middleware = None  # type: ignore

from src.defi.signer import TransactionSigner


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
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC Ethereum (esempio)
        "XAUT": "0x672e96c7068FC6350C8862438540728d68049C3b",  # Tether Gold (esempio)
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "UNISWAP_ROUTER": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    },
    "polygon": {
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "XAUT": "0xTuoXAUTSuPolygon",
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
        self.signer: Optional[TransactionSigner] = None
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
                # Inizializza il firmatore se c'è una chiave privata
                if self.chiave_privata:
                    try:
                        chain_id_map = {"ethereum": 1, "polygon": 137, "bsc": 56}
                        chain_id = chain_id_map.get(self.rete, 1)
                        self.signer = TransactionSigner(
                            self.rpc_url, self.chiave_privata, chain_id=chain_id
                        )
                        if self.signer.è_connesso():
                            logger.info(f"TransactionSigner inizializzato su {self.rete} (chain {chain_id}).")
                        else:
                            logger.warning("Signer creato ma non connesso alla RPC.")
                    except Exception as exc:
                        logger.error(f"Errore inizializzazione TransactionSigner: {exc}")
                        self.signer = None
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
    # Trading reale su DEX con firma automatica (EIP-1559)
    # ------------------------------------------------------------------ #
    def _reale_compra(self, importo_usd: float, prezzo: float, slippage: float) -> OrdineEseguito:
        """Compra XAUT con USDC firmando la transazione on-chain."""
        if not self.signer or not self.router_contratto:
            return OrdineEseguito(
                successo=False,
                hash_transazione=None,
                importo_usd=importo_usd,
                quantita_asset=0.0,
                prezzo=prezzo,
                nota="Signer o router non inizializzati",
            )
        try:
            indirizzi = INDIRIZZI_TOKEN.get(self.rete, {})
            usdc_addr = Web3.to_checksum_address(indirizzi.get("USDC", ""))
            xaut_addr = Web3.to_checksum_address(indirizzi.get("XAUT", ""))
            if not usdc_addr or not xaut_addr:
                raise ValueError("Indirizzi USDC/XAUT non configurati per questa rete")

            # Approva USDC al router se necessario (semplificato: saltato qui, presuppone allowance già presente)

            # Conversione importi (USDC 6 decimali, XAUT 9 decimali - valori indicativi)
            usdc_decimali = 6
            xaut_decimali = 9
            amount_in_wei = int(importo_usd * (10 ** usdc_decimali))
            quantita_asset = importo_usd / prezzo if prezzo > 0 else 0.0
            amount_out_min = int(quantita_asset * (10 ** xaut_decimali) * (1 - slippage / 100.0))

            tx = self.signer.costruisci_swap_token_per_token(
                self.router_contratto,
                amount_in_wei,
                amount_out_min,
                [usdc_addr, xaut_addr],
            )
            successo, hash_tx, nota = self.signer.firma_e_invia(tx)
            return OrdineEseguito(
                successo=successo,
                hash_transazione=hash_tx,
                importo_usd=importo_usd,
                quantita_asset=quantita_asset,
                prezzo=prezzo,
                nota=nota,
            )
        except Exception as exc:
            logger.error(f"Errore acquisto reale XAUT: {exc}")
            return OrdineEseguito(
                successo=False,
                hash_transazione=None,
                importo_usd=importo_usd,
                quantita_asset=0.0,
                prezzo=prezzo,
                nota=str(exc),
            )

    def _reale_vendita(self, quantita_asset: float, prezzo: float, slippage: float) -> OrdineEseguito:
        """Vende XAUT per USDC firmando la transazione on-chain."""
        if not self.signer or not self.router_contratto:
            return OrdineEseguito(
                successo=False,
                hash_transazione=None,
                importo_usd=quantita_asset * prezzo,
                quantita_asset=quantita_asset,
                prezzo=prezzo,
                nota="Signer o router non inizializzati",
            )
        try:
            indirizzi = INDIRIZZI_TOKEN.get(self.rete, {})
            usdc_addr = Web3.to_checksum_address(indirizzi.get("USDC", ""))
            xaut_addr = Web3.to_checksum_address(indirizzi.get("XAUT", ""))
            if not usdc_addr or not xaut_addr:
                raise ValueError("Indirizzi USDC/XAUT non configurati per questa rete")

            xaut_decimali = 9
            usdc_decimali = 6
            amount_in_wei = int(quantita_asset * (10 ** xaut_decimali))
            importo_usd = quantita_asset * prezzo
            amount_out_min = int(importo_usd * (10 ** usdc_decimali) * (1 - slippage / 100.0))

            tx = self.signer.costruisci_swap_token_per_token(
                self.router_contratto,
                amount_in_wei,
                amount_out_min,
                [xaut_addr, usdc_addr],
            )
            successo, hash_tx, nota = self.signer.firma_e_invia(tx)
            return OrdineEseguito(
                successo=successo,
                hash_transazione=hash_tx,
                importo_usd=importo_usd,
                quantita_asset=quantita_asset,
                prezzo=prezzo,
                nota=nota,
            )
        except Exception as exc:
            logger.error(f"Errore vendita reale XAUT: {exc}")
            return OrdineEseguito(
                successo=False,
                hash_transazione=None,
                importo_usd=quantita_asset * prezzo,
                quantita_asset=quantita_asset,
                prezzo=prezzo,
                nota=str(exc),
            )

    def saldo_wallet(self) -> dict:
        """Restituisce i saldi dei token configurati (simulato se paper)."""
        if self.paper_trading:
            return {"USDT": 1000.0, self.asset_defi: 0.0, "nota": "Paper trading"}
        # reale: leggere balanceOf dal contratto ERC20
        return {"nota": "Reale non implementato"}
