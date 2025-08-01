# Using the Python SDK

Install with:

```bash
pip install aicostmanager
```

Create a client:

```python
from aicostmanager import CostManagerClient as aicm
client = aicm()

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

# manually refresh configuration
cfg = CostManagerConfig(client)
cfg.refresh()

# subsequent calls can use the ETag header for caching
cfgs = client.get_configs()
etag = client.configs_etag
unchanged = client.get_configs(etag=etag)  # returns None when unchanged

The `/configs` endpoint returns an `ETag` header. Send this value back in
`If-None-Match` to avoid downloading configuration when nothing has changed.
If the configuration is unchanged, the SDK will still refresh the
`triggered_limits` section by calling `/triggered-limits`.
Triggered limit information is read from `AICM.INI` each time it is needed and
is fetched from the server only when the client is initialized (including the
etag check described above) or when usage is recorded via the `/track-usage`
endpoint.

# using CostManager with automatic delivery
from aicostmanager import CostManager

with CostManager(client) as manager:
    manager.client.list_customers()
    # payloads delivered in background

# asynchronous tracking
from aicostmanager import AsyncCostManager, AsyncCostManagerClient

async def async_example():
    async with AsyncCostManagerClient() as aclient:
        async with AsyncCostManager(aclient) as manager:
            await manager.client.list_customers()
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
AICostManager just like when using ``CostManager``.

