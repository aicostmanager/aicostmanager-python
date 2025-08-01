# Tracking REST APIs

`RestCostManager` and `AsyncRestCostManager` make it easy to track any plain REST service accessed via `requests` or `httpx`.

```python
import requests
from aicostmanager import RestCostManager

session = requests.Session()
tracker = RestCostManager(session, base_url="https://api.heygen.com")
response = tracker.get("/v2/streaming.list", params={"page": 1})
```

The hostname of the API (``api.heygen.com`` in this example) becomes both the
``api_id`` and ``config_id``. The full URL without the scheme is used as the
``service_id``. Any payloads extracted from the call are queued for delivery to
AICostManager just like with ``CostManager``.

The response for ``/v2/streaming.list`` contains a list of streaming sessions.
A handling configuration can iterate over those sessions and produce a usage
record for each one. Each record's ``usage`` payload simply contains the session
``duration``.

Example delivery payload for two sessions:

```json
{
  "usage_records": [
    {
      "config_id": "api.heygen.com",
      "service_id": "api.heygen.com/v2/streaming.list",
      "timestamp": "2024-01-01T00:00:00Z",
      "response_id": "session-1",
      "usage": {"duration": 12}
    },
    {
      "config_id": "api.heygen.com",
      "service_id": "api.heygen.com/v2/streaming.list",
      "timestamp": "2024-01-01T00:00:00Z",
      "response_id": "session-2",
      "usage": {"duration": 20}
    }
  ]
}
```

Handling configuration for this endpoint:

```json
{
  "tracked_methods": ["GET /v2/streaming.list"],
  "list_path": "sessions",
  "response_fields": [
    {"key": "session_id", "path": "session_id"},
    {"key": "duration", "path": "duration"}
  ],
  "payload_mapping": {
    "config_id": "config_identifier",
    "service_id": "service_id",
    "timestamp": "timestamp",
    "response_id": "response_data.session_id",
    "usage": "response_data.duration"
  }
}
```
