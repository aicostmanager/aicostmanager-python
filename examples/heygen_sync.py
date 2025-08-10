#!/usr/bin/env python3

"""Sync HeyGen streaming sessions to AICostManager.

This example uses :class:`aicostmanager.tracker.Tracker` to validate usage
records and deliver them in the background. The tracker relies on a
process-wide worker that batches and retries records. When used inside a Celery
task the worker is started automatically, so the task only needs to enqueue
usage via :meth:`Tracker.track`.

To **guarantee** that all usage records are delivered before the task finishes,
call :func:`sync_streaming_sessions` with ``wait=True`` (the default). The
function closes the tracker in a ``finally`` block which stops the background
worker after the queue is drained. The next task that needs to send usage data
will spawn a new worker automatically when a new tracker instance is created.

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
import requests

from aicostmanager.tracker import Tracker

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

    tracker = Tracker(AICM_CONFIG_ID, AICM_SERVICE_ID, delivery_on_full="block")

    try:
        for session in iter_sessions(page_size=page_size):
            tracker.track(
                {"duration": session.get("duration")},
                response_id=session.get("session_id"),
            )
    finally:
        if wait:
            tracker.close()


def main() -> None:
    sync_streaming_sessions()


if __name__ == "__main__":
    main()
