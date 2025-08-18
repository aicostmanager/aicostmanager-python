from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List

from .base import DeliveryConfig, DeliveryType, QueueDelivery, QueueItem


class PersistentDelivery(QueueDelivery):
    """Durable queue based delivery using SQLite."""

    type = DeliveryType.PERSISTENT_QUEUE

    def __init__(
        self,
        *,
        config: DeliveryConfig,
        db_path: str,
        poll_interval: float = 1.0,
        batch_interval: float = 0.5,
        max_attempts: int = 3,
        max_retries: int = 5,
        log_bodies: bool = False,
        max_batch_size: int = 100,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            config,
            batch_interval=batch_interval,
            max_batch_size=max_batch_size,
            max_attempts=max_attempts,
            max_retries=max_retries,
            logger=logger,
        )
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.log_bodies = log_bodies

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    scheduled_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
        self._lock = threading.Lock()

    def enqueue(self, payload: Dict[str, Any]) -> int:
        now = time.time()
        data = json.dumps(payload)
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO queue (payload, status, retry_count, scheduled_at, created_at, updated_at) VALUES (?, 'queued', 0, ?, ?, ?)",
                (data, now, now, now),
            )
            self.conn.commit()
            msg_id = cur.lastrowid
        self.logger.debug("Enqueued message id=%s", msg_id)
        return msg_id

    def get_batch(self, max_batch_size: int, *, block: bool = True) -> List[QueueItem]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM queue WHERE status='queued' AND scheduled_at <= ? ORDER BY id LIMIT ?",
                (time.time(), max_batch_size),
            )
            rows = cur.fetchall()
            if rows:
                now = time.time()
                self.conn.executemany(
                    "UPDATE queue SET status='processing', updated_at=? WHERE id=?",
                    [(now, row["id"]) for row in rows],
                )
                self.conn.commit()
        if not rows:
            if block:
                time.sleep(self.poll_interval)
            return []
        if self.logger.isEnabledFor(logging.DEBUG):
            ids = ", ".join(str(row["id"]) for row in rows)
            self.logger.debug("Fetched %d messages for processing: %s", len(rows), ids)
        return [QueueItem(id=row["id"], payload=json.loads(row["payload"]), retry_count=row["retry_count"]) for row in rows]

    def acknowledge(self, items: List[QueueItem]) -> None:
        ids = [(item.id,) for item in items if item.id is not None]
        if not ids:
            return
        with self._lock:
            self.conn.executemany("DELETE FROM queue WHERE id=?", ids)
            self.conn.commit()
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Delivered %d messages", len(ids))

    def reschedule(self, item: QueueItem) -> None:
        retry_count = item.retry_count
        if retry_count >= self.max_retries:
            status = "failed"
            scheduled = time.time()
        else:
            status = "queued"
            scheduled = time.time() + min(2**retry_count, 300)
        with self._lock:
            self.conn.execute(
                "UPDATE queue SET status=?, retry_count=?, scheduled_at=?, updated_at=? WHERE id=?",
                (status, retry_count, scheduled, time.time(), item.id),
            )
            self.conn.commit()
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Rescheduled message id=%s retry=%s status=%s next_at=%.2f",
                item.id,
                retry_count,
                status,
                scheduled,
            )

    def queued(self) -> int:
        with self._lock:
            cur = self.conn.execute("SELECT COUNT(*) FROM queue WHERE status='queued'")
            (count,) = cur.fetchone()
        return int(count)

    def stop(self) -> None:
        super().stop()
        self.conn.close()
