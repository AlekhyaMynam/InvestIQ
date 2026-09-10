"""Bank-specific financial metric calculations.

All calculations are deterministic Python — never delegated to an LLM.
Every metric is accompanied by evidence items tracing back to the
source financial statement fields used in the computation.
"""

import uuid
from datetime import datetime, timezone

from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.financials import BalanceSheet, FinancialData, IncomeStatement
from investiq.models.metrics import BankMetrics


def _evidence(
    label: str,
    source_field: str,
    value: float,
    fiscal_year: str,
    company_name: str = "Unknown",
    tag: EvidenceTag = EvidenceTag.CALCULATION,
    domain: EvidenceDomain | None = None,
) -> EvidenceItem:
    """Create an evidence item for a calculated metric.

    The source field is derived from the actual company name to ensure
    company-specific provenance.
    """
    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        tag=tag,
        label=label,
        source=f"{company_name} Financial Statements {fiscal_year}",
        source_field=source_field,
        timestamp=datetime.now(timezone.utc),
        value=round(value, 4),
        domain=domain,
    )


def _fact(
    label: str,
    source_field: str,
    value: float,
    fiscal_year: str,
    company_name: str = "Unknown",
    domain: EvidenceDomain | None = None,
) -> EvidenceItem:
    """Create a FACT evidence item for a raw financial data point.

    The source field is derived from the actual company name to ensure
    company-specific provenance.
    """
    return EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        tag=EvidenceTag.FACT,
        label=label,
        source=f"{company_name} Financial Statements {fiscal_year}",
        source_field=source_field,
        timestamp=datetime.now(timezone.utc),
        value=value,
        domain=domain,
    )


def calculate_roe(
    net_profit: float,
    equity_current: float,
    equity_previous: float | None,
) -> float:
    """Return on Equity = Net Profit / Average Equity (%).

    Uses average equity when previous year data is available,
    falls back to current year equity for the first year.
    """
    avg_equity = (
        (equity_current + equity_previous) / 2
        if equity_previous is not None
        else equity_current
    )
    if avg_equity == 0:
        return 0.0
    return (net_profit / avg_equity) * 100


def calculate_roa(
    net_profit: float,
    assets_current: float,
    assets_previous: float | None,
) -> float:
    """Return on Assets = Net Profit / Average Total Assets (%)."""
    avg_assets = (
        (assets_current + assets_previous) / 2
        if assets_previous is not None
        else assets_current
    )
    if avg_assets == 0:
        return 0.0
    return (net_profit / avg_assets) * 100


def calculate_nim(
    nii: float,
    assets_current: float,
    assets_previous: float | None,
) -> float:
    """Net Interest Margin = NII / Average Total Assets (%)."""
    avg_assets = (
        (assets_current + assets_previous) / 2
        if assets_previous is not None
        else assets_current
    )
    if avg_assets == 0:
        return 0.0
    return (nii / avg_assets) * 100


def calculate_casa_ratio(casa_deposits: float, total_deposits: float) -> float:
    """CASA Ratio = CASA Deposits / Total Deposits (%)."""
    if total_deposits == 0:
        return 0.0
    return (casa_deposits / total_deposits) * 100


def calculate_gross_npa_ratio(gross_npa: float, gross_advances: float) -> float:
    """Gross NPA Ratio = Gross NPA / Gross Advances (%)."""
    if gross_advances == 0:
        return 0.0
    return (gross_npa / gross_advances) * 100


def calculate_net_npa_ratio(net_npa: float, net_advances: float) -> float:
    """Net NPA Ratio = Net NPA / Net Advances (%)."""
    if net_advances == 0:
        return 0.0
    return (net_npa / net_advances) * 100


def calculate_cost_to_income(
    operating_expenses: float, total_operating_income: float
) -> float:
    """Cost-to-Income Ratio = Operating Expenses / Total Operating Income (%)."""
    if total_operating_income == 0:
        return 0.0
    return (operating_expenses / total_operating_income) * 100


def calculate_credit_cost(
    provisions: float,
    advances_current: float,
    advances_previous: float | None,
) -> float:
    """Credit Cost = Provisions / Average Gross Advances (%)."""
    avg_advances = (
        (advances_current + advances_previous) / 2
        if advances_previous is not None
        else advances_current
    )
    if avg_advances == 0:
        return 0.0
    return (provisions / avg_advances) * 100


def calculate_eps(net_profit: float, shares_outstanding: float) -> float:
    """Earnings Per Share = Net Profit (₹ Cr) / Shares Outstanding (Cr) → ₹."""
    if shares_outstanding == 0:
        return 0.0
    return net_profit / shares_outstanding


def calculate_bvps(total_equity: float, shares_outstanding: float) -> float:
    """Book Value Per Share = Total Equity (₹ Cr) / Shares Outstanding (Cr) → ₹."""
    if shares_outstanding == 0:
        return 0.0
    return total_equity / shares_outstanding


def compute_bank_metrics(financial_data: FinancialData) -> list[BankMetrics]:
    """Compute all bank metrics for each fiscal year in the dataset.

    For metrics requiring averages (ROE, ROA, NIM, credit cost), the
    first year uses point-in-time values since no prior year is available.

    Args:
        financial_data: Complete financial dataset with statements and balance sheets.

    Returns:
        List of BankMetrics, one per fiscal year, ordered oldest → newest.
    """
    income_stmts = sorted(financial_data.income_statements, key=lambda x: x.fiscal_year)
    balance_sheets = sorted(financial_data.balance_sheets, key=lambda x: x.fiscal_year)

    # Build lookup by fiscal year
    bs_by_year: dict[str, BalanceSheet] = {bs.fiscal_year: bs for bs in balance_sheets}
    is_by_year: dict[str, IncomeStatement] = {is_.fiscal_year: is_ for is_ in income_stmts}

    company_name = financial_data.company.name
    results: list[BankMetrics] = []

    for i, fy in enumerate([is_.fiscal_year for is_ in income_stmts]):
        inc = is_by_year[fy]
        bs = bs_by_year[fy]

        # Previous year balance sheet for averages
        prev_bs: BalanceSheet | None = None
        if i > 0:
            prev_fy = income_stmts[i - 1].fiscal_year
            prev_bs = bs_by_year.get(prev_fy)

        prev_equity = prev_bs.total_equity if prev_bs else None
        prev_assets = prev_bs.total_assets if prev_bs else None
        prev_advances = prev_bs.total_advances_gross if prev_bs else None

        evidence: list[EvidenceItem] = []

        # --- ROE ---
        roe = calculate_roe(inc.net_profit, bs.total_equity, prev_equity)
        evidence.append(_evidence(
            f"ROE = Net Profit / Avg Equity = {roe:.2f}%",
            "roe", roe, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- ROA ---
        roa = calculate_roa(inc.net_profit, bs.total_assets, prev_assets)
        evidence.append(_evidence(
            f"ROA = Net Profit / Avg Total Assets = {roa:.2f}%",
            "roa", roa, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- NIM ---
        nim = calculate_nim(inc.net_interest_income, bs.total_assets, prev_assets)
        evidence.append(_evidence(
            f"NIM = NII / Avg Total Assets = {nim:.2f}%",
            "nim", nim, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- CASA Ratio ---
        casa = calculate_casa_ratio(bs.casa_deposits, bs.total_deposits)
        evidence.append(_evidence(
            f"CASA Ratio = CASA / Total Deposits = {casa:.2f}%",
            "casa_ratio", casa, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- Gross NPA Ratio ---
        gnpa = calculate_gross_npa_ratio(bs.gross_npa, bs.total_advances_gross)
        evidence.append(_evidence(
            f"Gross NPA Ratio = Gross NPA / Gross Advances = {gnpa:.2f}%",
            "gross_npa_ratio", gnpa, fy, company_name=company_name, domain=EvidenceDomain.ASSET_QUALITY,
        ))

        # --- Net NPA Ratio ---
        nnpa = calculate_net_npa_ratio(bs.net_npa, bs.total_advances_net)
        evidence.append(_evidence(
            f"Net NPA Ratio = Net NPA / Net Advances = {nnpa:.2f}%",
            "net_npa_ratio", nnpa, fy, company_name=company_name, domain=EvidenceDomain.ASSET_QUALITY,
        ))

        # --- Cost to Income ---
        cti = calculate_cost_to_income(inc.operating_expenses, inc.total_operating_income)
        evidence.append(_evidence(
            f"Cost-to-Income = Opex / Total Operating Income = {cti:.2f}%",
            "cost_to_income", cti, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- Credit Cost ---
        cc = calculate_credit_cost(inc.provisions, bs.total_advances_gross, prev_advances)
        evidence.append(_evidence(
            f"Credit Cost = Provisions / Avg Gross Advances = {cc:.2f}%",
            "credit_cost", cc, fy, company_name=company_name, domain=EvidenceDomain.ASSET_QUALITY,
        ))

        # --- EPS ---
        eps = calculate_eps(inc.net_profit, bs.shares_outstanding)
        evidence.append(_evidence(
            f"EPS = Net Profit / Shares Outstanding = ₹{eps:.2f}",
            "eps", eps, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        # --- BVPS ---
        bvps = calculate_bvps(bs.total_equity, bs.shares_outstanding)
        evidence.append(_evidence(
            f"BVPS = Total Equity / Shares Outstanding = ₹{bvps:.2f}",
            "book_value_per_share", bvps, fy, company_name=company_name, domain=EvidenceDomain.FINANCIAL,
        ))

        results.append(BankMetrics(
            fiscal_year=fy,
            roe=round(roe, 2),
            roa=round(roa, 2),
            nim=round(nim, 2),
            casa_ratio=round(casa, 2),
            gross_npa_ratio=round(gnpa, 2),
            net_npa_ratio=round(nnpa, 2),
            cost_to_income=round(cti, 2),
            credit_cost=round(cc, 2),
            eps=round(eps, 2),
            book_value_per_share=round(bvps, 2),
            evidence=evidence,
        ))

    return results
