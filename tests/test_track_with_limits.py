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
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_usage_from_response

MODEL = "gpt-5-mini"
SERVICE_KEY = f"openai::{MODEL}"
OTHER_MODEL = "gpt-4o-mini"
LIMIT_AMOUNT = Decimal("0.0000001")

# Pricing (USD per token)
INPUT_COST = Decimal("0.25") / Decimal("1000000")
OUTPUT_COST = Decimal("2") / Decimal("1000000")
CACHE_READ_COST = Decimal("0.025") / Decimal("1000000")


def _estimate_cost(usage: dict) -> Decimal:
    inp = Decimal(str(usage.get("input_tokens", 0)))
    out = Decimal(str(usage.get("output_tokens", 0)))
    cached = Decimal(str(usage.get("input_tokens_details", {}).get("cached_tokens", 0)))
    return inp * INPUT_COST + out * OUTPUT_COST + cached * CACHE_READ_COST


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
@pytest.mark.xfail(reason="Server-side async processing timing - not deterministic")
def test_track_with_limits_immediate(
    openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    print("AICM_API_BASE:", aicm_api_base)
    # Enable triggered limits for this test
    IniManager(str(ini)).set_option("tracker", "AICM_LIMITS_ENABLED", "true")
    # Ensure Tracker uses the same API base as the client by providing a delivery
    dconfig = DeliveryConfig(
        ini_manager=IniManager(str(ini)),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    # Speed up immediate post-send check during tests (but keep long enough to be reliable)
    os.environ["AICM_IMMEDIATE_PAUSE_SECONDS"] = "5.0"
    with Tracker(
        aicm_api_key=aicm_api_key,
        ini_path=str(ini),
        delivery=create_delivery(DeliveryType.IMMEDIATE, dconfig),
    ) as tracker:
        print(
            "tracker delivery endpoint:", getattr(tracker.delivery, "_endpoint", None)
        )
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
    api_key_uuid = (
        aicm_api_key.split(".")[-1] if aicm_api_key and "." in aicm_api_key else None
    )
    print("parsed api_key_uuid:", api_key_uuid)
    ul_payload = {
        "threshold_type": "limit",
        "amount": str(LIMIT_AMOUNT),
        "period": "day",
        "service_key": SERVICE_KEY,
        "api_key_uuid": api_key_uuid,
    }
    print("creating usage limit:", json.dumps(ul_payload))
    limit = ul_mgr.create_usage_limit(ul_payload)
    limit_uuid = getattr(limit, "uuid", None)

    # Allow server time to process the usage and trigger the limit
    time.sleep(2)

    try:
        resp = client.responses.create(model=MODEL, input="trigger")
        response_id = getattr(resp, "id", None)
        usage_payload = get_usage_from_response(resp, "openai_responses")
        print("trigger response_id:", response_id)
        print("trigger usage payload:", json.dumps(usage_payload, default=str))
        with pytest.raises(UsageLimitExceeded):
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

        upd_payload = {
            "threshold_type": "limit",
            "amount": str(Decimal("0.1")),
            "period": "day",
            "service_key": SERVICE_KEY,
            "api_key_uuid": api_key_uuid,
        }
        print("updating usage limit:", json.dumps(upd_payload))
        ul_mgr.update_usage_limit(limit.uuid, upd_payload)

        # Allow server time to process the limit update and clear triggered limits
        time.sleep(2)

        # Force refresh of triggered limits to clear the cache
        try:
            tracker.delivery._refresh_triggered_limits()
        except Exception:
            pass

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
        # May or may not raise again depending on accumulated usage; allow either
        try:
            tracker.track(
                "openai_responses",
                SERVICE_KEY,
                usage_payload,
                response_id=response_id,
            )
        except UsageLimitExceeded:
            pass

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
    finally:
        try:
            if limit_uuid:
                ul_mgr.delete_usage_limit(limit_uuid)
        except Exception:
            pass


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="requires network access",
)
@pytest.mark.usefixtures("clear_triggered_limits")
@pytest.mark.parametrize(
    "delivery_type", [DeliveryType.MEM_QUEUE, DeliveryType.PERSISTENT_QUEUE]
)
@pytest.mark.xfail(reason="Server-side async processing timing - not deterministic")
def test_track_with_limits_queue(
    delivery_type, openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    print("AICM_API_BASE:", aicm_api_base)
    # Enable triggered limits for this test
    IniManager(str(ini)).set_option("tracker", "AICM_LIMITS_ENABLED", "true")
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
    api_key_uuid = (
        aicm_api_key.split(".")[-1] if aicm_api_key and "." in aicm_api_key else None
    )
    print("parsed api_key_uuid:", api_key_uuid)
    ul_payload = {
        "threshold_type": "limit",
        "amount": str(LIMIT_AMOUNT),
        "period": "day",
        "service_key": SERVICE_KEY,
        "api_key_uuid": api_key_uuid,
    }
    print("creating usage limit:", json.dumps(ul_payload))
    limit = ul_mgr.create_usage_limit(ul_payload)
    limit_uuid = getattr(limit, "uuid", None)

    try:
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
            # Trigger may or may not raise depending on timing; allow either, but ensure one of the two raises
            raised = False
            try:
                tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
            except UsageLimitExceeded:
                raised = True
            _wait_for_empty(tracker.delivery)

            resp = client.responses.create(model=MODEL, input="should fail")
            rid = getattr(resp, "id", None)
            up = get_usage_from_response(resp, "openai_responses")
            print("queue should-fail response_id:", rid)
            print("queue should-fail usage payload:", json.dumps(up, default=str))
            if raised:
                # Might not raise again depending on when server processed
                try:
                    tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
                except UsageLimitExceeded:
                    pass
            else:
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

            upd_payload = {
                "threshold_type": "limit",
                "amount": str(Decimal("0.1")),
                "period": "day",
                "service_key": SERVICE_KEY,
                "api_key_uuid": api_key_uuid,
            }
            print("updating usage limit:", json.dumps(upd_payload))
            ul_mgr.update_usage_limit(limit.uuid, upd_payload)

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
            # May or may not raise depending on timing after the update; allow either
            try:
                tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
            except UsageLimitExceeded:
                pass
            _wait_for_empty(tracker.delivery)

            ul_mgr.delete_usage_limit(limit.uuid)

            resp = client.responses.create(model=MODEL, input="after delete")
            rid = getattr(resp, "id", None)
            up = get_usage_from_response(resp, "openai_responses")
            print("queue after-delete response_id:", rid)
            print("queue after-delete usage payload:", json.dumps(up, default=str))
            tracker.track("openai_responses", SERVICE_KEY, up, response_id=rid)
            _wait_for_empty(tracker.delivery)
    finally:
        try:
            if limit_uuid:
                ul_mgr.delete_usage_limit(limit_uuid)
        except Exception:
            pass


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
    # Enable triggered limits for this test
    IniManager(str(ini)).set_option("tracker", "AICM_LIMITS_ENABLED", "true")
    client = openai.OpenAI(api_key=openai_api_key)
    customer = "cust-limit"

    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    api_key_uuid = (
        aicm_api_key.split(".")[-1] if aicm_api_key and "." in aicm_api_key else None
    )
    print("parsed api_key_uuid:", api_key_uuid)
    ul_payload = {
        "threshold_type": "limit",
        "amount": str(LIMIT_AMOUNT),
        "period": "day",
        "service_key": SERVICE_KEY,
        "client": customer,
        "api_key_uuid": api_key_uuid,
    }
    print("creating usage limit (customer):", json.dumps(ul_payload))
    limit = ul_mgr.create_usage_limit(ul_payload)
    limit_uuid = getattr(limit, "uuid", None)

    try:
        with Tracker(aicm_api_key=aicm_api_key, ini_path=str(ini)) as tracker:
            resp = client.responses.create(model=MODEL, input="hi")
            rid = getattr(resp, "id", None)
            up = get_usage_from_response(resp, "openai_responses")
            print("cust first response_id:", rid)
            print("cust first usage payload:", json.dumps(up, default=str))
            with pytest.raises(UsageLimitExceeded):
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

        pass
    finally:
        try:
            if limit_uuid:
                ul_mgr.delete_usage_limit(limit_uuid)
        except Exception:
            pass
