"""LLM Response Cache abstraction.

Generates deterministic cache keys based on company, analyst type, normalized input,
prompt version, and model config. For Phase 2A, provides an in-memory cache implementation.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from investiq.llm.base import LLMResponse


def build_cache_key(
    ticker: str,
    analyst_type: str,
    normalized_input: str,
    prompt_version: str,
    model_config: dict[str, Any],
) -> str:
    """Generate a deterministic SHA-256 cache key.

    Incorporates company/ticker, analyst type, normalized input payload,
    prompt version, and model configuration parameters.
    """
    raw_key_payload = {
        "ticker": ticker.upper(),
        "analyst_type": analyst_type,
        "input_hash": hashlib.sha256(normalized_input.encode("utf-8")).hexdigest(),
        "prompt_version": prompt_version,
        "model_config": model_config,
    }
    serialized = json.dumps(raw_key_payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class LLMCache(ABC):
    """Abstract cache interface for LLM outputs."""

    @abstractmethod
    def get(self, key: str) -> LLMResponse | None:
        """Retrieve a cached response if present."""
        pass

    @abstractmethod
    def set(self, key: str, response: LLMResponse) -> None:
        """Store a response in the cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        pass


class MemoryLLMCache(LLMCache):
    """In-memory implementation of LLMCache for Phase 2A offline execution."""

    def __init__(self) -> None:
        self._store: dict[str, LLMResponse] = {}

    def get(self, key: str) -> LLMResponse | None:
        if key in self._store:
            cached_resp = self._store[key].model_copy(deep=True)
            cached_resp.cache_hit = True
            return cached_resp
        return None

    def set(self, key: str, response: LLMResponse) -> None:
        self._store[key] = response.model_copy(deep=True)

    def clear(self) -> None:
        self._store.clear()
