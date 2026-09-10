"""Financial/Banking Analyst prompt template (version financial_analyst_v1).

Formulates institutional-grade research instructions for banking fundamentals.
Prohibits BUY/SELL trading recommendations and final CIO stance.
"""

from investiq.models.analyst_input import AnalystInput

PROMPT_VERSION = "financial_analyst_v1"

FINANCIAL_ANALYST_SYSTEM_INSTRUCTION = """You are a senior institutional equity research analyst specializing in Indian banking and financial services.

Your role:
- Analyze fundamental business metrics, asset quality, operating efficiency, and liability franchise.
- Derive analytical insights, state explicit assumptions, and draw evidence-backed inferences.
- Highlight positive implications, downside risks, and thesis breakers.

STRICT CONSTRAINTS:
1. Do NOT issue BUY, SELL, HOLD, or price target recommendations. This platform provides decision support only.
2. Do NOT adopt a final CIO stance or issue a definitive portfolio allocation.
3. Every finding MUST cite one or more valid evidence_id values from the provided input evidence payload.
4. Confidence scores MUST be between 0.0 and 1.0.
"""


def render_financial_analyst_prompt(payload: AnalystInput) -> str:
    """Render versioned financial_analyst_v1 prompt string from AnalystInput payload."""
    comp = payload.company
    metrics = payload.latest_metrics

    evidence_summary = "\n".join(
        f"  - [{ev.evidence_id}] {ev.label}: {ev.value} (Source: {ev.source})"
        for ev in payload.evidence_items
    )

    prompt = f"""--- RESEARCH OBJECTIVE ---
{payload.research_objective}

--- TARGET COMPANY ---
Ticker: {comp.ticker}
Name: {comp.name}
Company Type: {comp.company_type.value}
Sector: {comp.sector.value}

--- CALCULATED FINANCIAL METRICS ({metrics.fiscal_year}) ---
- ROE: {metrics.roe}%
- ROA: {metrics.roa}%
- NIM: {metrics.nim}%
- CASA Ratio: {metrics.casa_ratio}%
- Gross NPA Ratio: {metrics.gross_npa_ratio}%
- Net NPA Ratio: {metrics.net_npa_ratio}%
- Cost-to-Income: {metrics.cost_to_income}%
- Credit Cost: {metrics.credit_cost}%
- EPS: ₹{metrics.eps}
- Book Value Per Share: ₹{metrics.book_value_per_share}

--- EVIDENCE PAYLOAD ---
{evidence_summary if evidence_summary else "  (No specific evidence items supplied)"}

--- OUTPUT REQUIREMENTS ---
Return a JSON object with a single key "findings" containing an array of finding objects.
Each finding object has these fields (REQUIRED: analyst, title, statement, confidence, evidence_ids, category.
OPTIONAL: fundamental_observation, why_it_matters, positive_implication, negative_implication, thesis_breaker):

REQUIRED fields:
1. analyst: Identifying analyst handle, set to "financial_analyst".
2. title: Short descriptive headline.
3. statement: Core high-level investment insight statement.
4. confidence: Confidence score between 0.0 and 1.0.
5. evidence_ids: List of valid evidence_id strings cited.
6. category: Finding category (liability_franchise, asset_quality, profitability, growth, valuation).

OPTIONAL enrichment fields:
7. fundamental_observation: Core business data observation.
8. why_it_matters: Analytical justification of significance.
9. positive_implication: Upside driver or operational strength.
10. negative_implication: Downside risk or counter-evidence.
11. thesis_breaker: Condition under which this thesis fails.
"""
    return prompt.strip()
