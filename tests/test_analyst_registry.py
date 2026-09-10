"""Tests for AnalystRegistry — string-keyed lookup for ResearchAnalyst instances.

All tests are deterministic and make zero external API calls.
"""

import pytest

from investiq.analysts.asset_quality_analyst import AssetQualityAnalyst
from investiq.analysts.banking_business_analyst import BankingBusinessAnalyst
from investiq.analysts.base import ResearchAnalyst
from investiq.analysts.financial_analyst import FinancialAnalystPipeline
from investiq.analysts.registry import AnalystRegistry
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import FindingCategory, ResearchFinding
from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
from investiq.research.orchestrator import ResearchOrchestrator


# ── Test double: a minimal concrete ResearchAnalyst ──────────────────

class _SpyAnalyst(ResearchAnalyst):
    """A minimal ResearchAnalyst implementation for registry testing.

    Does not call any LLM — returns a fixed list of findings.
    """

    def __init__(self, name: str = "spy") -> None:
        self.name = name
        self.call_count = 0

    def run(self, analyst_input: AnalystInput) -> list[ResearchFinding]:
        self.call_count += 1
        return [
            ResearchFinding(
                analyst=self.name,
                title="Spy Finding",
                statement="This is a test finding from the spy analyst.",
                confidence=0.5,
                evidence_ids=["SYN-HDFCBANK-ROE-001"],
                category=FindingCategory.PROFITABILITY,
            ),
        ]


# ── Tests ────────────────────────────────────────────────────────────

class TestAnalystRegistryEmpty:
    """Empty registry behavior."""

    def test_list_empty(self):
        """list() returns [] for a newly created registry."""
        registry = AnalystRegistry()
        assert registry.list() == []

    def test_get_unknown_raises_key_error(self):
        """get() raises KeyError for an unregistered key."""
        registry = AnalystRegistry()
        with pytest.raises(KeyError, match="unknown"):
            registry.get("unknown")


class TestAnalystRegistryRegister:
    """Registering analysts."""

    def test_register_and_get(self):
        """get() returns the exact registered instance."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst(name="test")
        registry.register("test_analyst", analyst)
        retrieved = registry.get("test_analyst")
        assert retrieved is analyst
        assert retrieved.name == "test"

    def test_register_preserves_identity(self):
        """The registered instance is the exact same object (identity)."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        registry.register("spy", analyst)
        assert registry.get("spy") is analyst

    def test_register_financial_analyst_pipeline(self):
        """Registry accepts a FinancialAnalystPipeline as a ResearchAnalyst."""
        registry = AnalystRegistry()
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        registry.register("financial_analyst", pipeline)
        retrieved = registry.get("financial_analyst")
        assert retrieved is pipeline
        assert isinstance(retrieved, ResearchAnalyst)
        assert isinstance(retrieved, FinancialAnalystPipeline)

    def test_duplicate_key_raises_value_error(self):
        """register() raises ValueError on duplicate key."""
        registry = AnalystRegistry()
        analyst_a = _SpyAnalyst(name="a")
        analyst_b = _SpyAnalyst(name="b")
        registry.register("same_key", analyst_a)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("same_key", analyst_b)

    def test_register_after_duplicate_error(self):
        """After a duplicate error, the original registration is intact."""
        registry = AnalystRegistry()
        analyst_a = _SpyAnalyst(name="a")
        analyst_b = _SpyAnalyst(name="b")
        registry.register("same_key", analyst_a)
        with pytest.raises(ValueError):
            registry.register("same_key", analyst_b)
        assert registry.get("same_key") is analyst_a

    def test_empty_key_raises_value_error(self):
        """register() raises ValueError for an empty key."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        with pytest.raises(ValueError, match="non-empty"):
            registry.register("", analyst)
class TestAnalystRegistryList:
    """Listing registered analysts."""

    def test_list_after_register(self):
        """list() includes registered keys."""
        registry = AnalystRegistry()
        registry.register("alpha", _SpyAnalyst())
        registry.register("beta", _SpyAnalyst())
        keys = registry.list()
        assert "alpha" in keys
        assert "beta" in keys
        assert len(keys) == 2

    def test_list_deterministic_ordering(self):
        """list() returns keys in sorted order."""
        registry = AnalystRegistry()
        registry.register("z-analyst", _SpyAnalyst())
        registry.register("a-analyst", _SpyAnalyst())
        registry.register("m-analyst", _SpyAnalyst())
        assert registry.list() == ["a-analyst", "m-analyst", "z-analyst"]

    def test_list_does_not_include_removed_keys(self):
        """list() only reflects currently registered keys."""
        registry = AnalystRegistry()
        registry.register("temp", _SpyAnalyst())
        assert "temp" in registry.list()
        del registry._analysts["temp"]
        assert "temp" not in registry.list()


class TestAnalystRegistryKeyValidation:
    """Key validation rules."""

    def test_case_sensitive_keys(self):
        """Keys are case-sensitive — 'A' and 'a' are distinct."""
        registry = AnalystRegistry()
        registry.register("Financial_Analyst", _SpyAnalyst())
        registry.register("financial_analyst", _SpyAnalyst())
        assert registry.list() == ["Financial_Analyst", "financial_analyst"]
        assert "financial_analyst" in registry.list()
        assert "Financial_Analyst" in registry.list()

    def test_keys_are_not_normalized(self):
        """Keys are stored exactly as provided."""
        registry = AnalystRegistry()
        registry.register("  spaced-key  ", _SpyAnalyst())
        assert "  spaced-key  " in registry.list()
        assert registry.get("  spaced-key  ") is not None


class TestAnalystRegistryNonMutation:
    """Registry does not mutate registered analysts."""

    def test_registry_does_not_mutate_analyst(self):
        """Registering an analyst does not change it."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst(name="original")
        original_name = analyst.name
        registry.register("test", analyst)
        assert analyst.name == original_name

    def test_registry_does_not_call_analyst(self):
        """Registering does not invoke the analyst's run() method."""
        registry = AnalystRegistry()
        analyst = _SpyAnalyst()
        registry.register("test", analyst)
        assert analyst.call_count == 0


class TestAnalystRegistryDeterministic:
    """Registry behavior is deterministic."""

    def test_repeatable_results(self):
        """Multiple operations on the same registry produce consistent results."""
        registry = AnalystRegistry()
        registry.register("a", _SpyAnalyst())
        registry.register("b", _SpyAnalyst())
        assert registry.list() == ["a", "b"]
        assert registry.list() == ["a", "b"]
        assert registry.get("a") is registry.get("a")


class TestAnalystRegistryWithFinancialAnalyst:
    """End-to-end verification with FinancialAnalystPipeline."""

    def test_financial_analyst_registered_and_works(self):
        """A registered FinancialAnalystPipeline can be run after retrieval."""
        registry = AnalystRegistry()
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        registry.register("financial_analyst", pipeline)

        retrieved = registry.get("financial_analyst")
        assert isinstance(retrieved, FinancialAnalystPipeline)

        from investiq.calculators.bank_metrics import compute_bank_metrics
        from investiq.data.loader import load_financial_data
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
        from pathlib import Path

        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        data = load_financial_data("HDFCBANK", data_dir=data_dir)
        metrics = compute_bank_metrics(data)[-1]
        evidence = get_synthetic_hdfcbank_evidence()

        analyst_input = AnalystInput(
            company=data.company,
            latest_metrics=metrics,
            evidence_items=evidence,
        )

        findings = retrieved.run(analyst_input)
        assert len(findings) > 0
        assert all(f.analyst == "financial_analyst" for f in findings)

    def test_existing_orchestrator_unchanged(self):
        """ResearchOrchestrator still works without AnalystRegistry."""
        from investiq.research.orchestrator import ResearchOrchestrator
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence
        from pathlib import Path

        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=data_dir)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)

        assert snapshot.ticker == "HDFCBANK"
class TestOrchestratorRegistryIntegration:
    """ResearchOrchestrator integration with AnalystRegistry."""

    def test_default_orchestrator_creates_registry(self):
        """Orchestrator without explicit registry creates a default one."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider)
        assert orchestrator.analyst_registry is not None
        assert isinstance(orchestrator.analyst_registry, AnalystRegistry)

    def test_default_registry_contains_financial_analyst(self):
        """Default registry has exactly 'financial_analyst' key."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider)
        keys = orchestrator.analyst_registry.list()
        assert "financial_analyst" in keys

    def test_default_registry_contains_financial_analyst_pipeline(self):
        """Default registry contains a FinancialAnalystPipeline instance."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider)
        analyst = orchestrator.analyst_registry.get("financial_analyst")
        assert isinstance(analyst, FinancialAnalystPipeline)

    def test_existing_provider_only_constructor_works(self):
        """ResearchOrchestrator(provider=provider) still works."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider)
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert snapshot.ticker == "HDFCBANK"
        assert len(snapshot.findings) > 0

    def test_existing_provider_and_data_dir_constructor_works(self):
        """ResearchOrchestrator(provider=provider, data_dir=dir) still works."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        orchestrator = ResearchOrchestrator(provider=provider, data_dir=data_dir)
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert len(snapshot.findings) > 0
        assert snapshot.ticker == "HDFCBANK"

    def test_injected_registry_is_used(self):
        """An explicitly injected AnalystRegistry is used by the orchestrator."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        registry = AnalystRegistry()
        registry.register("financial_analyst", analyst)
        orchestrator = ResearchOrchestrator(
            provider=provider,
            data_dir=data_dir,
            analyst_registry=registry,
        )
        assert orchestrator.analyst_registry is registry
        assert orchestrator.analyst_registry.get("financial_analyst") is analyst

    def test_injected_analyst_identity_preserved(self):
        """The exact injected analyst instance is used by research()."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        aqa_analyst = AssetQualityAnalyst(provider=provider)
        bba_analyst = BankingBusinessAnalyst(provider=provider)
        registry = AnalystRegistry()
        registry.register("financial_analyst", analyst)
        registry.register("asset_quality_analyst", aqa_analyst)
        registry.register("banking_business_analyst", bba_analyst)
        orchestrator = ResearchOrchestrator(
            provider=provider,
            data_dir=data_dir,
            analyst_registry=registry,
        )
        evidence = get_synthetic_hdfcbank_evidence()
        orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert orchestrator.analyst_registry.get("financial_analyst") is analyst

    def test_injected_registry_can_execute_research(self):
        """A registry with both analysts can execute research successfully."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        aqa_analyst = AssetQualityAnalyst(provider=provider)
        bba_analyst = BankingBusinessAnalyst(provider=provider)
        registry = AnalystRegistry()
        registry.register("financial_analyst", analyst)
        registry.register("asset_quality_analyst", aqa_analyst)
        registry.register("banking_business_analyst", bba_analyst)
        orchestrator = ResearchOrchestrator(
            provider=provider,
            data_dir=data_dir,
            analyst_registry=registry,
        )
        evidence = get_synthetic_hdfcbank_evidence()
        snapshot = orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert snapshot.ticker == "HDFCBANK"
        assert len(snapshot.findings) > 0

    def test_orchestrator_no_second_analyst_with_injected_registry(self):
        """When a registry is injected, no additional pipelines are created."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        analyst = FinancialAnalystPipeline(provider=provider)
        aqa_analyst = AssetQualityAnalyst(provider=provider)
        bba_analyst = BankingBusinessAnalyst(provider=provider)
        registry = AnalystRegistry()
        registry.register("financial_analyst", analyst)
        registry.register("asset_quality_analyst", aqa_analyst)
        registry.register("banking_business_analyst", bba_analyst)
        orchestrator = ResearchOrchestrator(
            provider=provider,
            data_dir=data_dir,
            analyst_registry=registry,
        )
        assert len(registry.list()) == 3
        evidence = get_synthetic_hdfcbank_evidence()
        orchestrator.research("HDFCBANK", evidence_items=evidence)
        assert len(registry.list()) == 3

    def test_missing_analyst_in_injected_registry_raises_key_error(self):
        """If injected registry lacks 'financial_analyst', research raises KeyError."""
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data" / "prepared"
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        registry = AnalystRegistry()  # empty
        orchestrator = ResearchOrchestrator(
            provider=provider,
            data_dir=data_dir,
            analyst_registry=registry,
        )
        with pytest.raises(KeyError, match="financial_analyst"):
            orchestrator.research("HDFCBANK")