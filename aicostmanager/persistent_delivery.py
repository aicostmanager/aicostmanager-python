from __future__ import annotations

import configparser
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    stop_after_attempt,
    wait_exponential_jitter,
)


class PersistentDelivery:
    """Durable queue based delivery using SQLite.

    The queue is stored in a local SQLite database configured for WAL mode to
    survive restarts and power loss. A background worker pulls messages and
    delivers them to the server. Immediate synchronous delivery is available via
    :meth:`deliver_now`.
    """

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
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        max_attempts: int = 3,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.ini_path = (
            aicm_ini_path
            or os.getenv("AICM_INI_PATH")
            or str(Path.home() / ".config" / "aicostmanager" / "AICM.INI")
        )

        cp = configparser.ConfigParser()
        if os.path.exists(self.ini_path):
            cp.read(self.ini_path)

        def _cfg(env: str, section: str, option: str, default: Optional[str]) -> Optional[str]:
            if env and (val := os.getenv(env)):
                return val
            if cp.has_section(section) and option in cp[section]:
                return cp[section][option]
            return default

        self.db_path = db_path or _cfg(
            "AICM_DELIVERY_DB_PATH", "delivery", "db_path", str(
                Path.home() / ".cache" / "aicostmanager" / "delivery_queue.db"
            )
        )
        self.log_file = log_file or _cfg(
            "AICM_DELIVERY_LOG_FILE", "delivery", "log_file", None
        )
        self.log_level = (log_level or _cfg(
            "AICM_DELIVERY_LOG_LEVEL", "delivery", "log_level", "INFO"
        )).upper()

        if self.log_file:
            log_dir = os.path.dirname(self.log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            logging.basicConfig(
                filename=self.log_file,
                level=getattr(logging, self.log_level, logging.INFO),
                format="%(asctime)s %(levelname)s %(message)s",
            )
        else:
            logging.basicConfig(
                level=getattr(logging, self.log_level, logging.INFO),
                format="%(asctime)s %(levelname)s %(message)s",
            )

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
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.max_attempts = max_attempts
        self.timeout = timeout
        self._transport = transport
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._endpoint = (
            self.api_base.rstrip("/") + self.api_url.rstrip("/") + "/track"
        )
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------
    # Queue helpers
    def enqueue(self, payload: Dict[str, Any]) -> int:
        """Persist a payload to the queue."""
        now = time.time()
        data = json.dumps(payload)
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO queue (payload, status, retry_count, scheduled_at, created_at, updated_at) VALUES (?, 'queued', 0, ?, ?, ?)",
                (data, now, now, now),
            )
            self.conn.commit()
            return cur.lastrowid

    def _get_next(self) -> Optional[sqlite3.Row]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM queue WHERE status='queued' AND scheduled_at <= ? ORDER BY id LIMIT 1",
                (time.time(),),
            ).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE queue SET status='processing', updated_at=? WHERE id=?",
                    (time.time(), row["id"]),
                )
                self.conn.commit()
            return row

    def _reschedule(self, row_id: int, retry_count: int) -> None:
        if retry_count >= self.max_retries:
            status = "failed"
            scheduled = time.time()
        else:
            status = "queued"
            scheduled = time.time() + min(2 ** retry_count, 300)
        with self._lock:
            self.conn.execute(
                "UPDATE queue SET status=?, retry_count=?, scheduled_at=?, updated_at=? WHERE id=?",
                (status, retry_count, scheduled, time.time(), row_id),
            )
            self.conn.commit()

    def _delete(self, row_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM queue WHERE id=?", (row_id,))
            self.conn.commit()

    # ------------------------------------------------------------------
    # Worker
    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            row = self._get_next()
            if not row:
                time.sleep(self.poll_interval)
                continue
            payload = json.loads(row["payload"])
            try:
                self.deliver_now(payload)
                self._delete(row["id"])
            except Exception:
                retry = row["retry_count"] + 1
                logging.exception("Delivery failed for queued item %s", row["id"])
                self._reschedule(row["id"], retry)

    # ------------------------------------------------------------------
    # Delivery methods
    def _send_once(self, payload: Dict[str, Any]) -> None:
        resp = self._client.post(
            self._endpoint, json=payload, headers=self._headers
        )
        resp.raise_for_status()

    def deliver_now(self, payload: Dict[str, Any]) -> None:
        """Send a payload immediately with retries."""
        for attempt in Retrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1, max=10),
        ):
            with attempt:
                self._send_once(payload)

    async def deliver_now_async(self, payload: Dict[str, Any]) -> None:
        async def _send() -> None:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                resp = await client.post(
                    self._endpoint, json=payload, headers=self._headers
                )
                resp.raise_for_status()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1, max=10),
        ):
            with attempt:
                await _send()

    # ------------------------------------------------------------------
    # Monitoring
    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT status, COUNT(*) as c FROM queue GROUP BY status"
            )
            stats = {row["status"]: row["c"] for row in cur.fetchall()}
        return stats

    def list_messages(self, status: str = "queued", limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT id, payload, retry_count, scheduled_at FROM queue WHERE status=? ORDER BY id LIMIT ?",
                (status, limit),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "retry_count": row["retry_count"],
                    "scheduled_at": row["scheduled_at"],
                    "payload": json.loads(row["payload"]),
                }
            )
        return result

    def health(self) -> Dict[str, Any]:
        data = self.get_stats()
        data["worker_alive"] = self._worker.is_alive()
        return data

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_event.set()
        self._worker.join(timeout=5)
        self._client.close()
        self.conn.close()
