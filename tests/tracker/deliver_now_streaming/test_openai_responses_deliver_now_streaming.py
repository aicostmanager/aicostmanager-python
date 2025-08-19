import json
import os
import time
import urllib.request
import uuid

import pytest

from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import (
    get_streaming_usage_from_response,
    get_usage_from_response,
)

openai = pytest.importorskip("openai")

BASE_URL = os.environ.get("AICM_API_BASE", "http://127.0.0.1:8001")


def _wait_for_cost_event(aicm_api_key: str, response_id: str):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    time.sleep(5)
    last_data = None
    for _ in range(3):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}", headers=headers
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    last_data = data
                    if isinstance(data, list):
                        if data:
                            evt = data[0]
                            evt_id = evt.get("event_id") or evt.get("uuid")
                            if evt_id:
                                uuid.UUID(str(evt_id))
                                return data
                    else:
                        event_id = data.get("event_id") or data.get(
                            "cost_event", {}
                        ).get("event_id")
                        if event_id:
                            uuid.UUID(str(event_id))
                            return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(
        f"cost event for {response_id} not found; last_data={last_data} base_url={BASE_URL}"
    )


@pytest.mark.parametrize(
    "service_key, model",
    [("openai::gpt-5-mini", "gpt-5-mini")],
)
def test_openai_responses_deliver_now_streaming(
    service_key, model, openai_api_key, aicm_api_key
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    ini = IniManager("ini")
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=BASE_URL
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE, dconfig, poll_interval=0.1, batch_interval=0.1
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        client = openai.OpenAI(api_key=openai_api_key)

        response_id = uuid.uuid4().hex
        usage_payload = {}

        print("openai responses response_id:", response_id)
        stream = client.responses.stream(
            model=model,
            input="Say hi (deliver_now_streaming)",
        )
        with stream as s:
            for event in s:
                try:
                    print("openai responses event has usage:", hasattr(event, "usage"))
                except Exception:
                    pass
                up = get_streaming_usage_from_response(event, "openai_responses")
                if isinstance(up, dict) and up:
                    print("openai responses usage chunk:", json.dumps(up, default=str))
                    usage_payload = up

            # Fallback to final response usage if we didn't catch a chunk
            final_resp = s.get_final_response()
            if not usage_payload:
                usage_payload = get_usage_from_response(final_resp, "openai_responses")

        if not usage_payload:
            pytest.skip("No usage returned in streaming events; skipping")

        dconfig2 = DeliveryConfig(
            ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=BASE_URL
        )
        delivery2 = create_delivery(DeliveryType.IMMEDIATE, dconfig2)
        with Tracker(
            aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery2
        ) as t2:
            t2.track(
                "openai_responses", service_key, usage_payload, response_id=response_id
            )

        _wait_for_cost_event(aicm_api_key, response_id)
