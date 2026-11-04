"""AI package - esporta MotoreAI, Segnale e LLMManager."""

from src.ai.motore import MotoreAI, Segnale
from src.ai.llm_motore import LLMManager, conferma_con_llm

__all__ = ["MotoreAI", "Segnale", "LLMManager", "conferma_con_llm"]
