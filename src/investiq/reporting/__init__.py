"""InvestIQ reporting package.

Generates interactive research reports from BigQuery-persisted data.
"""

from investiq.reporting.data import ReportData, ReportDataFetcher
from investiq.reporting.report import build_report, render_report

__all__ = [
    "ReportData",
    "ReportDataFetcher",
    "build_report",
    "render_report",
]