import os
import time
import pytest

from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker

if os.environ.get("RUN_NETWORK_TESTS") != "1":
    pytestmark = pytest.mark.skip(reason="requires network access")

_SCENARIOS = [
    (
        "transcription_nova3_en_no_terms",
        [
            {
                "response_id": "dg-transcription-nova3-en-no-terms",
                "service_key": "deepgram::deepgram_websocket_transcription",
                "payload": {
                    "model": "nova-3",
                    "language": "en",
                    "duration": 120,
                    "keywords": [],
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "transcription_nova3_en_with_terms",
        [
            {
                "response_id": "dg-transcription-nova3-en-with-terms",
                "service_key": "deepgram::deepgram_websocket_transcription",
                "payload": {
                    "model": "nova-3",
                    "language": "en",
                    "duration": 90,
                    "keywords": ["brand", "product"],
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "transcription_nova3_multi",
        [
            {
                "response_id": "dg-transcription-nova3-multi",
                "service_key": "deepgram::deepgram_websocket_transcription",
                "payload": {
                    "model": "nova-3",
                    "language": "multi",
                    "duration": 45,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "transcription_fallback_nova2",
        [
            {
                "response_id": "dg-transcription-fallback-nova2",
                "service_key": "deepgram::deepgram_websocket_transcription",
                "payload": {
                    "model": "nova-2",
                    "language": "en",
                    "duration": 30,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "tts_aura1_500",
        [
            {
                "response_id": "dg-tts-aura1-500",
                "service_key": "deepgram::deepgram_streaming_tts",
                "payload": {
                    "model": "aura-1",
                    "char_count": 500,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "tts_aura1_2500",
        [
            {
                "response_id": "dg-tts-aura1-2500",
                "service_key": "deepgram::deepgram_streaming_tts",
                "payload": {
                    "model": "aura-1",
                    "char_count": 2500,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "tts_aura2_1000",
        [
            {
                "response_id": "dg-tts-aura2-1000",
                "service_key": "deepgram::deepgram_streaming_tts",
                "payload": {
                    "model": "aura-2",
                    "char_count": 1000,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "tts_aura2_750",
        [
            {
                "response_id": "dg-tts-aura2-750",
                "service_key": "deepgram::deepgram_streaming_tts",
                "payload": {
                    "model": "aura-2",
                    "char_count": 750,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    ),
    (
        "mixed_batch",
        [
            {
                "response_id": "dg-batch-transcription",
                "service_key": "deepgram::deepgram_websocket_transcription",
                "payload": {
                    "model": "nova-3",
                    "language": "en",
                    "duration": 120,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            },
            {
                "response_id": "dg-batch-tts",
                "service_key": "deepgram::deepgram_streaming_tts",
                "payload": {
                    "model": "aura-1",
                    "char_count": 1500,
                },
                "timestamp": "2025-01-01T00:00:00Z",
            },
        ],
    ),
]


@pytest.mark.parametrize("events", [s[1] for s in _SCENARIOS], ids=[s[0] for s in _SCENARIOS])
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
                "deepgram",
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
            assert result["result"]["cost_events"]


@pytest.mark.parametrize("events", [s[1] for s in _SCENARIOS], ids=[s[0] for s in _SCENARIOS])
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
                "deepgram",
                event["service_key"],
                event["payload"],
                response_id=event["response_id"],
                timestamp=event["timestamp"],
            )
        deadline = time.time() + 5
        while time.time() < deadline:
            if delivery.stats().get("queued", 0) == 0:
                break
            time.sleep(0.1)
        assert delivery.stats().get("queued", 0) == 0
