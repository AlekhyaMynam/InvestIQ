"""CIO Synthesis model — the final investment-level synthesis of all analyst research.

Combines deterministic financial data, valuation outputs, and evidence-backed
analyst findings into a structured investment thesis.
"""

from __future__ import annotations

from pydantic import BaseModel


class CIOSynthesis(BaseModel):
    """Structured investment synthesis produced by the CIO.

    Synthesizes findings from all three analysts (financial, asset quality,
    banking business) into a coherent investment thesis with scenarios.

    Attributes:
        executive_summary: Concise overview of the investment case.
        investment_thesis: Core thesis statement.
        key_strengths: Key positive factors supporting the investment case.
        key_concerns: Key risks or concerns.
        growth_drivers: Identified growth catalysts.
        risks: Material risks to the thesis.
        bull_case: Optimistic scenario with assumptions.
        base_case: Most likely scenario.
        bear_case: Pessimistic scenario with assumptions.
        thesis_breakers: Conditions under which the thesis breaks.
        overall_assessment: Final assessment (e.g., Conviction, Cautious, Avoid).
    """

    executive_summary: str
    investment_thesis: str
    key_strengths: list[str]
    key_concerns: list[str]
    growth_drivers: list[str]
    risks: list[str]
    bull_case: str
    base_case: str
    bear_case: str
    thesis_breakers: list[str]
    overall_assessment: str


class CIOSynthesisResponse(BaseModel):
    """Wrapper for CIO synthesis output returned by the LLM.

    Enables structured-output schema enforcement by wrapping CIOSynthesis
    in a BaseModel that has model_json_schema().
    """

    synthesis: CIOSynthesis