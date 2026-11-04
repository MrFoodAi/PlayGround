"""TransactionSigner - Firma e invio automatico transazioni su DEX (trading reale).

⚠️ PERICOLO: questo modulo gestisce chiavi private e invia transazioni on-chain.
Usare SOLO se si è esperti, su testnet prima, e con fondi che si possono perdere.
La chiave privata NON deve mai essere salvata su disco: usare solo variabili d'ambiente.
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List, Tuple

from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except Exception:
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
    except Exception:
        geth_poa_middleware = None  # type: ignore

from src.utils.logger import logger


class TransactionSigner:
    """Firma e invia transazioni firmate su Ethereum/Polygon/BSC."""

    def __init__(self, rpc_url: str, private_key: str, chain_id: int = 1):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if geth_poa_middleware is not None:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.account = self.w3.eth.account.from_key(private_key)
        self.indirizzo = self.account.address
        self.chain_id = chain_id
        self._nonce_cache: Optional[int] = None

    def è_connesso(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def saldo_nativo(self) -> float:
        """Restituisce saldo ETH/MATIC/BNB in unità native."""
        try:
            saldo_wei = self.w3.eth.get_balance(self.indirizzo)
            return float(self.w3.from_wei(saldo_wei, "ether"))
        except Exception as exc:
            logger.error(f"Errore lettura saldo nativo: {exc}")
            return 0.0

    def _nonce(self) -> int:
        if self._nonce_cache is None:
            self._nonce_cache = self.w3.eth.get_transaction_count(self.indirizzo, "pending")
        return self._nonce_cache

    def _incrementa_nonce(self):
        if self._nonce_cache is not None:
            self._nonce_cache += 1

    def _raw_tx(self, signed) -> bytes:
        """Compatibilità tra versioni web3.py (raw_transaction / rawTransaction)."""
        return getattr(signed, "raw_transaction", signed.rawTransaction)

    def costruisci_swap_eth_per_token(
        self,
        router_contratto,
        amount_in_wei: int,
        amount_out_min_wei: int,
        path: List[str],
        scadenza_secondi: int = 600,
    ) -> Dict[str, Any]:
        """Costruisce transazione swapExactETHForTokens firmabile."""
        try:
            ultimo_blocco = self.w3.eth.get_block("latest")
            deadline = int(ultimo_blocco["timestamp"]) + scadenza_secondi
            tx = router_contratto.functions.swapExactETHForTokens(
                amount_out_min_wei,
                path,
                self.indirizzo,
                deadline,
            ).build_transaction({
                "chainId": self.chain_id,
                "from": self.indirizzo,
                "value": amount_in_wei,
                "gas": 300000,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.to_wei("2", "gwei"),
                "nonce": self._nonce(),
            })
            return tx
        except Exception as exc:
            logger.error(f"Errore costruzione swap ETH→token: {exc}")
            raise

    def costruisci_swap_token_per_token(
        self,
        router_contratto,
        amount_in_wei: int,
        amount_out_min_wei: int,
        path: List[str],
        scadenza_secondi: int = 600,
    ) -> Dict[str, Any]:
        """Costruisce transazione swapExactTokensForTokens firmabile."""
        try:
            ultimo_blocco = self.w3.eth.get_block("latest")
            deadline = int(ultimo_blocco["timestamp"]) + scadenza_secondi
            tx = router_contratto.functions.swapExactTokensForTokens(
                amount_in_wei,
                amount_out_min_wei,
                path,
                self.indirizzo,
                deadline,
            ).build_transaction({
                "chainId": self.chain_id,
                "from": self.indirizzo,
                "gas": 300000,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.to_wei("2", "gwei"),
                "nonce": self._nonce(),
            })
            return tx
        except Exception as exc:
            logger.error(f"Errore costruzione swap token→token: {exc}")
            raise

    def firma_e_invia(self, tx: Dict[str, Any]) -> Tuple[bool, Optional[str], str]:
        """Firma e invia transazione. Ritorna (successo, hash_tx, nota)."""
        try:
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(self._raw_tx(signed))
            self._incrementa_nonce()
            hash_hex = self.w3.to_hex(tx_hash)
            logger.info(f"Transazione firmata e inviata: {hash_hex}")
            return True, hash_hex, "Transazione inviata on-chain"
        except Exception as exc:
            logger.error(f"Errore firma/invio transazione: {exc}")
            return False, None, str(exc)

    def attendi_conferma(self, tx_hash_hex: str, timeout: int = 180) -> Optional[dict]:
        """Attende la conferma on-chain della transazione."""
        try:
            ricevuta = self.w3.eth.wait_for_transaction_receipt(tx_hash_hex, timeout=timeout)
            return dict(ricevuta)
        except Exception as exc:
            logger.warning(f"Transazione non confermata entro {timeout}s: {exc}")
            return None
