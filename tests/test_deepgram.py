import os
import uuid
from datetime import datetime, timezone

import pytest

from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker

if os.environ.get("RUN_NETWORK_TESTS") != "1":
    pytestmark = pytest.mark.skip(reason="requires network access")


def _generate_unique_id():
    """Generate a unique ID for test response_ids."""
    return str(uuid.uuid4())[:8]


def _get_scenarios():
    """Generate test scenarios with unique response_ids and timestamps."""
    base_timestamp = datetime.now(timezone.utc)
    unique_id = _generate_unique_id()

    return [
        (
            "transcription_nova3_en_no_terms",
            [
                {
                    "response_id": f"dg-transcription-nova3-en-no-terms-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "en",
                        "duration": 120,
                        "keywords": [],
                    },
                    "timestamp": base_timestamp.isoformat().replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "transcription_nova3_en_with_terms",
            [
                {
                    "response_id": f"dg-transcription-nova3-en-with-terms-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "en",
                        "duration": 90,
                        "keywords": ["brand", "product"],
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "transcription_nova3_multi",
            [
                {
                    "response_id": f"dg-transcription-nova3-multi-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "multi",
                        "duration": 45,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "transcription_fallback_nova2",
            [
                {
                    "response_id": f"dg-transcription-fallback-nova2-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-2",
                        "language": "en",
                        "duration": 30,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "tts_aura1_500",
            [
                {
                    "response_id": f"dg-tts-aura1-500-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-1",
                        "char_count": 500,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "tts_aura1_2500",
            [
                {
                    "response_id": f"dg-tts-aura1-2500-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-1",
                        "char_count": 2500,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "tts_aura2_1000",
            [
                {
                    "response_id": f"dg-tts-aura2-1000-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-2",
                        "char_count": 1000,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "tts_aura2_750",
            [
                {
                    "response_id": f"dg-tts-aura2-750-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-2",
                        "char_count": 750,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "mixed_batch",
            [
                {
                    "response_id": f"dg-batch-transcription-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "en",
                        "duration": 120,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                {
                    "response_id": f"dg-batch-tts-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-1",
                        "char_count": 1500,
                    },
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
            ],
        ),
    ]


def _get_scenarios_with_meta():
    """Generate test scenarios with meta data (client_customer_key, context) and unique response_ids."""
    base_timestamp = datetime.now(timezone.utc)
    unique_id = _generate_unique_id()

    return [
        (
            "transcription_nova3_en_with_meta",
            [
                {
                    "response_id": f"dg-transcription-nova3-en-meta-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "en",
                        "duration": 120,
                        "keywords": [],
                    },
                    "client_customer_key": "customer-123",
                    "context": {"environment": "production", "session_id": "sess-456"},
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "tts_aura1_with_meta",
            [
                {
                    "response_id": f"dg-tts-aura1-meta-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-1",
                        "char_count": 500,
                    },
                    "client_customer_key": "customer-789",
                    "context": {"user_id": "user-123", "feature": "tts"},
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        ),
        (
            "mixed_batch_with_meta",
            [
                {
                    "response_id": f"dg-batch-transcription-meta-{unique_id}",
                    "service_key": "deepgram::tts-streaming",
                    "payload": {
                        "model": "nova-3",
                        "language": "en",
                        "duration": 120,
                    },
                    "client_customer_key": "customer-batch",
                    "context": {"batch_id": "batch-001", "priority": "high"},
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                {
                    "response_id": f"dg-batch-tts-meta-{unique_id}",
                    "service_key": "deepgram::tts",
                    "payload": {
                        "model": "aura-1",
                        "char_count": 1500,
                    },
                    "client_customer_key": "customer-batch",
                    "context": {"batch_id": "batch-001", "priority": "high"},
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
            ],
        ),
    ]


@pytest.mark.parametrize(
    "events", [s[1] for s in _get_scenarios()], ids=[s[0] for s in _get_scenarios()]
)
def test_deepgram_track_immediate(events, aicm_api_key, aicm_api_base, tmp_path):
    ini = IniManager(str(tmp_path / "ini_immediate"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in events:
            result = tracker.track(
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
            assert result["result"]["cost_events"]


@pytest.mark.parametrize(
    "events", [s[1] for s in _get_scenarios()], ids=[s[0] for s in _get_scenarios()]
)
def test_deepgram_track_persistent(events, aicm_api_key, aicm_api_base, tmp_path):
    ini = IniManager(str(tmp_path / "ini_persistent"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path=str(tmp_path / "queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in events:
            tracker.track(
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
    assert delivery.stats().get("queued", 0) == 0


@pytest.mark.parametrize(
    "events",
    [s[1] for s in _get_scenarios_with_meta()],
    ids=[s[0] for s in _get_scenarios_with_meta()],
)
def test_deepgram_track_immediate_with_meta(
    events, aicm_api_key, aicm_api_base, tmp_path
):
    ini = IniManager(str(tmp_path / "ini_immediate_meta"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in events:
            result = tracker.track(
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                client_customer_key=event["client_customer_key"],
                context=event["context"],
                timestamp=event["timestamp"],
            )
            assert result["result"]["cost_events"]


@pytest.mark.parametrize(
    "events",
    [s[1] for s in _get_scenarios_with_meta()],
    ids=[s[0] for s in _get_scenarios_with_meta()],
)
def test_deepgram_track_persistent_with_meta(
    events, aicm_api_key, aicm_api_base, tmp_path
):
    ini = IniManager(str(tmp_path / "ini_persistent_meta"))
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path=str(tmp_path / "queue_meta.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        for event in events:
            tracker.track(
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                client_customer_key=event["client_customer_key"],
                context=event["context"],
                timestamp=event["timestamp"],
            )
    assert delivery.stats().get("queued", 0) == 0
