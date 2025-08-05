"""Background delivery helpers for ``CostManager``.

This module provides a simple thread based queue that batches payloads
and retries failed requests using ``tenacity``.  A single global queue
is shared across all ``CostManager`` instances to avoid the overhead of
creating a new worker per wrapper.
"""

from __future__ import annotations

import configparser
import json
import os
import queue
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Any, Optional

from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from .client import CostManagerClient

_global_delivery: "ResilientDelivery" | None = None


@contextmanager
def _file_lock(file_path: str):
    """Context manager for file locking to prevent race conditions."""
    # Handle empty or None file paths
    if not file_path:
        yield
        return

    lock_file = f"{file_path}.lock"

    # Handle directory creation more carefully
    dir_path = os.path.dirname(file_path)
    if dir_path:  # Only create directory if it's not empty
        os.makedirs(dir_path, exist_ok=True)

    # Retry mechanism for lock acquisition
    max_retries = 10
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if attempt == max_retries - 1:
                # Force remove stale lock if it's too old (>30 seconds)
                try:
                    stat = os.stat(lock_file)
                    if time.time() - stat.st_mtime > 30:
                        os.unlink(lock_file)
                        continue
                except (OSError, FileNotFoundError):
                    pass
                raise RuntimeError(f"Could not acquire lock for {file_path}")
            time.sleep(retry_delay * (2**attempt))  # Exponential backoff

    try:
        yield
    finally:
        try:
            os.close(lock_fd)
            os.unlink(lock_file)
        except (OSError, FileNotFoundError):
            pass


def _safe_read_config(ini_path: str) -> configparser.ConfigParser:
    """Safely read a ConfigParser, handling duplicate sections."""
    config = configparser.ConfigParser(allow_no_value=True, strict=False)

    if not os.path.exists(ini_path):
        return config

    # Read and clean the INI file if it has duplicates
    try:
        config.read(ini_path)
        return config
    except configparser.DuplicateSectionError:
        # Handle duplicate sections by cleaning the file
        _clean_duplicate_sections(ini_path)
        config = configparser.ConfigParser(allow_no_value=True, strict=False)
        config.read(ini_path)
        return config


def _clean_duplicate_sections(ini_path: str):
    """Remove duplicate sections from INI file, keeping the last occurrence."""
    if not os.path.exists(ini_path):
        return

    # Read the file and remove duplicates
    seen_sections = set()
    cleaned_lines = []
    current_section = None
    section_content = []

    with open(ini_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Found a section header
            if current_section is not None:
                # Save previous section if it's the first occurrence
                if current_section not in seen_sections:
                    cleaned_lines.extend(section_content)
                    seen_sections.add(current_section)
                section_content = []

            current_section = stripped
            section_content = [line]
        else:
            section_content.append(line)

    # Handle the last section
    if current_section is not None:
        if current_section not in seen_sections:
            cleaned_lines.extend(section_content)

    # Write cleaned content atomically
    _atomic_write(ini_path, "".join(cleaned_lines))


def _atomic_write(file_path: str, content: str):
    """Atomically write content to a file."""
    # Handle empty or None file paths
    if not file_path:
        return

    # Handle directory creation more carefully
    dir_path = os.path.dirname(file_path)
    if dir_path:  # Only create directory if it's not empty
        os.makedirs(dir_path, exist_ok=True)

    # Write to a temporary file first
    temp_dir = dir_path if dir_path else "."  # Use current directory if no dir_path
    temp_fd, temp_path = tempfile.mkstemp(
        dir=temp_dir, prefix=f".{os.path.basename(file_path)}.tmp"
    )

    try:
        with os.fdopen(temp_fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename
        os.rename(temp_path, file_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass
        raise


def get_global_delivery(
    client: CostManagerClient,
    *,
    max_retries: int = 5,
    queue_size: int = 1000,
    endpoint: str = "/track-usage",
    timeout: float = 10.0,
) -> "ResilientDelivery":
    """Return the shared delivery queue initialised with ``client``.

    The first caller creates the queue which is then reused by all
    subsequent ``CostManager`` instances.  The worker thread is started on
    creation.
    """
    global _global_delivery
    if _global_delivery is None:
        _global_delivery = ResilientDelivery(
            client.session,
            client.api_root,
            max_retries=max_retries,
            queue_size=queue_size,
            endpoint=endpoint,
            timeout=timeout,
            ini_path=client.ini_path,
        )
        _global_delivery.start()

        # Ensure the delivery thread is restarted in forked worker processes
        try:  # pragma: no cover - optional multiprocessing hook
            from multiprocessing import util as mp_util

            mp_util.register_after_fork(
                client, lambda _: get_global_delivery(client).start()
            )
        except Exception:  # pragma: no cover - environment may not support fork
            pass

        # Celery uses a separate signal for worker process initialisation
        try:  # pragma: no cover - optional Celery integration
            from celery.signals import worker_process_init

            worker_process_init.connect(
                lambda **_: get_global_delivery(client).start(), weak=False
            )
        except Exception:  # pragma: no cover - Celery not installed
            pass
    else:
        # Ensure the worker is actually running.  Tests may stop the
        # singleton leaving the object assigned but the thread stopped.
        thread = getattr(_global_delivery, "_thread", None)
        if thread is None or not thread.is_alive():
            try:
                # ``stop`` is idempotent so it is safe to call even if not running
                _global_delivery.stop()
            except Exception:  # pragma: no cover - defensive
                pass
            _global_delivery.start()
    return _global_delivery


def get_global_delivery_health() -> Optional[dict[str, Any]]:
    """Return health information for the global queue if initialised."""
    if _global_delivery is None:
        return None
    return _global_delivery.get_health_info()


class ResilientDelivery:
    """Thread based delivery queue with retry logic."""

    def __init__(
        self,
        session: Any,
        api_root: str,
        *,
        endpoint: str = "/track-usage",
        max_retries: int = 5,
        queue_size: int = 1000,
        timeout: float = 10.0,
        ini_path: Optional[str] = None,
    ) -> None:
        self.session = session
        self.api_root = api_root.rstrip("/")
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.timeout = timeout
        self.ini_path = ini_path
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._total_sent = 0
        self._total_failed = 0
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the background worker if not already running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the worker and wait for queued items to be processed."""
        if self._thread is None:
            return
        self._stop.set()
        self._queue.put({})  # sentinel
        self._thread.join()
        self._thread = None

    def deliver(self, payload: dict[str, Any]) -> None:
        """Queue ``payload`` for delivery without blocking."""
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            pass  # Drop payload if queue is full

    # ------------------------------------------------------------------
    # Worker implementation
    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if self._stop.is_set():
                self._queue.task_done()
                break
            batch = [item]
            while True:
                try:
                    nxt = self._queue.get_nowait()
                    batch.append(nxt)
                except queue.Empty:
                    break
            try:
                payload = {"usage_records": []}
                for p in batch:
                    payload["usage_records"].extend(p.get("usage_records", []))
                self._send_with_retry(payload)
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _send_with_retry(self, payload: dict[str, Any]) -> None:
        url = f"{self.api_root}{self.endpoint}"
        retry = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=30),
            reraise=True,
        )
        try:
            for attempt in retry:
                with attempt:
                    response = self.session.post(
                        url,
                        json=payload,
                        timeout=self.timeout,
                    )
                    if hasattr(response, "raise_for_status"):
                        response.raise_for_status()

                    # Process response for triggered_limits
                    if self.ini_path and hasattr(response, "json"):
                        try:
                            response_data = response.json()
                            # Always update triggered_limits, even if empty - server may have cleared previous limits
                            triggered_limits = response_data.get("triggered_limits")
                            self._update_triggered_limits(triggered_limits or {})
                        except Exception:
                            # Don't fail delivery for triggered_limits processing errors
                            pass

            self._total_sent += 1
        except Exception as exc:  # pragma: no cover - network failure
            self._total_failed += 1
            self._last_error = str(exc)

    def _update_triggered_limits(self, triggered_limits: dict) -> None:
        """Update triggered_limits in INI file from delivery response."""
        # Skip INI updates if no ini_path is configured
        if not self.ini_path:
            return

        try:
            with _file_lock(self.ini_path):
                cp = _safe_read_config(self.ini_path)

                # Remove existing triggered_limits section if it exists to prevent duplicates
                if "triggered_limits" in cp:
                    cp.remove_section("triggered_limits")
                cp.add_section("triggered_limits")
                cp["triggered_limits"]["payload"] = json.dumps(triggered_limits)

                # Write atomically using string buffer
                import io

                content = io.StringIO()
                cp.write(content)
                content_str = content.getvalue()

                _atomic_write(self.ini_path, content_str)
        except Exception:
            # Don't fail delivery for INI update errors
            pass

    # ------------------------------------------------------------------
    # Health helpers
    # ------------------------------------------------------------------
    def get_health_info(self) -> dict[str, Any]:
        """Return current queue metrics for debugging."""
        return {
            "worker_alive": self._thread is not None and self._thread.is_alive(),
            "queue_size": self._queue.qsize(),
            "queue_utilization": self._queue.qsize() / self._queue.maxsize,
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "last_error": self._last_error,
        }
