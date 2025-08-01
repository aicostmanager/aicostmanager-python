import time

import pytest
import requests

openai = pytest.importorskip("openai")

from aicostmanager import (
    CostManager,
    CostManagerClient,
    Period,
    ThresholdType,
    UsageLimitIn,
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

    # Find gpt-3.5-turbo service specifically (since that's what we call)
    gpt35_service = None
    for svc in services:
        if svc.service_id == "gpt-3.5-turbo":
            gpt35_service = svc
            break

    if not gpt35_service:
        pytest.skip("gpt-3.5-turbo service not found - cannot test limit enforcement")

    service = gpt35_service

    limit = client.create_usage_limit(
        UsageLimitIn(
            threshold_type=ThresholdType.LIMIT,
            amount=0.00004,  # $0.01 - should allow first call but trigger on subsequent calls
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

        # first call should succeed
        print("Making initial API call...")
        tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        print("Initial call completed successfully")
        time.sleep(2)

        # subsequent calls expected to exceed limit (may take multiple calls)
        print("Starting loop to trigger usage limit (max 100 attempts)...")
        exception_raised = False
        for i in range(10):
            try:
                print(f"Attempt {i + 1}/100: Making API call...")
                tracked_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": f"hi again {i}"}],
                    max_tokens=5,
                )
                print(f"Attempt {i + 1}/100: Call completed")

                # Check for triggered limits after each call
                triggered_limits = tracked_client.config_manager.get_triggered_limits(
                    service_id=service.service_id
                )
                if triggered_limits:
                    print(
                        f"Attempt {i + 1}/100: Found {len(triggered_limits)} triggered limits!"
                    )
                    for tl in triggered_limits:
                        print(
                            f"  - Limit {tl.limit_id}: {tl.threshold_type}, amount: {tl.amount}"
                        )
                else:
                    print(f"Attempt {i + 1}/100: No triggered limits detected yet")

                time.sleep(2)  # Give server time to process usage
            except Exception as e:
                print(f"Attempt {i + 1}/100: Exception raised: {type(e).__name__}: {e}")
                exception_raised = True
                break

        if not exception_raised:
            print(
                "Loop completed without exception - checking final triggered limits..."
            )
            final_triggered = tracked_client.config_manager.get_triggered_limits(
                service_id=service.service_id
            )
            print(f"Final triggered limits count: {len(final_triggered)}")

        assert exception_raised, (
            "Expected an exception to be raised within 100 attempts"
        )

        # refresh triggered limits and check limit uuid
        triggered = tracked_client.config_manager.get_triggered_limits(
            service_id=service.service_id
        )
        assert any(t.limit_id == limit.uuid for t in triggered)
    finally:
        client.delete_usage_limit(limit.uuid)
        pass
