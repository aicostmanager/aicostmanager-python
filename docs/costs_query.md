# Querying Costs

The :class:`~aicostmanager.costs.CostQueryManager` provides a lightweight way
to retrieve cost events recorded by AICostManager. It wraps
:class:`~aicostmanager.client.CostManagerClient` and exposes convenience
methods for the ``/costs`` API.

## Basic usage

1. **Create a manager**

   ```python
   from aicostmanager import CostQueryManager

   manager = CostQueryManager()  # reads AICM_API_KEY from the environment
   ```

2. **Construct query filters**

   Filters can be provided as a dictionary or a
   :class:`~aicostmanager.models.CostEventFilters` instance. All fields are
   optional and correspond to the query parameters supported by the API.

   ```python
   from datetime import date
   from aicostmanager.models import CostEventFilters

   filters = CostEventFilters(
       api_key_id=["11111111-2222-3333-4444-555555555555"],
       service_key=["openai::gpt-4o"],
       start_date=date(2025, 1, 1),
       end_date=date(2025, 1, 31),
       limit=50,
   )
   ```

3. **Fetch results**

   Use :meth:`list_costs_typed` for a typed paginated response or
   :meth:`iter_costs` to stream individual events across all pages.

   ```python
   page = manager.list_costs_typed(filters)
   print("total events:", page.count)
   for event in page.results:
       print(event.vendor_id, event.cost)

   # or iterate through all pages
   for event in manager.iter_costs(filters):
       print(event.service_id, event.quantity)
   ```

4. **Context filters and pagination**

   Additional context-based filters can be supplied using dictionary keys that
   start with ``"context."``:

   ```python
   filters = {"context.project": "alpha", "limit": 25}
   data = manager.list_costs(filters)
   ```

## Response data

The API returns a paginated object with the following structure:

- ``count`` – total number of matching events
- ``next``/``previous`` – URLs for adjacent pages
- ``results`` – list of cost events

Each cost event includes:

- ``vendor_id`` and ``service_id``
- ``cost_unit_id``
- ``quantity`` – number of units consumed
- ``cost_per_unit`` – price for a single unit
- ``cost`` – total cost for the event

Close the manager when finished to release network resources:

```python
manager.close()
```
