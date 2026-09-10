"""AnalystExecutor — sequential execution of selected ResearchAnalyst instances.

Executes a list of analyst keys in deterministic order through the
AnalystRegistry. Each analyst receives the same AnalystInput.

The sequential API is designed to be replaced by concurrent execution
in a future phase without changing callers.

Usage:
    executor = AnalystExecutor(registry)
    findings = executor.execute(["financial_analyst"], analyst_input)
"""

from __future__ import annotations

from investiq.analysts.registry import AnalystRegistry
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import ResearchFinding


class AnalystExecutor:
    """Sequential executor for registered ResearchAnalyst instances.

    Attributes:
        registry: The AnalystRegistry used to resolve analyst keys.
    """

    def __init__(self, registry: AnalystRegistry) -> None:
        """Initialize the executor with a registry.

        Args:
            registry: An AnalystRegistry containing the analysts to execute.
        """
        self.registry = registry

    def execute(
        self,
        analyst_keys: list[str],
        analyst_input: AnalystInput,
    ) -> list[ResearchFinding]:
        """Execute the selected analysts in order.

        Iterates through analyst_keys in the exact order given, resolves
        each key through the registry, calls run(), and collects all
        findings into a flat list preserving key order.

        Args:
            analyst_keys: Ordered list of registered analyst keys to execute.
            analyst_input: The AnalystInput to pass to each analyst.

        Returns:
            A flat list of ResearchFinding instances. Findings are ordered
            by analyst_keys order, preserving each analyst's internal ordering.

        Raises:
            KeyError: If any analyst_key is not found in the registry.
            Any exception raised by an analyst's run() method propagates.
        """
        findings: list[ResearchFinding] = []

        for key in analyst_keys:
            analyst = self.registry.get(key)
            findings.extend(analyst.run(analyst_input))

        return findings