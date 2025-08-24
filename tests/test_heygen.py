import datetime
import os
import time
from typing import Dict, List

import pytest
import requests

from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker

SERVICE_KEY = "heygen::api.heygen.com/v2/streaming.list"
BASE_URL = "https://api.heygen.com/v2/streaming.list"

if os.environ.get("RUN_NETWORK_TESTS") != "1":
    pytestmark = pytest.mark.skip(reason="requires network access")


def _fetch_sessions(api_key: str, limit: int = 10) -> List[Dict[str, object]]:
    """Fetch closed streaming sessions and convert them to track events."""
    start = datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc)
    end = datetime.datetime.now(datetime.timezone.utc)
    headers = {"x-api-key": api_key, "accept": "application/json"}
    params = {
        "page": 1,
        "page_size": min(limit, 100),
        "date_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    events: List[Dict[str, object]] = []
    while len(events) < limit:
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") and data.get("code") != 100:
            raise RuntimeError(
                f"HeyGen API returned error code {data.get('code')}: {data.get('message')}"
            )
        sessions = data.get("data") or []
        for sess in sessions:
            if sess.get("status") != "closed":
                continue
            created = datetime.datetime.fromtimestamp(
                sess["created_at"], tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            events.append(
                {
                    "response_id": sess["session_id"],
                    "timestamp": created,
                    "payload": {"duration": sess.get("duration", 0)},
                }
            )
            if len(events) >= limit:
                break
        if len(events) >= limit or not data.get("next_page_token"):
            break
        params["page"] += 1
    return events


@pytest.fixture(scope="module")
def heygen_events():
    api_key = os.environ.get("HEYGEN_API_KEY")
    if not api_key:
        pytest.skip("HEYGEN_API_KEY not set in .env file")
    try:
        events = _fetch_sessions(api_key)
    except Exception as exc:  # pragma: no cover - network issues
        pytest.skip(f"HeyGen API call failed: {exc}")
    if not events:
        pytest.skip("No HeyGen sessions found for date range")
    if len(events) < 10:
        pytest.skip(
            f"Need at least 10 HeyGen sessions for testing, found {len(events)}"
        )
    return events


def test_heygen_track_immediate(heygen_events, aicm_api_key, aicm_api_base, tmp_path):
    # Use first 5 sessions for immediate delivery test
    immediate_events = heygen_events[:5]

    ini = IniManager(str(tmp_path / "heygen_immediate"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in immediate_events:
            result = tracker.track(
                "heygen",
                SERVICE_KEY,
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
            assert result["result"]["cost_events"]


def test_heygen_track_persistent(heygen_events, aicm_api_key, aicm_api_base, tmp_path):
    # Use last 5 sessions for persistent delivery test
    persistent_events = heygen_events[5:10]

    ini = IniManager(str(tmp_path / "heygen_persistent"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path=str(tmp_path / "heygen.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in persistent_events:
            tracker.track(
                "heygen",
                SERVICE_KEY,
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
    assert delivery.stats().get("queued", 0) == 0
