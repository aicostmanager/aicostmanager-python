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
    clean_delivery,
):
    import os

    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not _endpoint_live(aicm_api_base):
        pytest.skip("AICM endpoint not reachable")

    # Ensure clean start - delete INI file if it exists to prevent interference from other tests
    if os.path.exists(aicm_ini_path):
        os.remove(aicm_ini_path)
        print(f"Deleted existing INI file: {aicm_ini_path}")

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

        # Get the actual service_id used by the tracked call (e.g., gpt-3.5-turbo-0125)
        payloads = tracked_client.get_tracked_payloads()
        assert payloads, "No payloads tracked for initial call"
        actual_service_id = payloads[-1].get("service_id")
        assert actual_service_id, "No service_id in tracked payload"
        print(f"Actual service_id used: {actual_service_id}")

        # Find the service object for the actual service_id
        actual_service = None
        for svc in services:
            if svc.service_id == actual_service_id:
                actual_service = svc
                break

        if not actual_service:
            # Fallback to original service if not found
            actual_service = service
            actual_service_id = service.service_id

        # Compute cost using tracked payload usage and current service costs from the API
        usage = payloads[-1].get("usage", {})
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = (
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        costs = {
            c.name: c
            for c in client.list_service_costs(openai_vendor.name, actual_service_id)
        }

        def _unit_cost(name: str) -> float:
            c = costs.get(name)
            if not c:
                return 0.0
            # cost is per 'per_quantity' units
            return float(c.cost) / max(int(c.per_quantity), 1)

        first_call_cost = prompt_tokens * _unit_cost(
            "prompt_tokens"
        ) + completion_tokens * _unit_cost("completion_tokens")
        # Fallback if names differ
        if first_call_cost == 0:
            first_call_cost = prompt_tokens * _unit_cost(
                "input_tokens"
            ) + completion_tokens * _unit_cost("output_tokens")
        # Add a 20% headroom so the first call stays under the limit
        dynamic_limit_amount = max(first_call_cost * 1.2, first_call_cost + 1e-8)

        print(
            f"Setting limit: ${dynamic_limit_amount:.8f} for service {actual_service_id}"
        )
        limit = client.create_usage_limit(
            UsageLimitIn(
                threshold_type=ThresholdType.LIMIT,
                amount=dynamic_limit_amount,
                period=Period.DAY,
                vendor=openai_vendor.name,
                service=actual_service_id,  # Use the actual service_id
            )
        )

        # subsequent calls expected to exceed limit (may take multiple calls)
        print("Starting loop to trigger usage limit (max 10 attempts)...")
        exception_raised = False
        for i in range(10):
            try:
                print(f"Attempt {i + 1}/10: Making API call...")
                tracked_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": f"hi again {i}"}],
                    max_tokens=5,
                )
                print(f"Attempt {i + 1}/10: Call completed")

                # Check for triggered limits after each call
                triggered_limits = tracked_client.config_manager.get_triggered_limits(
                    service_id=actual_service_id  # Use the actual service_id
                )
                if triggered_limits:
                    print(
                        f"Attempt {i + 1}/10: Found {len(triggered_limits)} triggered limits!"
                    )
                    for tl in triggered_limits:
                        print(
                            f"  - Limit {tl.limit_id}: {tl.threshold_type}, amount: {tl.amount}"
                        )
                else:
                    print(f"Attempt {i + 1}/10: No triggered limits detected yet")

                time.sleep(2)  # Give server time to process usage
            except Exception as e:
                print(f"Attempt {i + 1}/10: Exception raised: {type(e).__name__}: {e}")
                exception_raised = True
                break

        if not exception_raised:
            print(
                "Loop completed without exception - checking final triggered limits..."
            )
            final_triggered = tracked_client.config_manager.get_triggered_limits(
                service_id=actual_service_id  # Use the actual service_id
            )
            print(f"Final triggered limits count: {len(final_triggered)}")

        assert exception_raised, "Expected an exception to be raised within 10 attempts"

        # refresh triggered limits and check limit uuid
        triggered = tracked_client.config_manager.get_triggered_limits(
            service_id=actual_service_id  # Use the actual service_id
        )
        assert any(t.limit_id == limit.uuid for t in triggered)
    finally:
        client.delete_usage_limit(limit.uuid)
        pass
