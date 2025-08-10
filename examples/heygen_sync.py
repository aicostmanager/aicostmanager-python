#!/usr/bin/env python3
"""Sync HeyGen streaming sessions to AICostManager.

This example relies on :func:`aicostmanager.delivery.get_global_delivery` for
resilient delivery. The helper returns a process-wide background worker that
batches and retries usage records. When used inside a Celery task the worker is
started automatically for each worker process so the task only needs to enqueue
payloads.

To **guarantee** that all usage records are delivered before the task finishes,
call :func:`sync_streaming_sessions` with ``wait=True`` (the default). This
stops the background worker after the queue is drained. The next task that
needs to send usage data will spawn a new worker automatically via
``get_global_delivery``.

If you prefer to let delivery continue in the background, pass ``wait=False``;
the worker thread will keep running after the task returns and will flush the
queue asynchronously.

Example Celery task::

    from celery import shared_task

    @shared_task
    def update_heygen_costs():
        sync_streaming_sessions()  # wait=True by default
"""

import os
from datetime import datetime, timezone
import requests

from aicostmanager.client import CostManagerClient
from aicostmanager.delivery import get_global_delivery

HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY")
AICM_CONFIG_ID = os.environ.get("AICM_CONFIG_ID")
AICM_SERVICE_ID = os.environ.get("AICM_SERVICE_ID")


def iter_sessions(page_size: int = 100):
    """Yield streaming sessions from HeyGen history."""
    url = "https://api.heygen.com/v2/streaming.list"
    headers = {"x-api-key": HEYGEN_API_KEY}
    params = {"page_size": page_size}
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        sessions = data.get("sessions") or data.get("data") or []
        for sess in sessions:
            yield sess
        token = data.get("token") or data.get("next_page_token")
        if not token:
            break
        params = {"token": token}


def sync_streaming_sessions(page_size: int = 100, *, wait: bool = True) -> None:
    """Fetch HeyGen sessions and queue them for delivery.

    Parameters
    ----------
    page_size:
        Number of sessions to fetch per API call.
    wait:
        When ``True`` (the default) the delivery worker is stopped after
        the queue drains, blocking until all pending records have been
        sent. Set ``wait=False`` to leave the worker running in the
        background, allowing the task to return immediately.
    """
    if not all([HEYGEN_API_KEY, AICM_CONFIG_ID, AICM_SERVICE_ID]):
        raise RuntimeError(
            "HEYGEN_API_KEY, AICM_CONFIG_ID, and AICM_SERVICE_ID must be set in the environment",
        )

    cm_client = CostManagerClient()
    delivery = get_global_delivery(cm_client, on_full="block")

    for session in iter_sessions(page_size=page_size):
        payload = {
            "config_id": AICM_CONFIG_ID,
            "service_id": AICM_SERVICE_ID,
            "timestamp": session.get("start_time")
            or datetime.now(timezone.utc).isoformat(),
            "response_id": session.get("session_id"),
            "usage": {"duration": session.get("duration")},
        }
        delivery.deliver({"usage_records": [payload]})

    if wait:
        delivery.stop()


def main() -> None:
    sync_streaming_sessions()


if __name__ == "__main__":
    main()
