# Using the Python SDK

Install with:

```bash
# Using uv (recommended)
uv pip install aicostmanager
# or add to a project
uv add aicostmanager
```

Create a client:

```python
from aicostmanager import CostManagerClient
client = CostManagerClient()

# asynchronous
from aicostmanager import AsyncCostManagerClient
# async with AsyncCostManagerClient() as client:
#     ...
```

You can override defaults when instantiating:

```python
client = aicm(
    aicm_api_key="sk-api01-...",
    aicm_api_base="https://staging.aicostmanager.com",
    aicm_api_url="/api/v1",
    aicm_ini_path="/path/to/AICM.INI",
    proxies={"http": "http://proxy"},
    headers={"X-Test": "1"},
)
```

Example request:

```python
from datetime import date
from aicostmanager.models import CustomerIn, UsageEventFilters

new_customer = CustomerIn(client_customer_key="cust1", name="Example")
created = client.create_customer(new_customer)
print(created.uuid)

filters = UsageEventFilters(client_customer_key="cust1", start_date=date(2024, 1, 1), limit=100)
for event in client.iter_usage_events(filters):
    print(event.event_id)

```

## FastAPI integration

See [Manual Usage Tracking](tracker.md) for a detailed guide on using the `Tracker` class.

When recording custom usage with :class:`Tracker` in a FastAPI application,
create the tracker during application startup so configuration loading doesn't
block individual requests. The asynchronous factory ``Tracker.create_async``
performs the initialization in a thread and returns a ready instance. During
shutdown, stop the background delivery using ``Tracker.close``:

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


## Vendor & Service Lookup

You can retrieve available vendors and their services:

```python
vendors = client.list_vendors()
for vendor in vendors:
    print(vendor.name)
    services = client.list_vendor_services(vendor.uuid)
    for svc in services:
        print(" -", svc.service_id)
```

## Tracking Plain REST APIs

Use ``RestCostManager`` (or ``AsyncRestCostManager`` for async) to track any
service accessed via ``requests`` or ``httpx``:

```python
import requests
from aicostmanager import RestCostManager

session = requests.Session()
tracker = RestCostManager(session, base_url="https://api.heygen.com")
data = tracker.get("/v2/streaming.list").json()
```

The wrapper automatically extracts payloads from each call and sends them to
AICostManager.

