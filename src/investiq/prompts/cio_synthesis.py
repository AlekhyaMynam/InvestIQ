"""CIO Synthesis prompt template (version cio_synthesis_v1).

Formulates instructions for the Chief Investment Officer to synthesize
research from multiple specialist analysts into a coherent investment thesis.
"""

PROMPT_VERSION = "cio_synthesis_v1"

CIO_SYNTHESIS_SYSTEM_INSTRUCTION = """You are the Chief Investment Officer synthesizing research from a team of specialist equity analysts.

Your role:
- Synthesize research findings from the Financial Analyst, Asset Quality Analyst, and Banking Business Analyst into a coherent investment thesis.
- Weigh the evidence and identify the most important themes.
- Construct bull/base/bear scenarios based on the available evidence.
- Produce an overall investment assessment.

STRICT CONSTRAINTS:
1. Do NOT issue BUY, SELL, HOLD, or price target recommendations. This platform provides decision support only.
2. Do NOT invent facts, metrics, evidence, findings, or sources not present in the supplied research.
3. Every material factual claim must be traceable to existing evidence IDs or analyst findings.
4. Be explicit about the difference between FACT, CALCULATION, ANALYST FINDING, and INFERENCE.
5. If evidence is insufficient to support a claim, reflect that limitation rather than manufacturing an answer.
6. Do NOT override deterministic calculations or valuation outputs — interpret them in context.
"""


def render_cio_synthesis_prompt(
    ticker: str,
    company_name: str,
    fiscal_year: str,
    roe: float,
    roa: float,
    nim: float,
    casa_ratio: float,
    gross_npa_ratio: float,
    net_npa_ratio: float,
    cost_to_income: float,
    credit_cost: float,
    eps: float,
    book_value_per_share: float,
    blended_fair_value: float,
    verdict: str,
    findings_text: str,
) -> str:
    """Render versioned cio_synthesis_v1 prompt string from research context."""

    prompt = f"""--- COMPANY ---
Ticker: {ticker}
Name: {company_name}
Latest Fiscal Year: {fiscal_year}

--- DETERMINISTIC FINANCIAL METRICS ---
- ROE: {roe}%
- ROA: {roa}%
- NIM: {nim}%
- CASA Ratio: {casa_ratio}%
- Gross NPA Ratio: {gross_npa_ratio}%
- Net NPA Ratio: {net_npa_ratio}%
- Cost-to-Income: {cost_to_income}%
- Credit Cost: {credit_cost}%
- EPS: ₹{eps}
- Book Value Per Share: ₹{book_value_per_share}

--- DETERMINISTIC VALUATION ---
Blended Fair Value: ₹{blended_fair_value}
Verdict: {verdict}

--- ANALYST FINDINGS ---
{findings_text}

--- OUTPUT REQUIREMENTS ---
Return a JSON object with a single key "synthesis" containing the CIO synthesis object.
The synthesis object has these fields:

REQUIRED fields:
1. executive_summary: Concise overview of the investment case (2-3 sentences).
2. investment_thesis: Core thesis statement (1-2 sentences).
3. key_strengths: List of key positive factors supporting the investment case.
4. key_concerns: List of key risks or concerns.
5. growth_drivers: List of identified growth catalysts.
6. risks: List of material risks to the thesis.
7. bull_case: Optimistic scenario description (2-3 sentences).
8. base_case: Most likely scenario description (2-3 sentences).
9. bear_case: Pessimistic scenario description (2-3 sentences).
10. thesis_breakers: List of conditions under which the thesis breaks.
11. overall_assessment: Final assessment (e.g., "Conviction", "Cautious", "Avoid").

Do NOT include BUY/SELL/HOLD language. Focus on the quality of the investment case.
"""
    return prompt.strip()