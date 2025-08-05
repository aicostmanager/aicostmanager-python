# Tracking Usage with `CostManager`

`CostManager` provides a small wrapper around any API client so that the
client's activity can be analysed.  It relies on configuration returned
from `CostManagerConfig` which describes how requests and responses
should be inspected.  The heavy lifting of turning that configuration
into data is handled by `UniversalExtractor`.

## Basic Workflow

1. Instantiate `CostManager` with the API client you wish to monitor.
2. On construction the wrapper fetches configuration for the client's
   `api_id` (the name of the client's class in lower case).
3. The wrapper creates a single `UniversalExtractor` with those
   configurations.
4. Every method call on the wrapped client is proxied through the
   extractor which returns payload dictionaries.
5. Those payloads are queued and delivered in the background to the
   `/track-usage` endpoint using a global worker thread.

## Handling Configuration

A handling configuration describes which methods should be tracked and
how to map request/response fields into a payload.  A very small example
is shown below:

```json
{
  "tracked_methods": ["add"],
  "request_fields": ["a", "b"],
  "response_fields": [{"key": "value", "path": ""}],
  "payload_mapping": {
    "config": "config_identifier",
    "timestamp": "timestamp",
    "usage": "response_data.value"
  },
  "static_payload_fields": {"static": 1}
}
```

This configuration tracks calls to a method named `add`, records the
keyword arguments `a` and `b`, stores the raw response value under the
`value` key and finally maps a few items into the payload that would be
sent to the AICostManager service.

When creating your own ``handling_config`` make sure the
``payload_mapping`` keys correspond to fields extracted by the
``UniversalExtractor``.  The mapping should resolve to a dictionary that
matches the ``ApiUsageRecord`` schema as documented in the API.

## Limitations

The implementation focuses on reliability rather than throughput.
Payloads are sent via a background thread with a bounded queue so that
usage tracking will not exhaust memory when used inside a web
application.  The queue size and retry policy can be tuned via
``CostManager`` parameters. When the queue is full the default behaviour
is to drop the oldest payload and log a warning. Set
``delivery_on_full`` to ``"block"`` to wait for space or ``"raise"`` to
propagate ``queue.Full`` back to the caller.

``ResilientDelivery`` uses the client's ``api_root`` to construct the
``/track-usage`` URL.  Payloads added to the queue are batched whenever
possible and sent with a configurable timeout (default 10 seconds).

## Selecting Delivery Mode

``ResilientDelivery`` supports two modes:

* **sync** (default) – uses a standard ``requests`` session.
* **async** – performs delivery using ``httpx.AsyncClient`` together with
  ``tenacity.AsyncRetrying`` for non-blocking retries.

Set ``AICM_DELIVERY_MODE=async`` (or pass ``delivery_mode="async"`` when
constructing ``CostManager``/``RestCostManager``) to enable the async mode.
This is useful for eventlet or gevent worker pools where blocking network
operations should be avoided.

An asynchronous variant ``AsyncCostManager`` is available for wrapping
async API clients.  It behaves the same as ``CostManager`` but uses an
``asyncio`` delivery queue and ``AsyncCostManagerClient`` for network
requests:

```python
from aicostmanager import AsyncCostManager, AsyncCostManagerClient

async with AsyncCostManagerClient() as client:
    async with AsyncCostManager(client) as tracker:
        await tracker.client.some_call()
```

## Multiprocessing Environments

In applications that fork worker processes (such as those using the
``multiprocessing`` module or Celery), create the ``CostManager`` instance
inside a worker-initialisation hook. This ensures each worker has its own
delivery thread and avoids race conditions when processes start.
