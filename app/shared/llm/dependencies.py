"""
Dependency injection factory for LLMClient.
Import get_llm_client in any module's dependencies.py that needs the LLM.
"""
from functools import lru_cache

from shared.llm.client import LLMClient
from core.config import settings

@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """
    Returns a singleton LLMClient.
    lru_cache ensures the model is initialised once per process,
    not once per request.
    """
    return LLMClient(settings=settings.llm)
