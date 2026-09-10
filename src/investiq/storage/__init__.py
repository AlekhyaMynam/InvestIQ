"""Storage layer for InvestIQ research persistence.

Provides repository abstractions for storing ResearchSnapshot data
in BigQuery for Looker dashboards and Firebase consumption.
"""

from investiq.storage.bigquery import BigQueryResearchRepository
from investiq.storage.fake import FakeBigQueryResearchRepository

__all__ = [
    "BigQueryResearchRepository",
    "FakeBigQueryResearchRepository",
]