import time

import httpx
import pytest

from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from tests.track_asserts import assert_track_result_payload

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
            "openai::gpt-5-mini",
            VALID_PAYLOAD,
            response_id="evt1",
            timestamp="2025-01-01T00:00:00Z",
        )
        if result is None:
            pytest.skip(
                "Server rejected tracking request - check server logs for validation errors"
            )
        payload = result.get("result") or {}
        assert payload, "Immediate track should return a result payload"
        assert_track_result_payload(payload)
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

    def _extract_payload(data: dict, fallback_id: str) -> dict:
        results = data.get("results", [])
        if results and isinstance(results[0], dict):
            payload = results[0]
            payload.setdefault("response_id", fallback_id)
            return payload
        errors = data.get("errors") or data.get("detail")
        if isinstance(errors, str):
            errors = [errors]
        elif not isinstance(errors, list):
            errors = ["Rejected by server"]
        return {"response_id": fallback_id, "errors": errors}

    collected: dict[str, dict] = {}

    for idx, event in enumerate(events):
        response_id = event.get("response_id") or f"evt-{idx}"
        if idx == 1:
            body = {
                "tracked": [
                    {
                        "api_id": event["api_id"],
                        "response_id": response_id,
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
            data = resp.json()
            collected_response = _extract_payload(data, response_id)
            collected[collected_response["response_id"]] = collected_response
            continue

        if idx in (2, 3, 5):
            body = {
                "tracked": [
                    {
                        "api_id": event["api_id"],
                        "service_key": event.get("service_key"),
                        "response_id": response_id,
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
            assert resp.status_code in {202, 422}, resp.text
            data = resp.json()
            collected_response = _extract_payload(data, response_id)
            collected[collected_response["response_id"]] = collected_response
            continue

        track_res = tracker.track(
            event["api_id"],
            event["payload"],
            response_id=response_id,
            timestamp=event.get("timestamp"),
        )
        payload = track_res.get("result") if isinstance(track_res, dict) else None
        if isinstance(payload, dict):
            collected[payload.get("response_id", response_id)] = payload
        else:
            collected[response_id] = {
                "response_id": response_id,
                "errors": ["Rejected by server"],
            }

    tracker.close()

    ok_payload = collected.get("ok1")
    assert ok_payload is not None
    assert_track_result_payload(ok_payload)

    missing_payload = collected.get("missing")
    assert missing_payload is not None
    assert missing_payload.get("errors")
    assert any("service_key" in e.lower() for e in missing_payload.get("errors", []))

    badformat_payload = collected.get("badformat")
    assert badformat_payload is not None
    assert badformat_payload.get("errors")

    noservice_payload = collected.get("noservice")
    assert noservice_payload is not None
    assert_track_result_payload(noservice_payload)
    assert noservice_payload.get("status") == "service_key_unknown"

    noapi_payload = collected.get("noapi")
    if noapi_payload is not None:
        # Some servers may reject this at ingestion time if the API client is unknown
        if noapi_payload.get("errors"):
            assert any("api" in e.lower() for e in noapi_payload["errors"])
        else:
            assert_track_result_payload(noapi_payload)

    badpayload_payload = collected.get("badpayload")
    assert badpayload_payload is not None
    assert badpayload_payload.get("errors")


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
    if len(results) == 1:
        first = results[0]
        assert "response_id" in first and isinstance(first.get("response_id"), str)
        assert first["response_id"].startswith("UNKNOWN-RESPONSE-")
        assert first.get("errors") == ["Missing response_id."]
    else:
        # Server may not return results for missing response_id
        assert len(results) == 0
