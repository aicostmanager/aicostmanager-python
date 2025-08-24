# HeyGen

AICostManager can track usage for HeyGen streaming sessions via the
`streaming.list` endpoint.

## Tracking streaming sessions

Use `api_id` **"heygen"** and service key
`heygen::api.heygen.com/v2/streaming.list`. Payloads require a
`duration` field representing the session length in seconds. Billing is
subject to a 30‑second minimum.

```python
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker

ini = IniManager("ini")
dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="YOUR_AICM_KEY")
delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)

with Tracker(aicm_api_key="YOUR_AICM_KEY", ini_path=ini.ini_path, delivery=delivery) as tracker:
    tracker.track(
        "heygen",
        "heygen::api.heygen.com/v2/streaming.list",
        {"duration": 45},
        response_id="heygen-session-uuid",
        timestamp="2025-01-01T00:00:00Z",
    )
```

## Persistent queue delivery

To batch and retry delivery, use the persistent queue option:

```python
ini = IniManager("ini")
dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="YOUR_AICM_KEY")
queue_delivery = create_delivery(
    DeliveryType.PERSISTENT_QUEUE,
    dconfig,
    db_path="queue.db",
)

with Tracker(aicm_api_key="YOUR_AICM_KEY", ini_path=ini.ini_path, delivery=queue_delivery) as tracker:
    tracker.track(
        "heygen",
        "heygen::api.heygen.com/v2/streaming.list",
        {"duration": 10},
        response_id="heygen-batch-10s",
        timestamp="2025-01-01T00:00:00Z",
    )
```

The same service key and payload format can be used for batches of
sessions. Durations shorter than 30 seconds will be billed as 30 seconds.
