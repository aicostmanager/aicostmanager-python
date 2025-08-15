import json
import time
import urllib.request
import uuid

import pytest

boto3 = pytest.importorskip("boto3")

from aicostmanager.persistent_delivery import PersistentDelivery
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import extract_usage

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}", headers=headers
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    event_id = data.get("event_id") or data.get("cost_event", {}).get(
                        "event_id"
                    )
                    if event_id:
                        uuid.UUID(str(event_id))
                        return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"cost event for {response_id} not found")


def _make_client(region: str):
    return boto3.client("bedrock-runtime", region_name=region)


@pytest.mark.parametrize(
    "service_key, model",
    [
        ("amazon-bedrock::amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
        (
            "amazon-bedrock::us.meta.llama3-3-70b-instruct-v1:0",
            "us.meta.llama3-3-70b-instruct-v1:0",
        ),
        ("amazon-bedrock::us.amazon.nova-pro-v1:0", "us.amazon.nova-pro-v1:0"),
    ],
)

def test_bedrock_track_non_streaming(service_key, model, aws_region, aicm_api_key):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = _make_client(aws_region)

    body = {
        "messages": [{"role": "user", "content": [{"text": "Say hi"}]}],
        "inferenceConfig": {"maxTokens": 50},
    }
    resp = client.converse(modelId=model, **body)
    response_id = (
        resp.get("output", {}).get("message", {}).get("id")
        or resp.get("ResponseMetadata", {}).get("RequestId")
    )
    usage = extract_usage(resp)
    tracker.track("amazon-bedrock", service_key, usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()


@pytest.mark.parametrize(
    "service_key, model",
    [
        ("amazon-bedrock::amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
        (
            "amazon-bedrock::us.meta.llama3-3-70b-instruct-v1:0",
            "us.meta.llama3-3-70b-instruct-v1:0",
        ),
        ("amazon-bedrock::us.amazon.nova-pro-v1:0", "us.amazon.nova-pro-v1:0"),
    ],
)

def test_bedrock_track_streaming(service_key, model, aws_region, aicm_api_key):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = _make_client(aws_region)

    body = {
        "messages": [{"role": "user", "content": [{"text": "Say hi"}]}],
        "inferenceConfig": {"maxTokens": 50},
    }
    resp = client.converse_stream(modelId=model, **body)
    stream = resp["stream"]
    final_event = None
    response_id = None
    for event in stream:
        final_event = event
        if response_id is None:
            if "messageStart" in event:
                msg = event["messageStart"]
                response_id = msg.get("id") or msg.get("message", {}).get("id")
            elif "metadata" in event:
                response_id = event["metadata"].get("id")
    usage = extract_usage(final_event)
    tracker.track("amazon-bedrock", service_key, usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()
