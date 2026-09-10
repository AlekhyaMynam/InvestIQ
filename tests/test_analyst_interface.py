"""Tests for ResearchAnalyst interface and FinancialAnalystPipeline conformance.

Verifies that the ResearchAnalyst ABC exists, defines the expected contract,
and that FinancialAnalystPipeline correctly implements it.

All tests are deterministic and make zero external API calls.
"""

from pathlib import Path

import pytest

from investiq.analysts.base import ResearchAnalyst
from investiq.analysts.financial_analyst import FinancialAnalystPipeline
from investiq.llm.mock import MockLLMProvider
from investiq.models.analyst_input import AnalystInput
from investiq.models.research import ResearchFinding

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prepared"


class TestResearchAnalystInterface:
    """ResearchAnalyst ABC contract."""

    def test_interface_exists(self):
        """ResearchAnalyst class exists."""
        assert ResearchAnalyst is not None

    def test_interface_has_run_method(self):
        """ResearchAnalyst defines an abstract run() method."""
        assert hasattr(ResearchAnalyst, "run")
        assert callable(ResearchAnalyst.run)

    def test_interface_cannot_be_instantiated(self):
        """ResearchAnalyst ABC cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            ResearchAnalyst()  # type: ignore

    def test_interface_accepts_analyst_input(self):
        """run() method signature accepts AnalystInput parameter."""
        import inspect
        sig = inspect.signature(ResearchAnalyst.run)
        params = list(sig.parameters.keys())
        assert "analyst_input" in params
        assert params[1] == "analyst_input"

    def test_interface_returns_list_of_research_finding(self):
        """run() return annotation is list[ResearchFinding]."""
        import inspect
        sig = inspect.signature(ResearchAnalyst.run)
        return_annotation = sig.return_annotation
        anno_str = str(return_annotation)
        assert "list" in anno_str.lower()
        assert "ResearchFinding" in anno_str


class TestFinancialAnalystConformance:
    """FinancialAnalystPipeline conforms to ResearchAnalyst."""

    def test_is_subclass_of_research_analyst(self):
        """FinancialAnalystPipeline is a subclass of ResearchAnalyst."""
        assert issubclass(FinancialAnalystPipeline, ResearchAnalyst)

    def test_instance_is_research_analyst(self):
        """A FinancialAnalystPipeline instance is a ResearchAnalyst."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        assert isinstance(pipeline, ResearchAnalyst)

    def test_run_returns_list_of_research_finding(self):
        """pipeline.run() returns list[ResearchFinding]."""
        from investiq.calculators.bank_metrics import compute_bank_metrics
        from investiq.data.loader import load_financial_data
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence

        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics = compute_bank_metrics(data)[-1]
        evidence = get_synthetic_hdfcbank_evidence()

        analyst_input = AnalystInput(
            company=data.company,
            latest_metrics=metrics,
            evidence_items=evidence,
        )

        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        findings = pipeline.run(analyst_input)

        assert isinstance(findings, list)
        assert len(findings) > 0
        for f in findings:
            assert isinstance(f, ResearchFinding)

    def test_run_accepts_analyst_input(self):
        """pipeline.run() accepts an AnalystInput parameter."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        import inspect
        sig = inspect.signature(pipeline.run)
        params = list(sig.parameters.keys())
        assert "analyst_input" in params

    def test_constructor_accepts_provider(self):
        """FinancialAnalystPipeline constructor accepts LLMProvider."""
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        assert pipeline.provider is provider

    def test_constructor_accepts_cache(self):
        """FinancialAnalystPipeline constructor accepts optional cache."""
        from investiq.llm.cache import MemoryLLMCache
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cache = MemoryLLMCache()
        pipeline = FinancialAnalystPipeline(provider=provider, cache=cache)
        assert pipeline.cache is cache

    def test_constructor_accepts_cost_tracker(self):
        """FinancialAnalystPipeline constructor accepts optional cost tracker."""
        from investiq.llm.cost import CostTracker
        provider = MockLLMProvider(simulated_latency_ms=0.0)
        cost_tracker = CostTracker()
        pipeline = FinancialAnalystPipeline(
            provider=provider, cost_tracker=cost_tracker
        )
class TestResearchAnalystPolymorphism:
    """FinancialAnalystPipeline can be used polymorphically as ResearchAnalyst."""

    def test_function_accepts_research_analyst(self):
        """A function typed to accept ResearchAnalyst works with FinancialAnalystPipeline."""
        def run_analyst(analyst: ResearchAnalyst, input_data: AnalystInput) -> list[ResearchFinding]:
            return analyst.run(input_data)

        from investiq.calculators.bank_metrics import compute_bank_metrics
        from investiq.data.loader import load_financial_data
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence

        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics = compute_bank_metrics(data)[-1]
        evidence = get_synthetic_hdfcbank_evidence()

        analyst_input = AnalystInput(
            company=data.company,
            latest_metrics=metrics,
            evidence_items=evidence,
        )

        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        findings = run_analyst(pipeline, analyst_input)
        assert len(findings) > 0
        assert all(isinstance(f, ResearchFinding) for f in findings)


class TestExistingBehaviorUnchanged:
    """Existing FinancialAnalystPipeline behavior remains unchanged."""

    def test_provider_used(self):
        """The injected LLMProvider is used for generation."""
        from investiq.calculators.bank_metrics import compute_bank_metrics
        from investiq.data.loader import load_financial_data
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence

        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics = compute_bank_metrics(data)[-1]
        evidence = get_synthetic_hdfcbank_evidence()

        analyst_input = AnalystInput(
            company=data.company,
            latest_metrics=metrics,
            evidence_items=evidence,
        )

        recorded = []

        class RecordingProvider(MockLLMProvider):
            def generate_structured(self, request, response_schema):
                recorded.append((request, response_schema))
                return super().generate_structured(request, response_schema)

        provider = RecordingProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        findings = pipeline.run(analyst_input)

        assert len(recorded) == 1
        assert len(findings) > 0
        assert findings[0].analyst == "financial_analyst"

    def test_mock_provider_zero_network_calls(self):
        """MockLLMProvider makes zero network calls."""
        from investiq.calculators.bank_metrics import compute_bank_metrics
        from investiq.data.loader import load_financial_data
        from investiq.research.evidence_fixture import get_synthetic_hdfcbank_evidence

        data = load_financial_data("HDFCBANK", data_dir=DATA_DIR)
        metrics = compute_bank_metrics(data)[-1]
        evidence = get_synthetic_hdfcbank_evidence()

        analyst_input = AnalystInput(
            company=data.company,
            latest_metrics=metrics,
            evidence_items=evidence,
        )

        provider = MockLLMProvider(simulated_latency_ms=0.0)
        pipeline = FinancialAnalystPipeline(provider=provider)
        findings = pipeline.run(analyst_input)

        assert len(findings) > 0
        assert all(f.analyst == "financial_analyst" for f in findings)