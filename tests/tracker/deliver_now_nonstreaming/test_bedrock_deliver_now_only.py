import json
import os
import time
import urllib.request
import uuid

import pytest

from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_usage_from_response

boto3 = pytest.importorskip("boto3")

BASE_URL = "http://127.0.0.1:8001"


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
    [
        (
            "amazon-bedrock::us.meta.llama3-3-70b-instruct-v1:0",
            "us.meta.llama3-3-70b-instruct-v1:0",
        ),
        ("amazon-bedrock::us.amazon.nova-pro-v1:0", "us.amazon.nova-pro-v1:0"),
    ],
)
def test_bedrock_deliver_now_only(service_key, model, aws_region, aicm_api_key):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = boto3.client("bedrock-runtime", region_name=aws_region)

    body = {
        "messages": [
            {"role": "user", "content": [{"text": "Say hi (deliver_now_only)"}]}
        ],
        "inferenceConfig": {"maxTokens": 50},
    }
    # Some cross-region model IDs (e.g., amazon.nova-pro-v1:0) require provisioned throughput
    # and will fail with a ValidationException in many accounts. If that happens, skip just
    # this parametrization to allow others to run.
    try:
        resp = client.converse(modelId=model, **body)
    except Exception as e:
        msg = str(e)
        if (
            "on-demand throughput isn’t supported" in msg
            or "on-demand throughput isn't supported" in msg
        ):
            pytest.skip(
                "Bedrock model requires provisioned throughput; skipping this case"
            )
        raise
    response_id = resp.get("output", {}).get("message", {}).get("id") or resp.get(
        "ResponseMetadata", {}
    ).get("RequestId")
    usage_payload = get_usage_from_response(resp, "bedrock")

    try:
        delivery_resp = tracker.deliver_now(
            "amazon-bedrock", service_key, usage_payload, response_id=response_id
        )
        print("deliver_now status:", delivery_resp.status_code)
        try:
            print("deliver_now json:", delivery_resp.json())
        except Exception:
            print("deliver_now text:", delivery_resp.text)
    except Exception as e:
        print("deliver_now raised:", repr(e))
        raise

    _wait_for_cost_event(aicm_api_key, response_id)

    tracker.close()
