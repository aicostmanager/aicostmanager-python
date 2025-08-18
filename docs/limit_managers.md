# Limit Managers

The library provides separate managers for usage limits and triggered limit
notifications.

## Managing Usage Limits

Use the :class:`UsageLimitManager` to create and maintain limits via the
API:

```python
from aicostmanager import (
    CostManagerClient,
    UsageLimitManager,
    UsageLimitIn,
    ThresholdType,
    Period,
)

client = CostManagerClient(aicm_api_key="sk-test")
limits = UsageLimitManager(client)

# Create a monthly team limit
limit = limits.create_usage_limit(
    UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=1000,
        period=Period.MONTH,
        team_uuid="team-uuid",
    )
)

# List and update limits
for lim in limits.list_usage_limits():
    print(lim.uuid, lim.amount)

limits.update_usage_limit(
    limit.uuid,
    UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=2000,
        period=Period.MONTH,
        team_uuid="team-uuid",
    ),
)

# View current spend versus configured limits
for prog in limits.list_usage_limit_progress():
    print(prog.current_spend, prog.remaining_amount)

# Delete when finished
limits.delete_usage_limit(limit.uuid)
```

## Working with Triggered Limits

Triggered limit events can be cached locally using the
:class:`TriggeredLimitManager` so they can be checked without an additional
API call:

```python
from aicostmanager import CostManagerClient, TriggeredLimitManager

client = CostManagerClient(aicm_api_key="sk-test")
tl_mgr = TriggeredLimitManager(client)

# Refresh the local cache of triggered limits
tl_mgr.update_triggered_limits()

# Filter triggered events for an API key and service
events = tl_mgr.check_triggered_limits(
    api_key_id="550e8400-e29b-41d4-a716-446655440000",
    service_key="openai::gpt-4",
)
for event in events:
    print(event["limit_id"], event["threshold_type"])
```
