"""Tests for AnalystExecutor — sequential execution of ResearchAnalyst instances.

All tests are deterministic and make zero external API calls.
"""

import pytest

from investiq.analysts.base import ResearchAnalyst
from investiq.analysts.executor import AnalystExecutor
from investiq.analysts.registry import AnalystRegistry
from investiq.models.analyst_input import AnalystInput
from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.metrics import BankMetrics
from investiq.models.research import FindingCategory, ResearchFinding


def _make_input() -> AnalystInput:
    """Create a minimal valid AnalystInput for testing."""
    return AnalystInput(
        company=CompanyProfile(
            ticker="TEST", name="Test",
            sector=Sector.FINANCIAL_SERVICES,
            company_type=CompanyType.BANK,
        ),
        latest_metrics=BankMetrics(
            fiscal_year="FY2025",
            roe=16.0, roa=2.0, nim=3.5,
            casa_ratio=40.0,
            gross_npa_ratio=1.2, net_npa_ratio=0.4,
            cost_to_income=42.0, credit_cost=0.5,
            eps=60.0, book_value_per_share=500.0,
            evidence=[],
        ),
    )


class _SpyAnalyst(ResearchAnalyst):
    """Minimal ResearchAnalyst that records calls and returns fixed findings."""

    def __init__(self, name: str = "spy") -> None:
        self.name = name
        self.call_count = 0
        self.received_inputs: list[AnalystInput] = []

    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        self.call_count += 1
        self.received_inputs.append(analyst_input)
        return [
            ResearchFinding(
                analyst=self.name,
                title=f"Finding from {self.name}",
                statement=f"Test statement from {self.name}.",
                confidence=0.5,
                evidence_ids=["SYN-HDFCBANK-ROE-001"],
                category=FindingCategory.PROFITABILITY,
            ),
        ]


class _MultiFindingAnalyst(ResearchAnalyst):
    """Analyst that returns a configurable number of findings."""

    def __init__(self, name: str, count: int = 2) -> None:
        self.name = name
        self.count = count

    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        return [
            ResearchFinding(
                analyst=self.name,
                title=f"{self.name} Finding {i + 1}",
                statement=f"Test statement {i + 1} from {self.name}.",
                confidence=0.5,
                evidence_ids=["SYN-HDFCBANK-ROE-001"],
                category=FindingCategory.PROFITABILITY,
            )
            for i in range(self.count)
        ]


class _RaisingAnalyst(ResearchAnalyst):
    """Analyst that raises an exception on run()."""

    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        raise RuntimeError("Analyst execution failed")


class TestAnalystExecutorConstruction:
    """Executor construction."""

    def test_constructor_accepts_registry(self):
        """AnalystExecutor can be constructed with a registry."""
        registry = AnalystRegistry()
        executor = AnalystExecutor(registry=registry)
        assert executor.registry is registry


class TestAnalystExecutorSingleAnalyst:
    """Single analyst execution."""

    def test_single_analyst(self):
        """Given one registered analyst, execute() returns its findings."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst(name="financial_analyst")
        registry.register("financial_analyst", analyst)
        executor = AnalystExecutor(registry=registry)
        findings = executor.execute(["financial_analyst"], _make_input())
        assert len(findings) == 1
        assert findings[0].analyst == "financial_analyst"

    def test_analyst_is_called(self):
        """The registered analyst's run() method is invoked."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        registry.register("spy", analyst)
        executor = AnalystExecutor(registry=registry)
        executor.execute(["spy"], _make_input())
        assert analyst.call_count == 1

    def test_analyst_identity_preserved(self):
        """Findings retain the analyst's name attribute."""
        registry = AnalystRegistry()
        analyst_a = _SpyAnalyst(name="analyst_a")
        analyst_b = _SpyAnalyst(name="analyst_b")
        registry.register("a", analyst_a)
        registry.register("b", analyst_b)
        executor = AnalystExecutor(registry=registry)
        findings = executor.execute(["a", "b"], _make_input())
        assert findings[0].analyst == "analyst_a"
        assert findings[1].analyst == "analyst_b"


class TestAnalystExecutorMultipleAnalysts:
    """Multiple analyst execution."""

    def test_both_analysts_execute(self):
        """Both analysts are called when multiple keys are provided."""
        registry = AnalystRegistry()
        analyst_a = _SpyAnalyst(name="a")
        analyst_b = _SpyAnalyst(name="b")
        registry.register("a", analyst_a)
        registry.register("b", analyst_b)
        executor = AnalystExecutor(registry=registry)
        executor.execute(["a", "b"], _make_input())
        assert analyst_a.call_count == 1
        assert analyst_b.call_count == 1
class TestAnalystExecutorExecutionOrdering:
    """Execution and finding ordering."""

    def test_execution_ordering(self):
        """Analysts execute in the order of analyst_keys."""
        execution_order: list[str] = []

        class _OrderingAnalyst(ResearchAnalyst):
            def __init__(self, name: str):
                self.name = name
            def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
                execution_order.append(self.name)
                return []

        registry = AnalystRegistry()
        registry.register("a", _OrderingAnalyst("a"))
        registry.register("b", _OrderingAnalyst("b"))
        executor = AnalystExecutor(registry=registry)
        executor.execute(["a", "b"], _make_input())
        assert execution_order == ["a", "b"]
        execution_order.clear()
        executor.execute(["b", "a"], _make_input())
        assert execution_order == ["b", "a"]

    def test_finding_ordering(self):
        """Findings are ordered by analyst_keys, preserving each analyst's order."""
        registry = AnalystRegistry()
        registry.register("a", _MultiFindingAnalyst(name="a", count=2))
        registry.register("b", _MultiFindingAnalyst(name="b", count=2))
        executor = AnalystExecutor(registry=registry)
        findings = executor.execute(["a", "b"], _make_input())
        assert len(findings) == 4
        assert findings[0].analyst == "a" and "1" in findings[0].title
        assert findings[1].analyst == "a" and "2" in findings[1].title
        assert findings[2].analyst == "b" and "1" in findings[2].title
        assert findings[3].analyst == "b" and "2" in findings[3].title


class TestAnalystExecutorEmptyList:
    """Empty analyst key list."""

    def test_empty_list_returns_empty(self):
        """execute([], input) returns []."""
        registry = AnalystRegistry()
        executor = AnalystExecutor(registry=registry)
        findings = executor.execute([], _make_input())
        assert findings == []

    def test_empty_list_no_registry_access(self):
        """Empty list does not access the registry."""
        registry = AnalystRegistry()
        executor = AnalystExecutor(registry=registry)
        findings = executor.execute([], _make_input())
        assert findings == []


class TestAnalystExecutorUnknownKey:
    """Unknown analyst key."""

    def test_unknown_key_raises_key_error(self):
        """execute() with unknown key raises KeyError."""
        registry = AnalystRegistry()
        executor = AnalystExecutor(registry=registry)
        with pytest.raises(KeyError, match="does_not_exist"):
            executor.execute(["does_not_exist"], _make_input())


class TestAnalystExecutorExceptionPropagation:
    """Analyst exceptions propagate."""

    def test_analyst_exception_propagates(self):
        """If an analyst raises, the exception propagates."""
        registry = AnalystRegistry()
        registry.register("failing", _RaisingAnalyst())
        executor = AnalystExecutor(registry=registry)
        with pytest.raises(RuntimeError, match="Analyst execution failed"):
            executor.execute(["failing"], _make_input())


class TestAnalystExecutorNonMutation:
    """Executor does not mutate inputs or registry."""

    def test_analyst_input_not_mutated(self):
        """AnalystInput is not mutated by execution."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        registry.register("spy", analyst)
        executor = AnalystExecutor(registry=registry)
        analyst_input = _make_input()
        original_objective = analyst_input.research_objective
        executor.execute(["spy"], analyst_input)
        assert analyst_input.research_objective == original_objective

    def test_registry_not_mutated(self):
        """Executor does not modify the registry."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        registry.register("spy", analyst)
        original_keys = registry.list()
        executor = AnalystExecutor(registry=registry)
        executor.execute(["spy"], _make_input())
        assert registry.list() == original_keys

    def test_same_analyst_input_to_multiple_analysts(self):
        """Multiple analysts receive the same AnalystInput instance."""
        registry = AnalystRegistry()
        analyst_a = _SpyAnalyst(name="a")
        analyst_b = _SpyAnalyst(name="b")
        registry.register("a", analyst_a)
        registry.register("b", analyst_b)
        executor = AnalystExecutor(registry=registry)
        analyst_input = _make_input()
        executor.execute(["a", "b"], analyst_input)
        assert analyst_a.received_inputs[0] is analyst_input
        assert analyst_b.received_inputs[0] is analyst_input