# AICostManager Python SDK

This package provides a thin wrapper around the AICostManager API.
Requests and responses are represented using Pydantic models so data is
validated before hitting the network.

```python
from aicostmanager import CostManagerClient as aicm
# use as a context manager to automatically close the session
with aicm() as client:
    ...

# async usage
from aicostmanager import AsyncCostManagerClient
# async with AsyncCostManagerClient() as client:
#     ...
```

`CostManagerClient` also implements the context manager protocol so the
underlying HTTP session is closed automatically when exiting the `with`
block.

By default the client reads configuration from environment variables.  You can pass
``proxies`` and extra ``headers`` when creating a client to suit enterprise
environments.  Errors from API calls raise ``APIRequestError`` which exposes
``error`` and ``message`` attributes parsed from the server response.

Configuration values can also be refreshed on demand using
``CostManagerConfig.refresh()`` or automatically on every call by setting
``auto_refresh=True`` when constructing ``CostManagerConfig``.

By default the client reads configuration from environment variables:

- `AICM_API_KEY` – API key used for authentication.
- `AICM_API_BASE` – base URL for the service (defaults to `https://aicostmanager.com`).
- `AICM_API_URL` – API path prefix (defaults to `/api/v1`).
- `AICM_INI_PATH` – path to the configuration INI file.

The combined base API URL is exposed via the `api_root` property on
`CostManagerClient`.

All endpoints documented in the project are available as methods on the
`CostManagerClient`.  Methods such as ``create_customer`` and
``create_usage_limit`` accept the corresponding models from
``aicostmanager.models`` and return typed objects. Pagination helpers
(``iter_usage_events``/``iter_usage_rollups``/``iter_customers``)
yield model instances across all pages. Typed list variants
(``list_usage_events_typed``, ``list_usage_rollups_typed`` and
``list_customers_typed``) return ``PaginatedResponse`` wrappers. Filter
models such as ``UsageEventFilters``, ``RollupFilters`` and
``CustomerFilters`` (which now include ``limit`` and ``offset`` fields)
can be provided to these methods to construct query parameters
automatically.

Refer to the [docs](docs/USAGE.md) for full examples.

## Tracking Wrapper

`CostManager` can wrap any API/LLM client and, using configuration
retrieved from `CostManagerConfig`, extract request and response data.
Payloads are queued and sent asynchronously via a single background
worker so tracking calls never block your application.
See [docs/TRACKING.md](docs/TRACKING.md) for a brief overview. ``CostManager``
is also a context manager so you can ``with CostManager(client)`` and the
delivery queue will start and stop automatically.

The worker batches queued payloads and retries failed requests with
exponential backoff.  The queue size, retry limit and request timeout
can be customised via ``delivery_queue_size``, ``delivery_max_retries``
and ``delivery_timeout`` when constructing ``CostManager``.

## Configuration Helper

Use `CostManagerConfig` to manage encrypted tracker configuration data stored in
`AICM.ini`:

```python
from aicostmanager import CostManagerClient, CostManagerConfig

client = CostManagerClient()
cfg = CostManagerConfig(client)
configs = cfg.get_config("python-client")
limits = cfg.get_triggered_limits(service_id="gpt-4")
```
