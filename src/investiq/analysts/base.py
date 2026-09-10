"""ResearchAnalyst — abstract base class for all InvestIQ analyst pipelines.

Defines the common contract that every analyst pipeline must satisfy.
All analyst implementations should inherit from this ABC and implement
the run() method.

Usage:
    class MyAnalyst(ResearchAnalyst):
        def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from investiq.models.analyst_input import AnalystInput
from investiq.models.research import ResearchFinding


class ResearchAnalyst(ABC):
    """Abstract base class for all InvestIQ analyst pipelines.

    Every analyst implementation must provide a run() method that
    accepts an AnalystInput payload and returns a list of validated
    ResearchFinding instances.

    The abstraction is intentionally minimal — it does not prescribe
    constructor signatures, caching, cost tracking, or LLM provider
    injection, which remain implementation-specific.
    """

    @abstractmethod
    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        """Execute the analyst pipeline on the given input.

        Args:
            analyst_input: Structured payload containing company profile,
                           calculated metrics, and evidence items.

        Returns:
            A list of validated ResearchFinding instances.
        """
        ...