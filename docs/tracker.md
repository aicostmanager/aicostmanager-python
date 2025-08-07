# Manual Usage Tracking with `Tracker`

`Tracker` lets you send usage records directly to AICostManager when you
cannot or do not want to wrap an API client with `CostManager`.
It loads a manual usage schema from the service configuration to validate
payloads before delivery.

## Creating a Tracker

```python
from aicostmanager import Tracker

tracker = Tracker("cfg", "svc")
```

* ``cfg`` – configuration identifier returned from ``/configs``
* ``svc`` – the service identifier your usage belongs to

The tracker automatically loads the manual usage schema for the given
configuration.  If the schema declares required fields or types they will be
validated when calling :meth:`track`.

### Asynchronous factory

Configuration loading uses blocking I/O.  In async applications use the
factory to perform the setup in a thread:

```python
tracker = await Tracker.create_async("cfg", "svc")
```

The returned instance is ready to use inside your async code.

## Recording Usage

```python
usage = {"tokens": 10, "model": "gpt"}
tracker.track(usage, client_customer_key="cust1", context={"task": "demo"})
```

``client_customer_key`` associates the record with one of your customers and
``context`` allows attaching arbitrary metadata.  The tracker builds the payload
and queues it for background delivery.

If the usage dictionary does not match the schema a
:class:`UsageValidationError` is raised detailing the missing or invalid fields.

## Stopping the delivery worker

The tracker shares the global delivery worker by default.  To shut it down
cleanly, call ``close`` during application shutdown:

```python
tracker.close()
```

## FastAPI example

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

The tracker instance is created once at startup, re-used for incoming requests
and closed when the application exits.
