"""Synthetic evidence fixture for testing the Financial/Banking Analyst engine.

All evidence items are explicitly marked as SYNTHETIC.
Do not present synthetic evidence as real public information.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag


def _sanitize_ticker(ticker: str) -> str:
    """Normalize a ticker to uppercase, stripped."""
    return ticker.strip().upper()


def get_synthetic_bank_evidence(ticker: str) -> list[EvidenceItem]:
    """Return synthetic evidence items for a bank ticker.

    Each evidence ID is scoped to the requested ticker so that
    different companies produce non-overlapping evidence ID sets.

    Args:
        ticker: Bank ticker symbol (e.g., "HDFCBANK", "ICICIBANK", "SBIN").

    Returns:
        A list of five deterministic synthetic EvidenceItem objects
        keyed to the requested ticker.
    """
    ticker = _sanitize_ticker(ticker)
    now = datetime.now(timezone.utc)
    pub_date = date(2025, 4, 15)

    return [
        EvidenceItem(
            evidence_id=f"SYN-{ticker}-ROE-001",
            tag=EvidenceTag.CALCULATION,
            label="Return on Equity (ROE) FY2025",
            source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
            source_field="metrics.roe",
            source_url=f"https://investiq.internal/synthetic/{ticker}/FY2025/roe",
            publication_date=pub_date,
            retrieved_at=now,
            timestamp=now,
            value=15.42,  # 15.42%
            domain=EvidenceDomain.FINANCIAL,
        ),
        EvidenceItem(
            evidence_id=f"SYN-{ticker}-NIM-001",
            tag=EvidenceTag.CALCULATION,
            label="Net Interest Margin (NIM) FY2025",
            source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
            source_field="metrics.nim",
            source_url=f"https://investiq.internal/synthetic/{ticker}/FY2025/nim",
            publication_date=pub_date,
            retrieved_at=now,
            timestamp=now,
            value=3.48,  # 3.48%
            domain=EvidenceDomain.FINANCIAL,
        ),
        EvidenceItem(
            evidence_id=f"SYN-{ticker}-CASA-001",
            tag=EvidenceTag.CALCULATION,
            label="CASA Ratio FY2025",
            source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
            source_field="metrics.casa_ratio",
            source_url=f"https://investiq.internal/synthetic/{ticker}/FY2025/casa_ratio",
            publication_date=pub_date,
            retrieved_at=now,
            timestamp=now,
            value=34.96,  # 34.96%
            domain=EvidenceDomain.FINANCIAL,
        ),
        EvidenceItem(
            evidence_id=f"SYN-{ticker}-NPA-001",
            tag=EvidenceTag.CALCULATION,
            label="Gross NPA Ratio FY2025",
            source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
            source_field="metrics.gross_npa_ratio",
            source_url=f"https://investiq.internal/synthetic/{ticker}/FY2025/gross_npa_ratio",
            publication_date=pub_date,
            retrieved_at=now,
            timestamp=now,
            value=1.23,  # 1.23%
            domain=EvidenceDomain.ASSET_QUALITY,
        ),
        EvidenceItem(
            evidence_id=f"SYN-{ticker}-CC-001",
            tag=EvidenceTag.CALCULATION,
            label="Credit Cost FY2025",
            source="InvestIQ Bank Metrics Calculator (Synthetic Fixture)",
            source_field="metrics.credit_cost",
            source_url=f"https://investiq.internal/synthetic/{ticker}/FY2025/credit_cost",
            publication_date=pub_date,
            retrieved_at=now,
            timestamp=now,
            value=0.56,  # 0.56%
            domain=EvidenceDomain.ASSET_QUALITY,
        ),
    ]


def get_synthetic_hdfcbank_evidence() -> list[EvidenceItem]:
    """Backward-compatibility wrapper around get_synthetic_bank_evidence().

    Returns synthetic evidence for HDFCBANK.

    Deprecated: Use get_synthetic_bank_evidence(\"HDFCBANK\") directly.
    """
    return get_synthetic_bank_evidence("HDFCBANK")
