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
cfg = CostManagerConfig(client, auto_refresh=True)
cfg.refresh()

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

