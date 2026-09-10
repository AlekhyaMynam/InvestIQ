"""Data loader — reads prepared JSON files into Pydantic models.

MVP implementation loads from local JSON files in data/prepared/.
The interface is designed so this can be swapped for a BigQuery
or API-based loader without changing downstream code.
"""

import json
from pathlib import Path

from investiq.models.financials import FinancialData


# Default data directory (relative to project root)
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "prepared"


def load_financial_data(
    ticker: str,
    data_dir: Path | None = None,
) -> FinancialData:
    """Load prepared financial data for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g., "HDFCBANK").
        data_dir: Directory containing prepared JSON files.
                  Defaults to <project_root>/data/prepared/.

    Returns:
        FinancialData: Validated financial data model.

    Raises:
        FileNotFoundError: If no prepared data file exists for the ticker.
        ValueError: If the JSON data fails Pydantic validation.
    """
    data_dir = data_dir or _DEFAULT_DATA_DIR
    file_path = data_dir / f"{ticker.upper()}.json"

    if not file_path.exists():
        raise FileNotFoundError(
            f"No prepared data found for ticker '{ticker}'. "
            f"Expected file: {file_path}"
        )

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    try:
        return FinancialData.model_validate(raw_data)
    except Exception as e:
        raise ValueError(
            f"Failed to validate financial data for '{ticker}': {e}"
        ) from e
