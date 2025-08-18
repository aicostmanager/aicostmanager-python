# Limits Manager

The `LimitsManager` wraps the AICostManager usage limit endpoints and
provides convenience helpers for working with both configured limits and
triggered limit events stored in the local `AICM.ini` file.

## Managing Usage Limits

Usage limits can be scoped to a team, individual user or a specific API
key.  Create and manage limits through the manager which delegates to the
underlying :class:`~aicostmanager.client.CostManagerClient`.

```python
from aicostmanager import (
    CostManagerClient,
    LimitsManager,
    UsageLimitIn,
    ThresholdType,
    Period,
)

client = CostManagerClient(aicm_api_key="sk-test")
limits = LimitsManager(client)

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

The manager can also cache triggered limit events in the INI file so they
can be checked locally without another API call.

```python
# Refresh the local cache of triggered limits
limits.update_triggered_limits()

# Filter triggered events for an API key and service
events = limits.check_triggered_limits(
    api_key_id="550e8400-e29b-41d4-a716-446655440000",
    service_key="openai::gpt-4",
)
for event in events:
    print(event["limit_id"], event["threshold_type"])
```
