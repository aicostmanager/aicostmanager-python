# Manual Usage Tracking (`Tracker`)

Use the `Tracker` to record custom usage events that are not tied to a wrapped SDK call. This is useful for batch jobs, internal tools, custom metrics, or any workflow where you want full control over the `usage` payload.

## Overview

- Validates your payload against a configuration-provided `manual_usage_schema`
- Uses the same resilient delivery queue and retry logic as `CostManager`
- Supports client context via `client_customer_key` and `context`
- Async factory for non-blocking initialization in web apps
- `close()` method for graceful shutdown

## Basic Usage

```python
from aicostmanager import Tracker

tracker = Tracker(
    config_id="your-config-id",
    service_id="your-service-id",
)

tracker.track({
    "tokens": 256,
    "model": "gpt-4o-mini",
})
```

## Validation and Errors

If your configuration includes a `manual_usage_schema`, values are validated with the built-in `TypeValidator`. When validation fails a `UsageValidationError` is raised summarizing issues:

```python
from aicostmanager import Tracker, UsageValidationError

try:
    tracker.track({"tokens": "oops"})
except UsageValidationError as exc:
    print(exc.errors, exc.missing_fields, exc.extra_fields)
```

Supported type strings include:

- Basic: `int`, `float`, `str`, `bool`, `list`, `dict`, `tuple`, `set`
- Collections: `List[T]`, `Dict[K, V]`
- Optional and unions: `Optional[T]`, `Union[A, B, ...]`

## Client Context

```python
tracker.track(
    {"duration": 12.3},
    client_customer_key="acme_corp",
    context={"project": "chatbot_v2", "env": "prod"},
)
```

## Async Initialization (Web Apps)

```python
from aicostmanager import Tracker

tracker = await Tracker.create_async("cfg", "svc")
# ... use tracker.track(...)
tracker.close()  # during shutdown
```

### FastAPI Example

```python
from fastapi import FastAPI
from aicostmanager import Tracker

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    app.state.tracker = await Tracker.create_async("cfg", "svc")

@app.on_event("shutdown")
def shutdown() -> None:
    app.state.tracker.close()

@app.post("/track")
async def track_usage(payload: dict) -> dict:
    app.state.tracker.track(payload)
    return {"status": "ok"}
```

## Delivery Behavior & Metrics

The tracker uses the global delivery queue. You can configure behavior when the queue is full with `delivery_on_full` or the `AICM_DELIVERY_ON_FULL` environment variable (`block`, `raise`, `backpressure`). When using backpressure, dropped payloads are counted and optionally reported via an `on_discard` callback.

Inspect metrics:

```python
from aicostmanager import get_global_delivery_health
print(get_global_delivery_health())
```

## Configuration Requirements

`Tracker` needs a `config_id` and `service_id` that correspond to entries provisioned in your AICostManager configuration. If a `manual_usage_schema` is defined for the config, payloads must conform to it.

