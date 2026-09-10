"""AnalystRegistry — a string-keyed lookup for ResearchAnalyst instances.

Provides a simple registration and retrieval mechanism for analyst
pipelines. The registry stores already-created ResearchAnalyst instances
and is NOT a factory or dependency-injection container.

Usage:
    registry = AnalystRegistry()
    registry.register("financial_analyst", analyst)
    registry.get("financial_analyst")  # returns the exact instance
    registry.list()                    # returns ["financial_analyst"]
"""

from __future__ import annotations

from investiq.analysts.base import ResearchAnalyst


class AnalystRegistry:
    """A string-keyed registry of ResearchAnalyst instances.

    Attributes:
        _analysts: Internal dict mapping string keys to ResearchAnalyst instances.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._analysts: dict[str, ResearchAnalyst] = {}

    def register(self, key: str, analyst: ResearchAnalyst) -> None:
        """Register a ResearchAnalyst instance under the given key.

        Args:
            key: A non-empty string key to identify the analyst.
            analyst: The ResearchAnalyst instance to register.

        Raises:
            ValueError: If the key is empty, or if the key is already
                        registered (to prevent silent overwrites).
        """
        if not key:
            raise ValueError("Analyst key must be a non-empty string.")
        if key in self._analysts:
            raise ValueError(
                f"Analyst key {key!r} is already registered. "
                f"Remove the existing entry first if replacement is intended."
            )
        self._analysts[key] = analyst

    def get(self, key: str) -> ResearchAnalyst:
        """Retrieve the registered ResearchAnalyst for the given key.

        Args:
            key: The string key to look up.

        Returns:
            The registered ResearchAnalyst instance.

        Raises:
            KeyError: If the key is not registered.
        """
        if key not in self._analysts:
            raise KeyError(key)
        return self._analysts[key]

    def list(self) -> list[str]:
        """Return all registered keys, sorted deterministically.

        Returns:
            A sorted list of registered key strings.
        """
        return sorted(self._analysts.keys())