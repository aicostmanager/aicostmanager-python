"""Background delivery helpers for ``CostManager``.

This module provides a simple thread based queue that batches payloads
and retries failed requests using ``tenacity``.  A single global queue
is shared across all ``CostManager`` instances to avoid the overhead of
creating a new worker per wrapper.
"""

from __future__ import annotations

import asyncio
import configparser
import json
import os
import queue
import tempfile
import threading
import time
import logging
import io
import atexit
from contextlib import contextmanager
from typing import Any, Optional, Callable

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    stop_after_attempt,
    wait_exponential_jitter,
)

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


def _ini_get_or_set(
    ini_path: str,
    section: str,
    option: str,
    value: float | int,
    override: bool = False,
) -> float:
    """Retrieve or store a numeric option in an INI file."""
    with _file_lock(ini_path):
        cp = _safe_read_config(ini_path)
        if section not in cp:
            cp.add_section(section)
        if option in cp[section] and not override:
            try:
                return float(cp[section][option])
            except ValueError:
                pass
        cp[section][option] = str(value)
        buf = io.StringIO()
        cp.write(buf)
        _atomic_write(ini_path, buf.getvalue())
        return float(value)


def get_global_delivery(
    client: CostManagerClient,
    *,
    max_retries: int = 5,
    queue_size: int = 1000,
    endpoint: str = "/track-usage",
    timeout: float = 10.0,
    batch_interval: float | None = None,
    max_batch_size: int = 100,
    delivery_mode: str | None = None,
    on_full: str | None = None,
) -> "ResilientDelivery":
    """Return the shared delivery queue initialised with ``client``.

    The first caller creates the queue which is then reused by all
    subsequent ``CostManager`` instances.  The worker thread is started on
    creation.
    """
    global _global_delivery
    if delivery_mode is None:
        delivery_mode = os.getenv("AICM_DELIVERY_MODE", "sync")
    if on_full is None:
        on_full = os.getenv("AICM_DELIVERY_ON_FULL", "backpressure")
    async_mode = delivery_mode.lower() == "async"
    if _global_delivery is None or _global_delivery.async_mode != async_mode:
        session = client.session
        if async_mode:
            session = httpx.AsyncClient()
            session.headers.update(client.session.headers)
        _global_delivery = ResilientDelivery(
            session,
            client.api_root,
            max_retries=max_retries,
            queue_size=queue_size,
            endpoint=endpoint,
            timeout=timeout,
            ini_path=client.ini_path,
            async_mode=async_mode,
            on_full=on_full,
            batch_interval=batch_interval,
            max_batch_size=max_batch_size,
        )
        _global_delivery.start()
        if not getattr(_global_delivery, "_atexit_registered", False):
            atexit.register(_global_delivery.stop)
            _global_delivery._atexit_registered = True

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
        async_mode: bool | None = None,
        on_full: str | None = None,
        batch_interval: float | None = None,
        max_batch_size: int = 100,
        on_discard: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        if async_mode is None:
            async_mode = (
                os.getenv("AICM_DELIVERY_MODE", "sync").lower() == "async"
            )
        self.async_mode = async_mode

        if self.async_mode and not hasattr(session, "aclose"):
            async_session = httpx.AsyncClient()
            try:
                async_session.headers.update(getattr(session, "headers", {}))
            except Exception:
                pass
            self.session = async_session
        else:
            self.session = session
        self.api_root = api_root.rstrip("/")
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.timeout = timeout
        self.ini_path = ini_path
        self.max_batch_size = max_batch_size
        if ini_path:
            default_interval = batch_interval if batch_interval is not None else 0.05
            override = batch_interval is not None
            self.batch_interval = _ini_get_or_set(
                ini_path, "delivery", "timeout", default_interval, override=override
            )
        else:
            self.batch_interval = batch_interval if batch_interval is not None else 0.05
        if on_full is None:
            on_full = os.getenv("AICM_DELIVERY_ON_FULL", "backpressure")
        if on_full not in {"block", "raise", "backpressure"}:
            raise ValueError("on_full must be 'block', 'raise', or 'backpressure'")
        self.on_full = on_full
        self.on_discard = on_discard
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._total_sent = 0
        self._total_failed = 0
        self._last_error: Optional[str] = None
        self._total_discarded = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

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
        if self.async_mode:
            if hasattr(self.session, "aclose"):
                try:
                    if self._loop is not None:
                        asyncio.run_coroutine_threadsafe(
                            self.session.aclose(), self._loop
                        ).result()
                    else:
                        asyncio.run(self.session.aclose())
                except Exception:
                    try:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(self.session.aclose())
                        loop.close()
                    except Exception:
                        pass
            if self._loop is not None:
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                    if self._loop_thread is not None:
                        self._loop_thread.join()
                    self._loop.close()
                finally:
                    self._loop = None
                    self._loop_thread = None

    def deliver(self, payload: dict[str, Any]) -> None:
        """Queue ``payload`` for delivery without blocking."""
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logging.warning("Delivery queue full")
            if self.on_full == "block":
                self._queue.put(payload)
            elif self.on_full == "raise":
                raise
            else:  # backpressure
                dropped = None
                try:
                    dropped = self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    pass
                if dropped is not None:
                    self._total_discarded += 1
                    if self.on_discard:
                        try:
                            self.on_discard(dropped)
                        except Exception:
                            logging.exception("Discard callback failed")
                try:
                    self._queue.put_nowait(payload)
                except queue.Full:
                    self._total_discarded += 1
                    if self.on_discard:
                        try:
                            self.on_discard(payload)
                        except Exception:
                            logging.exception("Discard callback failed")

    # ------------------------------------------------------------------
    # Worker implementation
    # ------------------------------------------------------------------
    def _run(self) -> None:
        if self.async_mode and self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self._loop.run_forever, daemon=True
            )
            self._loop_thread.start()

        while not self._stop.is_set():
            item = self._queue.get()
            if self._stop.is_set():
                self._queue.task_done()
                break
            batch = [item]
            deadline = time.time() + self.batch_interval
            while len(batch) < self.max_batch_size:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    nxt = self._queue.get(timeout=remaining)
                    batch.append(nxt)
                except queue.Empty:
                    break
            try:
                payload = {"usage_records": []}
                for p in batch:
                    payload["usage_records"].extend(p.get("usage_records", []))
                if self.async_mode and self._loop is not None:
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_with_retry_async(payload), self._loop
                    )
                    future.result()
                else:
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

    async def _send_with_retry_async(self, payload: dict[str, Any]) -> None:
        url = f"{self.api_root}{self.endpoint}"
        retry = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=30),
            reraise=True,
        )
        try:
            async for attempt in retry:
                with attempt:
                    response = await self.session.post(
                        url,
                        json=payload,
                        timeout=self.timeout,
                    )
                    if hasattr(response, "raise_for_status"):
                        response.raise_for_status()

                    if self.ini_path and hasattr(response, "json"):
                        try:
                            response_data = response.json()
                            triggered_limits = response_data.get("triggered_limits")
                            self._update_triggered_limits(triggered_limits or {})
                        except Exception:
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
            "total_discarded": self._total_discarded,
            "last_error": self._last_error,
        }
