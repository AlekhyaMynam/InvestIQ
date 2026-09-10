"""Fake BigQuery repository for testing — no cloud dependencies.

Stores snapshots in memory for verification purposes.
Tests must NOT require live BigQuery credentials.
"""

from __future__ import annotations

from investiq.models.research import ResearchSnapshot


class FakeBigQueryResearchRepository:
    """In-memory fake that mimics BigQueryResearchRepository for testing.

    Stores ResearchSnapshot data in memory dictionaries keyed by snapshot_id.
    All methods are synchronous and require no network access.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, ResearchSnapshot] = {}
        self.saved_snapshots: list[ResearchSnapshot] = []

    def save_snapshot(self, snapshot: ResearchSnapshot) -> None:
        """Store a snapshot in memory and record the save."""
        self._snapshots[snapshot.snapshot_id] = snapshot
        self.saved_snapshots.append(snapshot)

    @property
    def save_count(self) -> int:
        """Number of times save_snapshot was called."""
        return len(self.saved_snapshots)

    def get_snapshot(self, snapshot_id: str) -> ResearchSnapshot | None:
        """Retrieve a saved snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def clear(self) -> None:
        """Reset all stored data."""
        self._snapshots.clear()
        self.saved_snapshots.clear()