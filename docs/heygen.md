# HeyGen

AICostManager can track usage for HeyGen streaming sessions by fetching session data via the HeyGen API and sending it to AICostManager for cost tracking.

## Overview

HeyGen streaming sessions are billed based on duration with a 30-second minimum. This guide shows how to:
1. Fetch streaming session data from HeyGen's API
2. Process and track costs using AICostManager
3. Use both immediate and persistent delivery methods

## Prerequisites

- HeyGen API key (`HEYGEN_API_KEY`)
- AICostManager API key (`AICM_API_KEY`)
- Python packages: `requests`, `aicostmanager`

## Step-by-Step Implementation

### Step 1: Fetch HeyGen Sessions

First, create a function to retrieve streaming sessions from HeyGen's API:

```python
import datetime
import requests
from typing import List, Dict

def fetch_heygen_sessions(api_key: str, limit: int = 100) -> List[Dict[str, object]]:
    """Fetch closed streaming sessions from HeyGen API."""
    base_url = "https://api.heygen.com/v2/streaming.list"
    
    # Define date range (adjust as needed)
    start = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    end = datetime.datetime.now(datetime.timezone.utc)
    
    headers = {"x-api-key": api_key, "accept": "application/json"}
    params = {
        "page": 1,
        "page_size": min(limit, 100),
        "date_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    
    events = []
    
    while len(events) < limit:
        resp = requests.get(base_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        # Check for API errors
        if data.get("code") and data.get("code") != 100:
            raise RuntimeError(
                f"HeyGen API returned error code {data.get('code')}: {data.get('message')}"
            )
        
        sessions = data.get("data") or []
        
        for sess in sessions:
            # Only process closed sessions
            if sess.get("status") != "closed":
                continue
                
            # Convert timestamp
            created = datetime.datetime.fromtimestamp(
                sess["created_at"], tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Format for AICostManager
            events.append({
                "response_id": sess["session_id"],
                "timestamp": created,
                "payload": {"duration": sess.get("duration", 0)},
            })
            
            if len(events) >= limit:
                break
        
        # Check for more pages
        if len(events) >= limit or not data.get("next_page_token"):
            break
        params["page"] += 1
    
    return events
```

### Step 2: Immediate Delivery Method

Process sessions one by one with immediate cost tracking:

```python
import os
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker

def track_heygen_immediate():
    """Track HeyGen sessions using immediate delivery."""
    
    # Get API keys
    heygen_api_key = os.environ.get("HEYGEN_API_KEY")
    aicm_api_key = os.environ.get("AICM_API_KEY")
    
    if not heygen_api_key or not aicm_api_key:
        raise ValueError("HEYGEN_API_KEY and AICM_API_KEY must be set")
    
    # Step 1: Fetch sessions from HeyGen
    print("Fetching HeyGen sessions...")
    sessions = fetch_heygen_sessions(heygen_api_key, limit=50)
    print(f"Found {len(sessions)} closed sessions")
    
    # Step 2: Configure immediate delivery
    ini = IniManager("heygen_immediate")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key=aicm_api_key)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    
    # Step 3: Track each session immediately
    with Tracker(aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery) as tracker:
        for session in sessions:
            result = tracker.track(
                "heygen",                                      # api_id
                "heygen::api.heygen.com/v2/streaming.list",  # service_key
                session["payload"],                           # {"duration": seconds}
                response_id=session["response_id"],           # session_id
                timestamp=session["timestamp"],               # ISO timestamp
            )
            
            # Verify cost tracking succeeded
            if result and result.get("result", {}).get("cost_events"):
                print(f"✓ Tracked session {session['response_id']}: {session['payload']['duration']}s")
            else:
                print(f"✗ Failed to track session {session['response_id']}")

# Run immediate tracking
track_heygen_immediate()
```

### Step 3: Persistent Queue Delivery Method

For production environments, use persistent queuing for reliability:

```python
import time

def track_heygen_persistent():
    """Track HeyGen sessions using persistent queue delivery."""
    
    # Get API keys
    heygen_api_key = os.environ.get("HEYGEN_API_KEY")
    aicm_api_key = os.environ.get("AICM_API_KEY")
    
    if not heygen_api_key or not aicm_api_key:
        raise ValueError("HEYGEN_API_KEY and AICM_API_KEY must be set")
    
    # Step 1: Fetch sessions from HeyGen
    print("Fetching HeyGen sessions...")
    sessions = fetch_heygen_sessions(heygen_api_key, limit=100)
    print(f"Found {len(sessions)} closed sessions")
    
    # Step 2: Configure persistent queue delivery
    ini = IniManager("heygen_persistent")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key=aicm_api_key)
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path="heygen_queue.db",      # SQLite database for queue
        poll_interval=0.5,              # Check queue every 500ms
        batch_interval=2.0,             # Send batches every 2 seconds
    )
    
    # Step 3: Queue all sessions for background delivery
    with Tracker(aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery) as tracker:
        print("Queueing sessions for delivery...")
        
        for session in sessions:
            tracker.track(
                "heygen",                                      # api_id
                "heygen::api.heygen.com/v2/streaming.list",  # service_key
                session["payload"],                           # {"duration": seconds}
                response_id=session["response_id"],           # session_id
                timestamp=session["timestamp"],               # ISO timestamp
            )
        
        print(f"Queued {len(sessions)} sessions for delivery")
    
    # Queue is automatically flushed when exiting the 'with' block
    # The context manager waits for the background worker to finish
    print("✓ All sessions delivered successfully")

# Run persistent tracking
track_heygen_persistent()
```

### Step 4: Production Integration

For production use, consider creating a scheduled task:

```python
import logging
from datetime import datetime, timedelta

def sync_heygen_costs_daily():
    """Daily sync of HeyGen costs - suitable for cron jobs."""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Get yesterday's sessions
        yesterday = datetime.now() - timedelta(days=1)
        logger.info(f"Syncing HeyGen costs for {yesterday.date()}")
        
        # Use persistent delivery for production reliability
        track_heygen_persistent()
        
        logger.info("HeyGen cost sync completed successfully")
        
    except Exception as e:
        logger.error(f"HeyGen cost sync failed: {e}")
        raise

# Example cron job: Run daily at 2 AM
# 0 2 * * * /usr/bin/python3 /path/to/heygen_sync.py
```

## Configuration Details

### Service Configuration

- **API ID**: `"heygen"`
- **Service Key**: `"heygen::api.heygen.com/v2/streaming.list"`
- **Required Payload**: `{"duration": <seconds>}`
- **Billing**: 30-second minimum per session

### Delivery Method Comparison

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| **Immediate** | Scripts, testing | Simple, instant feedback | No retry on failure |
| **Persistent** | Production, large volumes | Reliable, batched, retries | More complex setup |

### Error Handling

Both methods include built-in error handling:

- **HeyGen API errors**: Automatically detected and reported
- **Network issues**: Retries with exponential backoff (persistent mode)
- **AICostManager API issues**: Automatic retry logic
- **Duplicate tracking**: Prevented via unique `response_id`

## Best Practices

1. **Use persistent delivery** for production environments
2. **Filter for closed sessions** only to avoid tracking incomplete sessions
3. **Set reasonable date ranges** to avoid fetching too much historical data
4. **Monitor queue stats** in persistent mode to ensure delivery
5. **Log session IDs** for audit trails and troubleshooting
6. **Handle API rate limits** by implementing appropriate delays

## Troubleshooting

### Common Issues

- **No sessions found**: Check date range and API key permissions
- **API errors**: Verify HeyGen API key and rate limits
- **Delivery failures**: Check AICostManager API key and connectivity
- **Duplicate costs**: Ensure unique `response_id` for each session

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your tracking code here
```

This will show detailed information about API calls, queue operations, and delivery attempts.