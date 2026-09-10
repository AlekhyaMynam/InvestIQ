"""Company profile and classification models.

CompanyType drives sector-specific research frameworks and valuation models.
"""

from enum import Enum

from pydantic import BaseModel


class Sector(str, Enum):
    """High-level sector classification."""

    FINANCIAL_SERVICES = "financial_services"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    CONSUMER = "consumer"
    INDUSTRIALS = "industrials"
    ENERGY = "energy"


class CompanyType(str, Enum):
    """Specific company type — drives framework and valuation model selection.

    This enum determines which calculators, research frameworks, and
    valuation models are applied to a company.
    """

    BANK = "BANK"
    NBFC = "NBFC"
    IT = "IT"
    PHARMA = "PHARMA"
    FMCG = "FMCG"


class CompanyProfile(BaseModel):
    """Core company identification and classification.

    Attributes:
        ticker: Exchange ticker symbol (e.g., "HDFCBANK").
        name: Full legal name of the company.
        sector: High-level sector (e.g., FINANCIAL_SERVICES).
        company_type: Specific type driving framework selection (e.g., BANK).
        sub_sector: Optional sub-sector detail (e.g., "Private Sector Bank").
        isin: International Securities Identification Number.
        bse_code: BSE scrip code.
        nse_symbol: NSE trading symbol.
    """

    ticker: str
    name: str
    sector: Sector
    company_type: CompanyType
    sub_sector: str | None = None
    isin: str | None = None
    bse_code: str | None = None
    nse_symbol: str | None = None
