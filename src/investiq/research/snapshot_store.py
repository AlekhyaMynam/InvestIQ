"""ResearchSnapshotStore — local JSON persistence for ResearchSnapshot objects.

Saves and loads ResearchSnapshot instances to/from JSON files on the local
filesystem. All operations are deterministic and make zero external API calls.

File naming: <snapshot_id>.json
Storage:     single flat directory

This is the Phase 3C.1 persistence layer.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from investiq.models.research import ResearchSnapshot


# A snapshot_id must match this pattern to be considered valid.
# UUIDs are the expected format, but we accept any identifier that
# does not contain path traversal sequences.
_VALID_SNAPSHOT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-.]+$")


def _validate_snapshot_id(snapshot_id: str) -> None:
    """Validate a snapshot_id to prevent path traversal.

    Raises:
        ValueError: If the snapshot_id contains characters that could
                    be used for directory traversal.
    """
    if not snapshot_id or not isinstance(snapshot_id, str):
        raise ValueError(f"Invalid snapshot_id: {snapshot_id!r}")
    if not _VALID_SNAPSHOT_ID_RE.match(snapshot_id):
        raise ValueError(
            f"Snapshot ID {snapshot_id!r} contains invalid characters. "
            f"Only alphanumeric, underscore, hyphen, and dot are allowed."
        )

class ResearchSnapshotStore:
    """Local filesystem persistence for ResearchSnapshot objects.

    Stores each snapshot as a single JSON file named <snapshot_id>.json
    in a configurable directory.

    Attributes:
        store_dir: Absolute Path to the directory where snapshot files
                   are stored. Created on __init__ if it does not exist.
    """

    def __init__(self, store_dir: str | Path) -> None:
        """Initialize the store.

        Args:
            store_dir: Directory path for snapshot storage. Created if
                       it does not exist.

        Raises:
            OSError: If the directory cannot be created.
        """
        self.store_dir = Path(store_dir).resolve(strict=False)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, snapshot: ResearchSnapshot) -> Path:
        """Serialize and persist a ResearchSnapshot to a JSON file.

        Writes atomically by writing to a temporary file in the same
        directory, then renaming over the target.

        Args:
            snapshot: The ResearchSnapshot to persist.

        Returns:
            The absolute Path to the written JSON file.

        Raises:
            OSError: If file writing fails.
        """
        _validate_snapshot_id(snapshot.snapshot_id)
        target = self._path_for(snapshot.snapshot_id)
        json_bytes = snapshot.model_dump_json(
            indent=2,
            by_alias=False,
            exclude_none=False,
        ).encode("utf-8")

        # Atomic write: temp file -> rename
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            prefix=f".{snapshot.snapshot_id}_",
            dir=self.store_dir,
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(json_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

        return target

    def load(self, snapshot_id: str) -> ResearchSnapshot:
        """Load and reconstruct a ResearchSnapshot from its JSON file.

        Args:
            snapshot_id: The unique identifier of the snapshot to load.

        Returns:
            A fully validated ResearchSnapshot instance.

        Raises:
            FileNotFoundError: If no snapshot with the given ID exists.
            ValueError: If the snapshot_id is invalid.
            pydantic.ValidationError: If the stored JSON is malformed.
        """
        _validate_snapshot_id(snapshot_id)
        path = self._path_for(snapshot_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Snapshot {snapshot_id!r} not found at {path}"
            )
        raw = path.read_bytes()
        return ResearchSnapshot.model_validate_json(raw)

    def exists(self, snapshot_id: str) -> bool:
        """Check whether a snapshot with the given ID exists.

        Args:
            snapshot_id: The unique identifier to check.

        Returns:
            True if the snapshot file exists, False otherwise.
        """
        _validate_snapshot_id(snapshot_id)
        return self._path_for(snapshot_id).exists()

    def list_snapshots(self) -> list[str]:
        """Return snapshot IDs for all valid snapshot files, sorted.

        Scans the store directory for files matching <id>.json and
        extracts the snapshot ID portion. Does NOT load any snapshot
        into memory.

        Returns:
            A sorted list of snapshot ID strings.
        """
        result: list[str] = []
        if not self.store_dir.is_dir():
            return result

        for entry in self.store_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() != ".json":
                continue
            sid = entry.stem
            if not sid or sid.startswith("."):
                continue
            try:
                _validate_snapshot_id(sid)
            except ValueError:
                continue
            result.append(sid)

        result.sort()
        return result

    def delete(self, snapshot_id: str) -> None:
        """Delete a snapshot file.

        Args:
            snapshot_id: The unique identifier of the snapshot to delete.

        Raises:
            FileNotFoundError: If no snapshot with the given ID exists.
            ValueError: If the snapshot_id is invalid.
        """
        _validate_snapshot_id(snapshot_id)
        path = self._path_for(snapshot_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Snapshot {snapshot_id!r} not found at {path}"
            )
        path.unlink()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, snapshot_id: str) -> Path:
        """Return the expected file path for a given snapshot_id."""
        return self.store_dir / f"{snapshot_id}.json"