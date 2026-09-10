"""Calculated financial metrics for banking companies.

All metrics are computed deterministically in Python from
IncomeStatement and BalanceSheet data. Never delegated to an LLM.
"""

from pydantic import BaseModel

from investiq.models.evidence import EvidenceItem


class BankMetrics(BaseModel):
    """Deterministic metrics calculated from bank financial statements.

    Each metric carries an evidence trail linking it to its source data
    and calculation methodology.

    Attributes:
        fiscal_year: The fiscal year these metrics apply to.
        roe: Return on Equity (Net Profit / Avg Equity) as percentage.
        roa: Return on Assets (Net Profit / Avg Total Assets) as percentage.
        nim: Net Interest Margin (NII / Avg Total Assets) as percentage.
        casa_ratio: CASA Deposits / Total Deposits as percentage.
        gross_npa_ratio: Gross NPA / Gross Advances as percentage.
        net_npa_ratio: Net NPA / Net Advances as percentage.
        cost_to_income: Operating Expenses / Total Operating Income as percentage.
        credit_cost: Provisions / Avg Gross Advances as percentage.
        eps: Earnings Per Share in ₹.
        book_value_per_share: Total Equity / Shares Outstanding in ₹.
        evidence: Full audit trail for all calculations.
    """

    fiscal_year: str

    # Profitability
    roe: float
    roa: float
    nim: float

    # Liability franchise
    casa_ratio: float

    # Asset quality
    gross_npa_ratio: float
    net_npa_ratio: float

    # Efficiency
    cost_to_income: float
    credit_cost: float

    # Per-share
    eps: float
    book_value_per_share: float

    # Traceability
    evidence: list[EvidenceItem]
