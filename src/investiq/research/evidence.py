"""EvidenceSet — a deduplicated, provenance-preserving collection of evidence.

Provides deterministic evidence IDs, deduplication by evidence_id,
preservation of provenance, lookup, and filtering by existing metadata.

This is the core abstraction for the Phase 3B evidence layer.
"""

from __future__ import annotations

from typing import Any, Iterator

from pydantic import BaseModel, Field

from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag


class EvidenceConflictError(ValueError):
    """Raised when two evidence items share the same evidence_id
    but have conflicting (non-identical) content.

    The error message includes both items so the caller can inspect
    the conflict and decide how to resolve it.
    """

    def __init__(
        self,
        evidence_id: str,
        existing: EvidenceItem,
        incoming: EvidenceItem,
    ) -> None:
        self.existing = existing
        self.incoming = incoming
        super().__init__(
            f"Evidence conflict for evidence_id '{evidence_id}': "
            f"existing={existing.model_dump(exclude={'timestamp', 'retrieved_at'})}, "
            f"incoming={incoming.model_dump(exclude={'timestamp', 'retrieved_at'})}"
        )


def _content_key(item: EvidenceItem) -> dict[str, Any]:
    """Return a canonical dict representing the logical content of an
    EvidenceItem, excluding time-sensitive fields (timestamp, retrieved_at)
    that should not affect deduplication decisions."""
    return item.model_dump(
        exclude={"timestamp", "retrieved_at"},
        exclude_none=True,
    )


class EvidenceSet(BaseModel):
    """A deduplicated, provenance-preserving collection of EvidenceItem objects.

    Provides:
    - Deterministic evidence IDs (preserved from source)
    - Deduplication by evidence_id (identical content → keep one)
    - Conflict detection (same ID, different content → EvidenceConflictError)
    - Lookup by evidence_id
    - Filtering by tag / source / source_field
    - Conversion back to list[EvidenceItem]

    Typical usage:
        items = [EvidenceItem(...), ...]
        ev_set = EvidenceSet(evidence=items)
        ev_set.get("SYN-HDFCBANK-ROE-001")
        ev_set.filter_by_tag(EvidenceTag.CALCULATION)
        ev_set.to_list()
    """

    items: dict[str, EvidenceItem] = Field(default_factory=dict)

    def __init__(self, evidence: list[EvidenceItem] | None = None) -> None:
        super().__init__(items={})
        if evidence is not None:
            for item in evidence:
                self.add(item)

    def add(self, item: EvidenceItem) -> None:
        """Add an evidence item, deduplicating by evidence_id.

        Raises:
            EvidenceConflictError: If the same evidence_id exists with
                                   conflicting (non-identical) content.
        """
        existing = self.items.get(item.evidence_id)
        if existing is not None:
            if _content_key(existing) == _content_key(item):
                # Identical content — skip duplicate silently.
                return
            raise EvidenceConflictError(
                evidence_id=item.evidence_id,
                existing=existing,
                incoming=item,
            )
        self.items[item.evidence_id] = item

    def get(self, evidence_id: str) -> EvidenceItem | None:
        """Look up an evidence item by its evidence_id."""
        return self.items.get(evidence_id)

    def filter_by_tag(self, tag: EvidenceTag) -> list[EvidenceItem]:
        """Return all evidence items with the given EvidenceTag."""
        return [it for it in self.items.values() if it.tag == tag]

    def filter_by_source(self, source: str) -> list[EvidenceItem]:
        """Return all evidence items whose source field contains the given string."""
        return [it for it in self.items.values() if source in (it.source or "")]

    def filter_by_source_field(self, source_field: str) -> list[EvidenceItem]:
        """Return all evidence items whose source_field contains the given string."""
        return [
            it
            for it in self.items.values()
            if source_field in (it.source_field or "")
        ]

    def to_list(self) -> list[EvidenceItem]:
        """Return all evidence items as a list, preserving insertion order."""
        return list(self.items.values())

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[EvidenceItem]:
        return iter(self.items.values())

    def __contains__(self, evidence_id: str) -> bool:
        return evidence_id in self.items

    def filter_by_domain(self, domain: EvidenceDomain) -> list[EvidenceItem]:
        """Return all evidence items with the given EvidenceDomain."""
        return [it for it in self.items.values() if it.domain == domain]