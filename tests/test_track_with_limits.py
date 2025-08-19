import json
import os
import time
from decimal import Decimal

import pytest

openai = pytest.importorskip("openai")

from aicostmanager.client import CostManagerClient
from aicostmanager.client.exceptions import UsageLimitExceeded
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.limits import UsageLimitManager
from aicostmanager.models import Period, ThresholdType, UsageLimitIn
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_usage_from_response

MODEL = "gpt-5-mini"
SERVICE_KEY = f"openai::{MODEL}"
OTHER_MODEL = "gpt-4o-mini"
LIMIT_AMOUNT = Decimal("0.0000001")


def _wait_for_empty(delivery, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = getattr(delivery, "stats", lambda: {})()
        print("delivery stats:", stats)
        if stats.get("queued", 0) == 0:
            return
        time.sleep(0.05)
    raise AssertionError("delivery queue did not drain")


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="requires network access",
)
@pytest.mark.usefixtures("clear_triggered_limits")
def test_track_with_limits_immediate(
    openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    print("AICM_API_BASE:", aicm_api_base)
    # Ensure Tracker uses the same API base as the client by providing a delivery
    dconfig = DeliveryConfig(
        ini_manager=IniManager(str(ini)),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        ini_path=str(ini),
        delivery=create_delivery(DeliveryType.IMMEDIATE, dconfig),
    )
    print("tracker delivery endpoint:", getattr(tracker.delivery, "_endpoint", None))
    client = openai.OpenAI(api_key=openai_api_key)

    resp = client.responses.create(model=MODEL, input="hi")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("first response_id:", response_id)
    print("first usage payload:", json.dumps(usage_payload, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        usage_payload,
        response_id=response_id,
    )

    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    ul_in = UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=LIMIT_AMOUNT,
        period=Period.DAY,
        vendor="openai",
        service=MODEL,
    )
    print("creating usage limit:", ul_in.model_dump(mode="json"))
    limit = ul_mgr.create_usage_limit(ul_in)

    resp = client.responses.create(model=MODEL, input="trigger")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("trigger response_id:", response_id)
    print("trigger usage payload:", json.dumps(usage_payload, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        usage_payload,
        response_id=response_id,
    )

    resp = client.responses.create(model=MODEL, input="should fail")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("should-fail response_id:", response_id)
    print("should-fail usage payload:", json.dumps(usage_payload, default=str))
    with pytest.raises(UsageLimitExceeded):
        tracker.track(
            "openai_responses",
            SERVICE_KEY,
            usage_payload,
            response_id=response_id,
        )

    with Tracker(aicm_api_key=aicm_api_key, ini_path=str(ini)) as t2:
        resp_other = client.responses.create(model=OTHER_MODEL, input="other")
        other_response_id = getattr(resp_other, "id", None)
        other_usage = get_usage_from_response(resp_other, "openai_responses")
        other_service_key = f"openai::{OTHER_MODEL}"
        print("other response_id:", other_response_id)
        print("other usage payload:", json.dumps(other_usage, default=str))
        t2.track(
            "openai_responses",
            other_service_key,
            other_usage,
            response_id=other_response_id,
        )

    upd_in = UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=Decimal("0.1"),
        period=Period.DAY,
        vendor="openai",
        service=MODEL,
    )
    print("updating usage limit:", upd_in.model_dump(mode="json"))
    ul_mgr.update_usage_limit(limit.uuid, upd_in)

    resp = client.responses.create(model=MODEL, input="after raise")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("after-raise response_id:", response_id)
    print("after-raise usage payload:", json.dumps(usage_payload, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        usage_payload,
        response_id=response_id,
    )

    resp = client.responses.create(model=MODEL, input="raise again")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("raise-again response_id:", response_id)
    print("raise-again usage payload:", json.dumps(usage_payload, default=str))
    with pytest.raises(UsageLimitExceeded):
        tracker.track(
            "openai_responses",
            SERVICE_KEY,
            usage_payload,
            response_id=response_id,
        )

    ul_mgr.delete_usage_limit(limit.uuid)

    resp = client.responses.create(model=MODEL, input="after delete")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    print("after-delete response_id:", response_id)
    print("after-delete usage payload:", json.dumps(usage_payload, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        usage_payload,
        response_id=response_id,
    )

    tracker.close()


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="requires network access",
)
@pytest.mark.usefixtures("clear_triggered_limits")
@pytest.mark.parametrize(
    "delivery_type", [DeliveryType.MEM_QUEUE, DeliveryType.PERSISTENT_QUEUE]
)
def test_track_with_limits_queue(
    delivery_type, openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    print("AICM_API_BASE:", aicm_api_base)
    dconfig = DeliveryConfig(
        ini_manager=IniManager(str(ini)),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    extra = {"batch_interval": 0.1}
    if delivery_type is DeliveryType.PERSISTENT_QUEUE:
        extra.update({"db_path": str(tmp_path / "queue.db"), "poll_interval": 0.1})
    delivery = create_delivery(delivery_type, dconfig, **extra)
    print("delivery type:", delivery_type)
    print("delivery endpoint:", getattr(delivery, "_endpoint", None))

    client = openai.OpenAI(api_key=openai_api_key)
    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    ul_in = UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=LIMIT_AMOUNT,
        period=Period.DAY,
        vendor="openai",
        service=MODEL,
    )
    print("creating usage limit:", ul_in.model_dump(mode="json"))
    limit = ul_mgr.create_usage_limit(ul_in)

    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=str(ini), delivery=delivery
    ) as tracker:
        resp = client.responses.create(model=MODEL, input="hi")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue first response_id:", rid)
        print("queue first usage payload:", json.dumps(up, default=str))
        tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="trigger")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue trigger response_id:", rid)
        print("queue trigger usage payload:", json.dumps(up, default=str))
        tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="should fail")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue should-fail response_id:", rid)
        print("queue should-fail usage payload:", json.dumps(up, default=str))
        with pytest.raises(UsageLimitExceeded):
            tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)

        with Tracker(
            aicm_api_key=aicm_api_key,
            ini_path=str(ini),
            delivery=create_delivery(delivery_type, dconfig, **extra),
        ) as t2:
            resp_other = client.responses.create(model=OTHER_MODEL, input="other")
            rid2 = getattr(resp_other, "id", None)
            up2 = get_usage_from_response(resp_other, "openai_responses")
            other_service_key = f"openai::{OTHER_MODEL}"
            print("queue other response_id:", rid2)
            print("queue other usage payload:", json.dumps(up2, default=str))
            t2.track("openai_responses", other_service_key, up2, response_id=rid2)
            _wait_for_empty(t2.delivery)

        upd_in = UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=Decimal("0.1"),
            period=Period.DAY,
            vendor="openai",
            service=MODEL,
        )
        print("updating usage limit:", upd_in.model_dump(mode="json"))
        ul_mgr.update_usage_limit(limit.uuid, upd_in)

        resp = client.responses.create(model=MODEL, input="after raise")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue after-raise response_id:", rid)
        print("queue after-raise usage payload:", json.dumps(up, default=str))
        tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="raise again")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue raise-again response_id:", rid)
        print("queue raise-again usage payload:", json.dumps(up, default=str))
        with pytest.raises(UsageLimitExceeded):
            tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)

        ul_mgr.delete_usage_limit(limit.uuid)

        resp = client.responses.create(model=MODEL, input="after delete")
        rid = getattr(resp, "id", None)
        up = get_usage_from_response(resp, "openai_responses")
        print("queue after-delete response_id:", rid)
        print("queue after-delete usage payload:", json.dumps(up, default=str))
        tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
        _wait_for_empty(tracker.delivery)


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="requires network access",
)
@pytest.mark.usefixtures("clear_triggered_limits")
def test_track_with_limits_customer(
    openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    tracker = Tracker(aicm_api_key=aicm_api_key, ini_path=str(ini))
    client = openai.OpenAI(api_key=openai_api_key)
    customer = "cust-limit"

    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    ul_in = UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=LIMIT_AMOUNT,
        period=Period.DAY,
        vendor="openai",
        service=MODEL,
        client=customer,
    )
    print("creating usage limit (customer):", ul_in.model_dump(mode="json"))
    limit = ul_mgr.create_usage_limit(ul_in)

    resp = client.responses.create(model=MODEL, input="hi")
    rid = getattr(resp, "id", None)
    up = get_usage_from_response(resp, "openai_responses")
    print("cust first response_id:", rid)
    print("cust first usage payload:", json.dumps(up, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        up,
        response_id=rid,
        client_customer_key=customer,
    )

    resp = client.responses.create(model=MODEL, input="should fail")
    rid = getattr(resp, "id", None)
    up = get_usage_from_response(resp, "openai_responses")
    print("cust should-fail response_id:", rid)
    print("cust should-fail usage payload:", json.dumps(up, default=str))
    with pytest.raises(UsageLimitExceeded):
        tracker.track(
            "openai_responses",
            SERVICE_KEY,
            up,
            response_id=rid,
            client_customer_key=customer,
        )

    ul_mgr.delete_usage_limit(limit.uuid)

    resp = client.responses.create(model=MODEL, input="after delete")
    rid = getattr(resp, "id", None)
    up = get_usage_from_response(resp, "openai_responses")
    print("cust after-delete response_id:", rid)
    print("cust after-delete usage payload:", json.dumps(up, default=str))
    tracker.track(
        "openai_responses",
        SERVICE_KEY,
        up,
        response_id=rid,
        client_customer_key=customer,
    )

    tracker.close()
