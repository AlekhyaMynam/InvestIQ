from datetime import date
from enum import Enum

from pydantic import BaseModel

from investiq.models.company import CompanyProfile


class ProvenanceType(str, Enum):
    """Data provenance classification."""

    SYNTHETIC = "SYNTHETIC"
    PUBLIC_FILING = "PUBLIC_FILING"
    MARKET_DATA = "MARKET_DATA"
    NEWS = "NEWS"
    OTHER_PUBLIC_SOURCE = "OTHER_PUBLIC_SOURCE"


class DatasetProvenance(BaseModel):
    """Metadata describing the origin, authenticity, and intended use of dataset."""

    type: ProvenanceType
    generated_by: str | None = None
    is_real_company_data: bool = False
    intended_use: str | None = None


class IncomeStatement(BaseModel):
    """Bank income statement for a single fiscal year.

    All monetary values in ₹ Crores.
    """

    fiscal_year: str                   # e.g., "FY2025"
    period_end: date

    # Revenue
    interest_income: float
    interest_expense: float
    net_interest_income: float         # Net Interest Income

    # Other income
    non_interest_income: float         # Fee income, trading gains, etc.
    total_operating_income: float      # = NII + non_interest_income

    # Expenses
    operating_expenses: float          # Employee cost + other opex
    pre_provision_operating_profit: float  # = total_operating_income - operating_expenses

    # Provisions & profit
    provisions: float                  # Loan loss provisions
    profit_before_tax: float
    tax_expense: float
    net_profit: float

    # Per-share (₹)
    dividend_per_share: float | None = None


class BalanceSheet(BaseModel):
    """Bank balance sheet for a single fiscal year.

    All monetary values in ₹ Crores.
    """

    fiscal_year: str
    period_end: date

    # Assets
    total_assets: float
    total_advances_gross: float        # Gross loan book
    total_advances_net: float          # Net of provisions
    investments: float | None = None

    # Liabilities
    total_deposits: float
    casa_deposits: float               # Current Account + Savings Account
    term_deposits: float | None = None

    # Equity
    total_equity: float                # Shareholders' funds (book value)
    shares_outstanding: float          # In Crores

    # Asset quality
    gross_npa: float
    net_npa: float


class MarketData(BaseModel):
    """Point-in-time market data snapshot.

    For the MVP, this is manually set. Future: real-time market data API.
    """

    current_price: float               # ₹ per share (CMP)
    market_cap: float                  # ₹ Crores
    shares_outstanding: float          # In Crores
    as_of: date


class FinancialData(BaseModel):
    """Complete financial dataset for a company.

    Bundles company profile, multi-year statements, market data, and provenance
    into a single object for downstream processing.
    """

    company: CompanyProfile
    provenance: DatasetProvenance | None = None
    income_statements: list[IncomeStatement]   # Ordered oldest → newest
    balance_sheets: list[BalanceSheet]          # Ordered oldest → newest
    market_data: MarketData
