from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


class PersistentQueueManager:
    """Utility for inspecting and maintaining the persistent delivery queue.

    Parameters
    ----------
    db_path:
        Path to the SQLite database used by :class:`PersistentDelivery`.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        """Return counts of messages grouped by status."""

        with self._connect() as conn:
            cur = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM queue GROUP BY status"
            )
            return {row["status"]: row["cnt"] for row in cur.fetchall()}

    # ------------------------------------------------------------------
    def list_failed(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return failed queue items.

        Parameters
        ----------
        limit:
            Maximum number of rows to return.
        """

        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM queue WHERE status='failed' ORDER BY id LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    def requeue_failed(self, ids: Iterable[int] | None = None) -> int:
        """Move failed items back to the queued state.

        Parameters
        ----------
        ids:
            Optional iterable of row IDs to requeue. If omitted, all failed
            items are requeued.
        Returns
        -------
        int
            Number of rows updated.
        """

        ids_list = list(ids) if ids is not None else None
        with self._connect() as conn:
            now = time.time()
            if ids_list:
                placeholders = ",".join("?" for _ in ids_list)
                conn.execute(
                    f"UPDATE queue SET status='queued', retry_count=0, scheduled_at=?, updated_at=? "
                    f"WHERE status='failed' AND id IN ({placeholders})",
                    [now, now, *ids_list],
                )
            else:
                conn.execute(
                    "UPDATE queue SET status='queued', retry_count=0, scheduled_at=?, updated_at=? "
                    "WHERE status='failed'",
                    (now, now),
                )
            conn.commit()
            return conn.total_changes

    # ------------------------------------------------------------------
    def purge_failed(self, ids: Iterable[int] | None = None) -> int:
        """Delete failed items from the queue.

        Parameters
        ----------
        ids:
            Optional iterable of row IDs to delete. If omitted, all failed items
            are removed.
        Returns
        -------
        int
            Number of rows deleted.
        """

        ids_list = list(ids) if ids is not None else None
        with self._connect() as conn:
            if ids_list:
                placeholders = ",".join("?" for _ in ids_list)
                conn.execute(
                    f"DELETE FROM queue WHERE status='failed' AND id IN ({placeholders})",
                    ids_list,
                )
            else:
                conn.execute("DELETE FROM queue WHERE status='failed'")
            conn.commit()
            return conn.total_changes
