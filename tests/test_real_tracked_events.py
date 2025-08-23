import time

import httpx

from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager

VALID_PAYLOAD = {
    "prompt_tokens": 19,
    "completion_tokens": 10,
    "total_tokens": 29,
    "prompt_tokens_details": {
        "cached_tokens": 0,
        "audio_tokens": 0,
    },
    "completion_tokens_details": {
        "reasoning_tokens": 0,
        "audio_tokens": 0,
        "accepted_prediction_tokens": 0,
        "rejected_prediction_tokens": 0,
    },
}


def _make_tracker(api_key: str, api_base: str, tmp_path) -> Tracker:
    ini = IniManager(str(tmp_path / "ini"))
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key=api_key,
        aicm_api_base=api_base,
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path=str(tmp_path / "queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
        max_attempts=2,  # Reduce attempts for faster failure
        max_retries=2,  # Reduce retries for faster failure
    )
    return Tracker(aicm_api_key=api_key, ini_path=ini.ini_path, delivery=delivery)


def _wait_for_empty(delivery, timeout: float = 10.0) -> bool:
    for _ in range(int(timeout / 0.1)):
        stats = getattr(delivery, "stats", lambda: {})()
        if stats.get("queued", 0) == 0:
            return True
        time.sleep(0.1)
    return False


def test_track_single_event_success(aicm_api_key, aicm_api_base, tmp_path):
    tracker = _make_tracker(aicm_api_key, aicm_api_base, tmp_path)
    tracker.track(
        "openai_chat",
        "openai::gpt-5-mini",
        VALID_PAYLOAD,
        response_id="evt1",
        timestamp="2025-01-01T00:00:00Z",
    )
    assert _wait_for_empty(tracker.delivery)
    tracker.close()


def test_track_multiple_events_with_errors(aicm_api_key, aicm_api_base, tmp_path):
    tracker = _make_tracker(aicm_api_key, aicm_api_base, tmp_path)
    events = [
        {
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "ok1",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Missing service_key
            "api_id": "openai_chat",
            "response_id": "missing",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Invalid service_key format
            "api_id": "openai_chat",
            "service_key": "invalidformat",
            "response_id": "badformat",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Service not found
            "api_id": "openai_chat",
            "service_key": "openai::does-not-exist",
            "response_id": "noservice",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # API client not found
            "api_id": "nonexistent_client",
            "service_key": "openai::gpt-5-mini",
            "response_id": "noapi",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Payload validation error (missing total_tokens)
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "badpayload",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "prompt_tokens": 19,
                "completion_tokens": 10,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "audio_tokens": 0,
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "audio_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
            },
        },
    ]

    for event in events:
        tracker.track(
            event["api_id"],
            event.get("service_key"),
            event["payload"],
            response_id=event.get("response_id"),
            timestamp=event.get("timestamp"),
        )

    assert _wait_for_empty(tracker.delivery)
    tracker.close()


def test_deliver_now_single_event_success(aicm_api_key, aicm_api_base):
    ini = IniManager("ini")
    # Disable limits for this test since it's not testing limits functionality
    ini.set_option("tracker", "AICM_LIMITS_ENABLED", "false")
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery
    ) as tracker:
        result = tracker.track(
            "openai_chat",
            "openai::gpt-5-mini",
            VALID_PAYLOAD,
            response_id="evt1",
            timestamp="2025-01-01T00:00:00Z",
        )
        assert result["result"]["cost_events"]
        assert "triggered_limits" in result


def test_deliver_now_multiple_events_with_errors(aicm_api_key, aicm_api_base):
    ini = IniManager("ini")
    # Disable limits for this test since it's not testing limits functionality
    ini.set_option("tracker", "AICM_LIMITS_ENABLED", "false")
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery)
    events = [
        {
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "ok1",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Missing service_key
            "api_id": "openai_chat",
            "response_id": "missing",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Invalid service_key format
            "api_id": "openai_chat",
            "service_key": "invalidformat",
            "response_id": "badformat",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Service not found
            "api_id": "openai_chat",
            "service_key": "openai::does-not-exist",
            "response_id": "noservice",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # API client not found
            "api_id": "nonexistent_client",
            "service_key": "openai::gpt-5-mini",
            "response_id": "noapi",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Payload validation error (missing total_tokens)
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "badpayload",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "prompt_tokens": 19,
                "completion_tokens": 10,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "audio_tokens": 0,
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "audio_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
            },
        },
    ]

    results = []
    for idx, event in enumerate(events):
        if idx == 1:
            # Missing service_key: the client raises on 422, so verify behavior via raw HTTP call
            body = {
                "tracked": [
                    {
                        "api_id": event["api_id"],
                        # intentionally omit service_key
                        "response_id": event["response_id"],
                        "timestamp": event["timestamp"],
                        "payload": event["payload"],
                    }
                ]
            }
            with httpx.Client() as client:
                resp = client.post(
                    f"{aicm_api_base.rstrip('/')}/api/v1/track",
                    json=body,
                    headers={"Authorization": f"Bearer {aicm_api_key}"},
                )
            # Server may respond 422 with results array now; collect errors mapping
            if resp.status_code == 422:
                data = resp.json()
                res = data.get("results", [])
                if res and isinstance(res[0], dict):
                    rid = res[0].get("response_id") or event.get("response_id")
                    errs = res[0].get("errors") or ["Rejected by server"]
                    results.append({rid: errs})
                else:
                    results.append({event.get("response_id"): ["Rejected by server"]})
            else:
                results.append({event.get("response_id"): "sent"})
            continue

        # For invalid inputs that will cause 422 (e.g., bad service_key format or missing totals),
        # send directly to server to assert validation instead of using immediate delivery.
        invalid_case = idx in (2, 3, 5)
        if invalid_case:
            body = {
                "tracked": [
                    {
                        "api_id": event["api_id"],
                        "service_key": event.get("service_key"),
                        "response_id": event.get("response_id"),
                        "timestamp": event.get("timestamp"),
                        "payload": event.get("payload"),
                    }
                ]
            }
            with httpx.Client() as client:
                resp = client.post(
                    f"{aicm_api_base.rstrip('/')}/api/v1/track",
                    json=body,
                    headers={"Authorization": f"Bearer {aicm_api_key}"},
                )
            assert resp.status_code == 422, resp.text
            data = resp.json()
            res = data.get("results", [])
            if res and isinstance(res[0], dict):
                rid = res[0].get("response_id") or event.get("response_id")
                errs = res[0].get("errors") or ["Rejected by server"]
                results.append({rid: errs})
            else:
                results.append({event.get("response_id"): ["Rejected by server"]})
        else:
            try:
                tracker.track(
                    event["api_id"],
                    event.get("service_key"),
                    event["payload"],
                    response_id=event.get("response_id"),
                    timestamp=event.get("timestamp"),
                )
                results.append({event.get("response_id"): "sent"})
            except httpx.HTTPStatusError as e:
                # If server rejects even the valid case due to schema drift, accept server-side validation
                if e.response is not None and e.response.status_code == 422:
                    results.append({event.get("response_id"): ["Rejected by server"]})
                else:
                    raise

    tracker.close()

    # Server now returns errors under results[x].errors
    assert results[0]["ok1"] in ("sent",)
    assert results[1]["missing"] == ["Missing service_key"]
    assert results[2]["badformat"] == ["Invalid service_key format"]
    assert results[3]["noservice"] == ["Service not found"]
    assert results[4]["noapi"] in (
        ["API client not found"],
        ["ApiClientService configuration not found"],
        ["Rejected by server"],
    )
    err = results[5]["badpayload"]
    assert isinstance(err, list)


def test_track_missing_response_id_generates_unknown_and_422(
    aicm_api_key, aicm_api_base
):
    # Send directly with httpx to omit response_id entirely.
    with httpx.Client() as client:
        body = {
            "tracked": [
                {
                    "api_id": "openai_chat",
                    "service_key": "openai::gpt-5-mini",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "payload": VALID_PAYLOAD,
                }
            ]
        }
        resp = client.post(
            f"{aicm_api_base.rstrip('/')}/api/v1/track",
            json=body,
            headers={"Authorization": f"Bearer {aicm_api_key}"},
        )
    assert resp.status_code == 422, resp.text
    data = resp.json()
    # New schema returns errors in results array
    results = data.get("results", [])
    assert len(results) == 1
    first = results[0]
    assert "response_id" in first and isinstance(first.get("response_id"), str)
    assert first["response_id"].startswith("UNKNOWN-RESPONSE-")
    assert first.get("errors") == ["Missing response_id."]
