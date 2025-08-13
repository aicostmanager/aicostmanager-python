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

logger = logging.getLogger(__name__)


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
        logger: Optional[logging.Logger] = None,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        batch_interval: float = 0.5,
        max_attempts: int = 3,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
        log_bodies: bool = False,
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

        self.logger = logger or logging.getLogger(__name__)
        globals()["logger"] = self.logger
        self.logger.setLevel(getattr(logging, self.log_level, logging.INFO))
        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            if self.log_file:
                log_dir = os.path.dirname(self.log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                handler = logging.FileHandler(self.log_file)
            else:
                handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

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
        self.batch_interval = batch_interval
        self.max_retries = max_retries
        self.max_attempts = max_attempts
        self.timeout = timeout
        self._transport = transport
        env_log_bodies = os.getenv("AICM_DELIVERY_LOG_BODIES", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.log_bodies = log_bodies or env_log_bodies
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
            msg_id = cur.lastrowid
        logger.debug("Enqueued message id=%s", msg_id)
        return msg_id

    def _get_batch(self, limit: int = 100) -> List[sqlite3.Row]:
        """Fetch up to ``limit`` queued rows and mark them processing."""
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
        if rows and logger.isEnabledFor(logging.DEBUG):
            ids = ", ".join(str(row["id"]) for row in rows)
            logger.debug("Fetched %d messages for processing: %s", len(rows), ids)
        return rows

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
        logger.debug(
            "Rescheduled message id=%s retry=%s status=%s next_at=%.2f",
            row_id,
            retry_count,
            status,
            scheduled,
        )

    def _delete(self, row_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM queue WHERE id=?", (row_id,))
            self.conn.commit()
        logger.debug("Deleted message id=%s", row_id)

    def _flush_buffer(self, buffer: List[sqlite3.Row]) -> None:
        """Send and remove all messages currently in ``buffer``.

        Any failures will reschedule the affected messages for a later
        attempt. The ``buffer`` list is cleared in all cases.
        """
        if not buffer:
            return
        if logger.isEnabledFor(logging.DEBUG):
            ids = ", ".join(str(row["id"]) for row in buffer)
            logger.debug("Flushing %d messages: %s", len(buffer), ids)
        payloads = [json.loads(row["payload"]) for row in buffer]
        try:
            self.deliver_batch(payloads)
            for row in buffer:
                self._delete(row["id"])
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Delivered %d messages", len(buffer))
        except Exception:
            logger.exception("Batch delivery failed")
            for row in buffer:
                retry = row["retry_count"] + 1
                self._reschedule(row["id"], retry)
        buffer.clear()

    # ------------------------------------------------------------------
    # Worker
    def _run_worker(self) -> None:
        logger.debug("Worker thread started")
        buffer: List[sqlite3.Row] = []
        first_ts: float | None = None
        while not self._stop_event.is_set():
            needed = 100 - len(buffer)
            if needed > 0:
                rows = self._get_batch(needed)
                if rows:
                    buffer.extend(rows)
                    if first_ts is None:
                        first_ts = time.time()

            should_flush = False
            if buffer:
                if len(buffer) >= 100:
                    should_flush = True
                elif first_ts is not None and (time.time() - first_ts) >= self.batch_interval:
                    should_flush = True

            if should_flush:
                self._flush_buffer(buffer)
                first_ts = None
                continue

            if buffer and first_ts is not None:
                remaining = self.batch_interval - (time.time() - first_ts)
                sleep_for = max(0, min(self.poll_interval, remaining))
            else:
                sleep_for = self.poll_interval
            time.sleep(sleep_for)

        # Final flush when stopping to ensure no messages are dropped
        if buffer:
            self._flush_buffer(buffer)
        logger.debug("Worker thread stopping")

    # ------------------------------------------------------------------
    # Helpers
    def _redact(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: ("<redacted>" if k.lower() in {"authorization", "api_key", "apikey"} else self._redact(v))
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._redact(v) for v in data]
        return data

    # ------------------------------------------------------------------
    # Delivery methods
    def _send_batch_once(self, payloads: List[Dict[str, Any]]) -> httpx.Response:
        body = {"tracked": payloads}
        payload_size = len(json.dumps(body).encode("utf-8"))
        logger.debug(
            "Sending %d payload(s) (%d bytes) to %s",
            len(payloads),
            payload_size,
            self._endpoint,
        )
        if self.log_bodies:
            logger.debug("Request body: %s", self._redact(body))
        resp = self._client.post(
            self._endpoint, json=body, headers=self._headers
        )
        if self.log_bodies:
            try:
                logger.debug("Response body: %s", self._redact(resp.json()))
            except Exception:
                logger.debug("Response body: %s", self._redact(resp.text))
        try:
            resp.raise_for_status()
            logger.info(
                "Batch delivered to %s with status %s",
                self._endpoint,
                resp.status_code,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Error delivering batch to %s: status %s body %s",
                self._endpoint,
                e.response.status_code,
                self._redact(e.response.text),
            )
            raise
        return resp

    def deliver_batch(self, payloads: List[Dict[str, Any]]) -> httpx.Response:
        """Send a batch of payloads immediately with retries."""
        for attempt in Retrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1, max=10),
        ):
            with attempt:
                return self._send_batch_once(payloads)
        # Retrying guarantees a return or raise, but mypy
        raise RuntimeError("unreachable")

    def deliver_now(self, payload: Dict[str, Any]) -> httpx.Response:
        """Send a single payload immediately."""
        return self.deliver_batch([payload])

    async def _send_batch_async(self, payloads: List[Dict[str, Any]]) -> httpx.Response:
        body = {"tracked": payloads}
        payload_size = len(json.dumps(body).encode("utf-8"))
        logger.debug(
            "Sending %d payload(s) (%d bytes) to %s",
            len(payloads),
            payload_size,
            self._endpoint,
        )
        if self.log_bodies:
            logger.debug("Request body: %s", self._redact(body))
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            resp = await client.post(
                self._endpoint, json=body, headers=self._headers
            )
        if self.log_bodies:
            try:
                logger.debug("Response body: %s", self._redact(resp.json()))
            except Exception:
                logger.debug("Response body: %s", self._redact(resp.text))
        try:
            resp.raise_for_status()
            logger.info(
                "Batch delivered to %s with status %s",
                self._endpoint,
                resp.status_code,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Error delivering batch to %s: status %s body %s",
                self._endpoint,
                e.response.status_code,
                self._redact(e.response.text),
            )
            raise
        return resp

    async def deliver_batch_async(self, payloads: List[Dict[str, Any]]) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1, max=10),
        ):
            with attempt:
                return await self._send_batch_async(payloads)
        raise RuntimeError("unreachable")

    async def deliver_now_async(self, payload: Dict[str, Any]) -> httpx.Response:
        return await self.deliver_batch_async([payload])

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
