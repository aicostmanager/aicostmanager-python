#!/usr/bin/env python3
"""Example script to sync HeyGen streaming sessions to AICostManager."""

import os
from datetime import datetime, timezone
import requests

from aicostmanager.client import CostManagerClient

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


def main():
    if not all([HEYGEN_API_KEY, AICM_CONFIG_ID, AICM_SERVICE_ID]):
        raise RuntimeError(
            "HEYGEN_API_KEY, AICM_CONFIG_ID, and AICM_SERVICE_ID must be set in the environment"
        )

    cm_client = CostManagerClient()

    for session in iter_sessions():
        record = {
            "usage_records": [
                {
                    "config_id": AICM_CONFIG_ID,
                    "service_id": AICM_SERVICE_ID,
                    "timestamp": session.get("start_time")
                    or datetime.now(timezone.utc).isoformat(),
                    "response_id": session.get("session_id"),
                    "usage": {"duration": session.get("duration")},
                }
            ]
        }
        cm_client.track_usage(record)


if __name__ == "__main__":
    main()
