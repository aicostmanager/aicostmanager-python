import time
import json
import uuid
import urllib.request

import pytest

boto3 = pytest.importorskip("boto3")

from aicostmanager.tracker import Tracker

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    event_id = data.get("event_id") or data.get("cost_event", {}).get("event_id")
                    if event_id:
                        uuid.UUID(str(event_id))
                        return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"cost event for {response_id} not found")


@pytest.mark.parametrize(
    "service_key, model_id",
    [
        ("amazon-bedrock::amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
        ("amazon-bedrock::us.meta.llama3-3-70b-instruct-v1:0", "us.meta.llama3-3-70b-instruct-v1:0"),
        ("amazon-bedrock::us.amazon.nova-pro-v1:0", "us.amazon.nova-pro-v1:0"),
    ],
)
def test_bedrock_tracker(service_key, model_id, aws_region, aicm_api_key):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = boto3.client("bedrock-runtime", region_name=aws_region)

    body = {
        "messages": [{"role": "user", "content": [{"text": "Say hi"}]}],
        "inferenceConfig": {"maxTokens": 50},
    }
    response = client.converse(modelId=model_id, **body)
    response_id = (
        response.get("output", {}).get("message", {}).get("id")
        or response.get("ResponseMetadata", {}).get("RequestId")
    )
    tracker.track("amazon-bedrock", service_key, {"input_tokens": 1}, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)

    body2 = {
        "messages": [{"role": "user", "content": [{"text": "Say hi again"}]}],
        "inferenceConfig": {"maxTokens": 50},
    }
    response2 = client.converse(modelId=model_id, **body2)
    response_id2 = (
        response2.get("output", {}).get("message", {}).get("id")
        or response2.get("ResponseMetadata", {}).get("RequestId")
    )
    delivery_resp = tracker.deliver_now(
        "amazon-bedrock", service_key, {"input_tokens": 1}, response_id=response_id2
    )
    assert delivery_resp.status_code in (200, 201)
    _wait_for_cost_event(aicm_api_key, response_id2)

    tracker.close()
