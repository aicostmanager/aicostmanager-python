# Querying Costs

This guide walks through how to retrieve cost events that were already tracked
by another service or teammate. You do **not** need to understand or run the
cost-tracking portion of AICostManager to follow along—you only need access to
the API key that grants read permissions to the data. The
:class:`~aicostmanager.costs.CostQueryManager` provides a friendly wrapper
around the ``/costs`` HTTP endpoint exposed by the AICostManager backend.

The examples below cover:

* Authenticating by providing the API key explicitly, via environment
  variables, or by using a ``.env`` file.
* Querying costs across a team (multiple API keys).
* Filtering by one or more ``customer_key`` values.
* Filtering using context metadata stored on each cost event.
* Interpreting the returned response objects and individual event payloads.
* Calling the API directly with `curl` if you prefer raw HTTP over the Python
  helper.

## Prerequisites

1. **Install the client library**

   ```bash
   pip install aicostmanager
   ```

2. **Obtain an AICM API key** from the teammate or system that manages cost
   tracking. Keys are scoped; make sure the key has read access to the cost
   data you need.

3. **Optional: create a `.env` file** if you want to load environment variables
   automatically.

   ```bash
   echo "AICM_API_KEY=sk_live_123..." > .env
   ```

   The :class:`~aicostmanager.costs.CostQueryManager` loads variables from the
   environment, so consider using a secrets manager or your shell profile
   instead of committing `.env` to source control.

## Authenticating with the CostQueryManager

You can instantiate the manager in several ways depending on how you manage
credentials.

### Read from environment variables

If ``AICM_API_KEY`` is exported in your shell or sourced from a `.env` file,
you can create the manager without passing any arguments:

```python
from aicostmanager import CostQueryManager

manager = CostQueryManager()  # automatically reads the AICM_API_KEY variable
```

### Pass the key explicitly

If you prefer to pass the key at runtime, provide it via the ``api_key``
parameter. This is useful in scripts or notebooks where you already loaded the
secret through another channel.

```python
from aicostmanager import CostQueryManager

manager = CostQueryManager(api_key="sk_live_123...")
```

### Use alternative environment variable names

Set ``AICM_API_KEY`` directly or override it using the
``AICOSTMANAGER_API_KEY`` alias. Both are recognized:

```bash
export AICOSTMANAGER_API_KEY=sk_live_123...
python my_query_script.py
```

### Load from operating system key stores

Any approach that results in ``AICM_API_KEY`` being present in the process
environment works, including injecting the variable through container secrets
or orchestration platforms. The manager simply reads ``os.environ`` when it is
constructed.

## Constructing Filters

The manager accepts filters as either:

* A plain dictionary using the same keys as the HTTP query string.
* An instance of :class:`~aicostmanager.models.CostEventFilters` for
  dataclass-style validation and autocompletion.

### Basic date and service filters

```python
from datetime import date
from aicostmanager.models import CostEventFilters

filters = CostEventFilters(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
    service_key=["openai::gpt-4o"],
    limit=100,
)
page = manager.list_costs_typed(filters)
print("Total events:", page.count)
```

### Querying across a team (multiple API keys)

If your organization issues individual API keys per teammate or system,
include them all in the ``api_key_id`` filter. Each identifier corresponds to
the API key UUID shown in the AICostManager dashboard.

```python
team_filters = {
    "api_key_id": [
        "11111111-2222-3333-4444-555555555555",  # teammate A
        "66666666-7777-8888-9999-000000000000",  # teammate B
    ],
    "start_date": "2025-02-01",
    "end_date": "2025-02-28",
}

team_page = manager.list_costs(team_filters)
print(team_page["count"], "events found for the team")
```

You can also combine team-wide filters with service or customer filters to
slice the data further.

### Filtering by one or more ``customer_key`` values

Cost events can be tagged with a ``customer_key`` to attribute usage to your
downstream customers. Provide a single value or a list to match multiple
customers:

```python
filters = {
    "customer_key": ["acme-enterprise", "contoso-retail"],
    "start_date": "2025-03-01",
    "end_date": "2025-03-31",
}

for event in manager.iter_costs(filters):
    print(event.service_key, event.cost)
```

When only one customer matters, pass a string instead of a list:

```python
solo_filters = {"customer_key": "acme-enterprise", "limit": 25}
page = manager.list_costs_typed(solo_filters)
```

### Filtering by context metadata

Every cost event can include additional metadata stored under the ``context``
namespace. To query by a context value, prefix the key with ``context.``.

```python
# Match events where context.project == "alpha" and context.region == "us-east"
context_filters = {
    "context.project": "alpha",
    "context.region": "us-east",
    "start_date": "2025-01-01",
}

events = list(manager.iter_costs(context_filters))
print(f"Found {len(events)} project alpha events")
```

Context filters support partial matching via wildcards (``*``) for text
fields. For example, ``{"context.notes": "*migration*"}`` matches any event
whose ``notes`` context contains the word "migration".

### Mixing filters together

Combine the above approaches to answer complex questions:

```python
filters = {
    "api_key_id": "11111111-2222-3333-4444-555555555555",
    "customer_key": "enterprise-plan",
    "service_key": "anthropic::claude-3",
    "start_date": "2025-02-01",
    "end_date": "2025-02-15",
    "context.team": "research",
}

for event in manager.iter_costs(filters):
    print(event.service_key, event.cost)
```

## Retrieving Results

The manager offers two main retrieval patterns.

### ``list_costs`` and ``list_costs_typed`` (paged results)

These methods request a single page of results. The untyped version returns a
dictionary mirroring the raw HTTP response, while the typed version returns a
:class:`~aicostmanager.models.CostEventsResponse` dataclass.

```python
page = manager.list_costs_typed(filters)

print("Total matching events:", page.count)
print("Next page URL:", page.next)

for event in page.results:
    print(event.provider_id, event.cost)
```

### ``iter_costs`` (auto-pagination)

Use :meth:`~aicostmanager.costs.CostQueryManager.iter_costs` when you want to
iterate through all matching events regardless of page size. It lazily fetches
additional pages as needed.

```python
total_cost = 0
for event in manager.iter_costs(filters):
    total_cost += event.cost

print("Aggregate cost:", total_cost)
```

When you are done querying, close the manager to release network resources:

```python
manager.close()
```

## Understanding the Response Schema

The paginated response contains these top-level fields:

* ``count`` – total number of events that match the filters.
* ``next`` – URL to fetch the next page, or ``None`` if you are on the last
  page.
* ``previous`` – URL for the previous page, if available.
* ``results`` – list of cost events for the current page.

Each cost event in the typed iterator is a
:class:`~aicostmanager.models.CostEventItem` with the following attributes:

| Field | Type | Description |
| ----- | ---- | ----------- |
| ``provider_id`` | ``str`` | Identifier of the upstream provider (e.g., ``openai``). |
| ``service_key`` | ``str`` | Specific service or model (e.g., ``openai::gpt-4o``). |
| ``cost_unit_id`` | ``str`` | Unit of measure (e.g., ``usd`` or a custom unit). |
| ``quantity`` | ``Decimal`` | Number of units consumed. |
| ``cost_per_unit`` | ``Decimal`` | Price per unit. |
| ``cost`` | ``Decimal`` | Total cost (``quantity * cost_per_unit``). |

When you call :meth:`list_costs` (the untyped variant), the raw dictionary may
include additional keys such as ``id``, ``timestamp``, ``api_key_id``,
``customer_key``, ``context`` metadata, and provider-specific ``metadata``. You
can access these by working with the dictionary directly or by reading from the
``results`` list in the JSON response.

### Example JSON response

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "8f4f9d5c-0305-4b19-9cf2-104631e33731",
      "timestamp": "2025-03-15T12:34:56.789Z",
      "provider_id": "openai",
      "service_key": "openai::gpt-4o",
      "api_key_id": "11111111-2222-3333-4444-555555555555",
      "customer_key": "acme-enterprise",
      "cost_unit_id": "usd",
      "quantity": "1234.567",
      "cost_per_unit": "0.0005",
      "cost": "0.6173",
      "context": {
        "project": "alpha",
        "team": "research",
        "region": "us-east"
      },
      "metadata": {
        "prompt_tokens": 812,
        "completion_tokens": 1544,
        "response_time_ms": 523
      }
    },
    {
      "id": "ca741cee-b644-4d07-a979-2e4fba2b5f26",
      "timestamp": "2025-03-15T13:01:22.110Z",
      "provider_id": "anthropic",
      "service_key": "anthropic::claude-3",
      "api_key_id": "66666666-7777-8888-9999-000000000000",
      "customer_key": null,
      "cost_unit_id": "usd",
      "quantity": "22.5",
      "cost_per_unit": "0.08",
      "cost": "1.80",
      "context": {
        "project": "alpha",
        "team": "support"
      },
      "metadata": {
        "input_tokens": 1024,
        "output_tokens": 256
      }
    }
  ]
}
```

### Example typed event usage

When using ``list_costs_typed`` or ``iter_costs``, each event is a
``CostEventItem`` instance. The attributes shown in the table above are
available as properties:

```python
page = manager.list_costs_typed({"limit": 5})

for event in page.results:
    print(f"{event.service_key}: {event.cost_unit_id} {event.cost}")
```

To access context or metadata fields, use the untyped ``list_costs`` method and
inspect the dictionaries:

```python
raw = manager.list_costs({"limit": 5})

for event in raw["results"]:
    project = event.get("context", {}).get("project")
    print(f"[{event['timestamp']}] {project} -> ${event['cost']}")
```

## Using curl

If you prefer to bypass the Python helper, you can query the REST endpoint
directly. The ``Authorization`` header must contain the API key.

```bash
curl https://api.aicostmanager.com/costs \
  -H "Authorization: Bearer $AICM_API_KEY" \
  -G \
  --data-urlencode "start_date=2025-03-01" \
  --data-urlencode "end_date=2025-03-31" \
  --data-urlencode "limit=50"
```

To query multiple team members, add additional ``api_key_id`` parameters. Bash
expands array-style flags, so repeat the flag for each value:

```bash
curl https://api.aicostmanager.com/costs \
  -H "Authorization: Bearer $AICM_API_KEY" \
  -G \
  --data-urlencode "api_key_id=11111111-2222-3333-4444-555555555555" \
  --data-urlencode "api_key_id=66666666-7777-8888-9999-000000000000" \
  --data-urlencode "context.project=alpha" \
  --data-urlencode "customer_key=acme-enterprise"
```

Use wildcard context filters the same way you would in Python:

```bash
curl https://api.aicostmanager.com/costs \
  -H "Authorization: Bearer $AICM_API_KEY" \
  -G \
  --data-urlencode "context.notes=*migration*" \
  --data-urlencode "limit=25"
```

## Best Practices

* **Paginate deliberately.** The API defaults to 25 results per page and caps
  at 200. Use ``iter_costs`` when you need the full dataset and ``limit`` when
  sampling.
* **Cache long-running aggregations.** If you routinely fetch the same date
  range, store the results locally to avoid re-downloading large responses.
* **Respect data access policies.** Sharing an API key across a team grants
  everyone the same access. Rotate keys if teammates leave and avoid embedding
  keys directly in source code.
* **Close the manager when done.** Although the client uses short-lived HTTP
  connections, explicitly calling ``close`` (or using a context manager) keeps
  resource usage tidy.

```python
with CostQueryManager() as manager:
    total = sum(event.cost for event in manager.iter_costs({"limit": 100}))
    print("Cost of first 100 events:", total)
```

Armed with these tools, you can answer cost questions for any project your
team is tracking in AICostManager—without touching the ingestion pipeline.
