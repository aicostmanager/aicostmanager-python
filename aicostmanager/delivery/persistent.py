from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .base import Delivery
from ..ini_manager import IniManager


class PersistentDelivery(Delivery):
    """Durable queue based delivery using SQLite."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        db_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log_level: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        batch_interval: float = 0.5,
        max_attempts: int = 3,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
        log_bodies: bool = False,
        ini_manager: IniManager | None = None,
    ) -> None:
        ini_path = IniManager.resolve_path(aicm_ini_path)
        ini_manager = ini_manager or IniManager(ini_path)
        super().__init__(
            ini_manager=ini_manager,
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            timeout=timeout,
            transport=transport,
            log_file=log_file,
            log_level=log_level,
            logger=logger,
        )
        self.db_path = db_path or self.ini_manager.get_option(
            "delivery",
            "db_path",
            str(Path.home() / ".cache" / "aicostmanager" / "delivery_queue.db"),
        )
        self.poll_interval = poll_interval
        self.batch_interval = batch_interval
        self.max_attempts = max_attempts
        self.max_retries = max_retries
        env_log_bodies = os.getenv("AICM_DELIVERY_LOG_BODIES", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.log_bodies = log_bodies or env_log_bodies

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
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()

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

    def _get_batch(self, limit: int = 100) -> List[sqlite3.Row]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM queue WHERE status='queued' AND scheduled_at <= ? ORDER BY id LIMIT ?",
                (time.time(), limit),
            )
            rows = cur.fetchall()
            if rows:
                now = time.time()
                self.conn.executemany(
                    "UPDATE queue SET status='processing', updated_at=? WHERE id=?",
                    [(now, row["id"]) for row in rows],
                )
                self.conn.commit()
        if rows and self.logger.isEnabledFor(logging.DEBUG):
            ids = ", ".join(str(row["id"]) for row in rows)
            self.logger.debug("Fetched %d messages for processing: %s", len(rows), ids)
        return rows

    def _reschedule(self, row_id: int, retry_count: int) -> None:
        if retry_count >= self.max_retries:
            status = "failed"
            scheduled = time.time()
        else:
            status = "queued"
            scheduled = time.time() + min(2**retry_count, 300)
        with self._lock:
            self.conn.execute(
                "UPDATE queue SET status=?, retry_count=?, scheduled_at=?, updated_at=? WHERE id=?",
                (status, retry_count, scheduled, time.time(), row_id),
            )
            self.conn.commit()
        self.logger.debug(
            "Rescheduled message id=%s retry=%s status=%s next_at=%.2f",
            row_id,
            retry_count,
            status,
            scheduled,
        )

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            rows = self._get_batch()
            if not rows:
                time.sleep(self.poll_interval)
                continue
            payloads: List[Dict[str, Any]] = []
            ids: List[int] = []
            for row in rows:
                payloads.append(json.loads(row["payload"]))
                ids.append(row["id"])
            body = {self._body_key: payloads}
            try:
                self._post_with_retry(body, max_attempts=self.max_attempts)
            except Exception as exc:
                self.logger.error("Delivery failed: %s", exc)
                for row, _payload in zip(rows, payloads):
                    self._reschedule(row["id"], row["retry_count"] + 1)
            else:
                with self._lock:
                    self.conn.executemany(
                        "DELETE FROM queue WHERE id=?",
                        [(row_id,) for row_id in ids],
                    )
                    self.conn.commit()
                self.logger.debug("Delivered %d messages", len(ids))
            time.sleep(self.batch_interval)

    def stop(self) -> None:
        self._stop_event.set()
        self._worker.join()
        self._client.close()
        self.conn.close()
