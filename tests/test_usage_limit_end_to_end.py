import time
import requests
import pytest

openai = pytest.importorskip("openai")

from aicostmanager import (
    CostManager,
    CostManagerClient,
    UsageLimitIn,
    ThresholdType,
    Period,
)


def _endpoint_live(base_url: str) -> bool:
    try:
        resp = requests.get(f"{base_url}/api/v1/openapi.json", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def test_usage_limit_end_to_end(
    aicm_api_key,
    aicm_api_base,
    aicm_ini_path,
    openai_api_key,
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not _endpoint_live(aicm_api_base):
        pytest.skip("AICM endpoint not reachable")

    client = CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    vendors = list(client.list_vendors())
    assert vendors, "No vendors returned"
    openai_vendor = next((v for v in vendors if v.name.lower() == "openai"), None)
    assert openai_vendor is not None, "OpenAI vendor not found"

    services = list(client.list_vendor_services(openai_vendor.name))
    assert services, "No services for OpenAI vendor"
    service = services[0]

    limit = client.create_usage_limit(
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=1,
            period=Period.DAY,
            vendor=openai_vendor.name,
            service=service.service_id,
        )
    )

    try:
        tracked_client = CostManager(
            openai.OpenAI(api_key=openai_api_key),
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_ini_path=aicm_ini_path,
        )

        # ensure configs updated with new limit info
        tracked_client.config_manager.refresh()

        # first call should succeed
        tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        time.sleep(2)

        # second call expected to exceed limit
        with pytest.raises(Exception):
            tracked_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "hi again"}],
                max_tokens=5,
            )
        time.sleep(2)

        # refresh triggered limits and check limit uuid
        triggered = tracked_client.config_manager.get_triggered_limits(
            service_id=service.service_id
        )
        assert any(t.limit_id == limit.uuid for t in triggered)
    finally:
        client.delete_usage_limit(limit.uuid)
