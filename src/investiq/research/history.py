"""ResearchHistoryService — thin orchestration over ResearchSnapshotStore and
ResearchDeltaCalculator.

Provides ticker-scoped history queries, chronological ordering, and
comparison of the latest two snapshots for a given ticker.

All operations are deterministic and make zero external API calls.
"""

from __future__ import annotations

from investiq.models.research import ResearchDelta, ResearchSnapshot
from investiq.research.delta import ResearchDeltaCalculator
from investiq.research.snapshot_store import ResearchSnapshotStore


class ResearchHistoryService:
    """Orchestrates snapshot store and delta calculator for ticker history.

    Responsibilities:
    - Finding snapshots belonging to a ticker (case-insensitive)
    - Ordering them chronologically by generated_at
    - Identifying the latest and immediately previous snapshots
    - Comparing the latest two snapshots

    Attributes:
        store: The ResearchSnapshotStore backing this service.
    """

    def __init__(self, store: ResearchSnapshotStore) -> None:
        """Initialize the service.

        Args:
            store: An existing ResearchSnapshotStore instance.
        """
        self.store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_for_ticker(self, ticker: str) -> list[ResearchSnapshot]:
        """Return all snapshots for the given ticker, chronologically ordered.

        Args:
            ticker: Company ticker symbol (case-insensitive).

        Returns:
            List of ResearchSnapshot objects ordered oldest → newest by
            generated_at. Snapshots with identical timestamps are ordered
            deterministically by snapshot_id.
        """
        matching = self._load_snapshots_for_ticker(ticker)
        matching.sort(key=lambda s: (s.generated_at, s.snapshot_id))
        return matching

    def get_latest(self, ticker: str) -> ResearchSnapshot | None:
        """Return the newest snapshot for the ticker, or None if none exist.

        Args:
            ticker: Company ticker symbol (case-insensitive).

        Returns:
            The most recent ResearchSnapshot, or None.
        """
        all_snaps = self.list_for_ticker(ticker)
        if not all_snaps:
            return None
        return all_snaps[-1]

    def get_previous(self, ticker: str) -> ResearchSnapshot | None:
        """Return the snapshot immediately before the latest, or None.

        Args:
            ticker: Company ticker symbol (case-insensitive).

        Returns:
            The second-most-recent ResearchSnapshot, or None if fewer
            than 2 snapshots exist.
        """
        all_snaps = self.list_for_ticker(ticker)
        if len(all_snaps) < 2:
            return None
        return all_snaps[-2]

    def compare_latest(self, ticker: str) -> ResearchDelta | None:
        """Compare the latest two snapshots for the ticker.

        Args:
            ticker: Company ticker symbol (case-insensitive).

        Returns:
            A ResearchDelta if at least 2 snapshots exist, otherwise None.
        """
        all_snaps = self.list_for_ticker(ticker)
        if len(all_snaps) < 2:
            return None
        previous = all_snaps[-2]
        current = all_snaps[-1]
        return ResearchDeltaCalculator.compare(previous, current)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_snapshots_for_ticker(self, ticker: str) -> list[ResearchSnapshot]:
        """Load all snapshots and filter by ticker (case-insensitive)."""
        ticker_upper = ticker.strip().upper()
        snapshot_ids = self.store.list_snapshots()
        result: list[ResearchSnapshot] = []
        for sid in snapshot_ids:
            snap = self.store.load(sid)
            if snap.ticker.strip().upper() == ticker_upper:
                result.append(snap)
        return result