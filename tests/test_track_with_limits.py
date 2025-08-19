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

MODEL = "gpt-5-mini"
SERVICE_KEY = f"openai::{MODEL}"
OTHER_MODEL = "gpt-4o-mini"
LIMIT_AMOUNT = Decimal("0.0000001")


def _wait_for_empty(delivery, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = getattr(delivery, "stats", lambda: {})()
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
    tracker = Tracker(aicm_api_key=aicm_api_key, ini_path=str(ini))
    client = openai.OpenAI(api_key=openai_api_key)

    resp = client.responses.create(model=MODEL, input="hi")
    tracker.track_llm_usage("openai_responses", resp)

    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    limit = ul_mgr.create_usage_limit(
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=LIMIT_AMOUNT,
            period=Period.DAY,
            vendor="openai",
            service=MODEL,
        )
    )

    resp = client.responses.create(model=MODEL, input="trigger")
    tracker.track_llm_usage("openai_responses", resp)

    resp = client.responses.create(model=MODEL, input="should fail")
    with pytest.raises(UsageLimitExceeded):
        tracker.track_llm_usage("openai_responses", resp)

    with Tracker(aicm_api_key=aicm_api_key, ini_path=str(ini)) as t2:
        resp_other = client.responses.create(model=OTHER_MODEL, input="other")
        t2.track_llm_usage("openai_responses", resp_other)

    ul_mgr.update_usage_limit(
        limit.uuid,
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=Decimal("0.1"),
            period=Period.DAY,
            vendor="openai",
            service=MODEL,
        ),
    )

    resp = client.responses.create(model=MODEL, input="after raise")
    tracker.track_llm_usage("openai_responses", resp)

    resp = client.responses.create(model=MODEL, input="raise again")
    with pytest.raises(UsageLimitExceeded):
        tracker.track_llm_usage("openai_responses", resp)

    ul_mgr.delete_usage_limit(limit.uuid)

    resp = client.responses.create(model=MODEL, input="after delete")
    tracker.track_llm_usage("openai_responses", resp)

    tracker.close()


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="requires network access",
)
@pytest.mark.usefixtures("clear_triggered_limits")
@pytest.mark.parametrize("delivery_type", [DeliveryType.MEM_QUEUE, DeliveryType.PERSISTENT_QUEUE])
def test_track_with_limits_queue(
    delivery_type, openai_api_key, aicm_api_key, aicm_api_base, tmp_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    ini = tmp_path / "AICM.ini"
    dconfig = DeliveryConfig(
        ini_manager=IniManager(str(ini)),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    extra = {"batch_interval": 0.1}
    if delivery_type is DeliveryType.PERSISTENT_QUEUE:
        extra.update({"db_path": str(tmp_path / "queue.db"), "poll_interval": 0.1})
    delivery = create_delivery(delivery_type, dconfig, **extra)

    client = openai.OpenAI(api_key=openai_api_key)
    cm_client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=str(ini),
    )
    ul_mgr = UsageLimitManager(cm_client)
    limit = ul_mgr.create_usage_limit(
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=LIMIT_AMOUNT,
            period=Period.DAY,
            vendor="openai",
            service=MODEL,
        )
    )

    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=str(ini), delivery=delivery
    ) as tracker:
        resp = client.responses.create(model=MODEL, input="hi")
        tracker.track_llm_usage("openai_responses", resp)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="trigger")
        tracker.track_llm_usage("openai_responses", resp)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="should fail")
        with pytest.raises(UsageLimitExceeded):
            tracker.track_llm_usage("openai_responses", resp)
        _wait_for_empty(tracker.delivery)

        with Tracker(
            aicm_api_key=aicm_api_key,
            ini_path=str(ini),
            delivery=create_delivery(delivery_type, dconfig, **extra),
        ) as t2:
            resp_other = client.responses.create(model=OTHER_MODEL, input="other")
            t2.track_llm_usage("openai_responses", resp_other)
            _wait_for_empty(t2.delivery)

        ul_mgr.update_usage_limit(
            limit.uuid,
            UsageLimitIn(
                threshold_type=ThresholdType.LIMIT,
                amount=Decimal("0.1"),
                period=Period.DAY,
                vendor="openai",
                service=MODEL,
            ),
        )

        resp = client.responses.create(model=MODEL, input="after raise")
        tracker.track_llm_usage("openai_responses", resp)
        _wait_for_empty(tracker.delivery)

        resp = client.responses.create(model=MODEL, input="raise again")
        with pytest.raises(UsageLimitExceeded):
            tracker.track_llm_usage("openai_responses", resp)
        _wait_for_empty(tracker.delivery)

        ul_mgr.delete_usage_limit(limit.uuid)

        resp = client.responses.create(model=MODEL, input="after delete")
        tracker.track_llm_usage("openai_responses", resp)
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
    limit = ul_mgr.create_usage_limit(
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=LIMIT_AMOUNT,
            period=Period.DAY,
            vendor="openai",
            service=MODEL,
            client=customer,
        )
    )

    resp = client.responses.create(model=MODEL, input="hi")
    tracker.track_llm_usage(
        "openai_responses", resp, client_customer_key=customer
    )

    resp = client.responses.create(model=MODEL, input="should fail")
    with pytest.raises(UsageLimitExceeded):
        tracker.track_llm_usage(
            "openai_responses", resp, client_customer_key=customer
        )

    ul_mgr.delete_usage_limit(limit.uuid)

    resp = client.responses.create(model=MODEL, input="after delete")
    tracker.track_llm_usage(
        "openai_responses", resp, client_customer_key=customer
    )

    tracker.close()
