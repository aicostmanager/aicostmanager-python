# Batch Tracking

The `track_batch()` method allows you to efficiently send multiple tracking records in a single operation, which is particularly useful for:

- High-throughput applications that need to track many events
- Batch processing scenarios where multiple operations occur together
- Reducing HTTP overhead by sending multiple records in one request
- Ensuring consistent API key usage across related tracking events

## Basic Usage

```python
from aicostmanager import Tracker

records = [
    {
        "service_key": "openai::gpt-4",
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "customer_key": "customer_1",
        "response_id": "request_1",
    },
    {
        "service_key": "anthropic::claude-3",
        "usage": {"input_tokens": 200, "output_tokens": 75},
        "customer_key": "customer_2",
        "context": {"session": "session_abc"},
        "timestamp": "2024-01-15T10:30:00Z",
    },
    {
        "service_key": "heygen::streaming-avatar",
        "usage": {"duration": 120.5},
        "customer_key": "customer_3",
        "context": {"video_id": "video_789"},
    },
]

with Tracker(aicm_api_key="your-api-key") as tracker:
    result = tracker.track_batch(records)
    print(f"Tracked {len(records)} records")
```

## Record Format

Each record in the batch is a dictionary with the following fields:

### Required Fields

- **`service_key`** (str): The service identifier (e.g., "openai::gpt-4", "anthropic::claude-3")
- **`usage`** (dict): Usage data specific to the service (e.g., tokens, duration, API calls)

### Optional Fields

- **`response_id`** (str): Unique identifier for this tracking record. If omitted, a UUID will be auto-generated.
- **`timestamp`** (str|datetime): When the usage occurred. Can be an ISO string or datetime object. Defaults to current time.
- **`customer_key`** (str): Customer identifier. If omitted, uses the tracker's default customer key.
- **`context`** (dict): Additional metadata. If omitted, uses the tracker's default context.

## Delivery Modes

### Immediate Delivery (Recommended for Batches)

With immediate delivery, all records are sent in a single HTTP request:

```python
with Tracker(aicm_api_key="your-key", delivery_type="immediate") as tracker:
    result = tracker.track_batch(records)
    # All records sent atomically in one request
    print(result["results"])  # List of results for each record
```

**Benefits:**
- Atomic operation (all succeed or all fail)
- Single HTTP request reduces latency
- Immediate feedback on success/failure
- Consistent API key usage

### Persistent Queue Delivery

With persistent queue delivery, records are queued individually but processed in batches by the background worker:

```python
with Tracker(aicm_api_key="your-key", delivery_type="persistent_queue") as tracker:
    result = tracker.track_batch(records)
    # Records queued individually, processed in background
    print(f"Queued {result['queued']} items")
    print(f"Response IDs: {result['response_ids']}")
```

**Benefits:**
- Durability (survives application restarts)
- Background processing doesn't block your application
- Automatic retries for failed requests

## Async Usage

Use `track_batch_async()` for async applications:

```python
import asyncio
from aicostmanager import Tracker

async def track_multiple_events():
    records = [
        {
            "service_key": "openai::gpt-4",
            "usage": {"input_tokens": 100},
        },
        {
            "service_key": "anthropic::claude-3",
            "usage": {"input_tokens": 200},
        },
    ]
    
    with Tracker(aicm_api_key="your-key") as tracker:
        result = await tracker.track_batch_async(records)
        return result

# Run the async function
result = asyncio.run(track_multiple_events())
```

## Advanced Features

### Anonymization

Apply anonymization to sensitive fields across all records:

```python
def anonymizer(value):
    if isinstance(value, str) and "@" in value:
        return "user@REDACTED.com"
    return "REDACTED"

records = [
    {
        "service_key": "openai::gpt-4",
        "usage": {"input_tokens": 100, "user_email": "john@acme.com"},
    },
    {
        "service_key": "anthropic::claude-3", 
        "usage": {"input_tokens": 200, "user_id": "user_12345"},
    },
]

with Tracker() as tracker:
    result = tracker.track_batch(
        records,
        anonymize_fields=["user_email", "user_id"],
        anonymizer=anonymizer,
    )
```

### Using Tracker Defaults

Set default customer_key and context at the tracker level, then override per record as needed:

```python
with Tracker() as tracker:
    # Set defaults
    tracker.set_customer_key("default_customer")
    tracker.set_context({"environment": "production"})
    
    records = [
        {
            "service_key": "openai::gpt-4",
            "usage": {"input_tokens": 100},
            # Uses default customer_key and context
        },
        {
            "service_key": "anthropic::claude-3",
            "usage": {"input_tokens": 200},
            "customer_key": "special_customer",  # Overrides default
            "context": {"environment": "staging"},  # Overrides default
        },
    ]
    
    tracker.track_batch(records)
```

### Timestamp Handling

The batch method handles various timestamp formats:

```python
from datetime import datetime, timezone

records = [
    {
        "service_key": "openai::gpt-4",
        "usage": {"tokens": 100},
        "timestamp": "2024-01-15T10:30:00Z",  # ISO string
    },
    {
        "service_key": "anthropic::claude-3",
        "usage": {"tokens": 200}, 
        "timestamp": datetime.now(timezone.utc),  # datetime object
    },
    {
        "service_key": "heygen::streaming-avatar",
        "usage": {"duration": 60},
        # No timestamp - uses current time
    },
]
```

## Error Handling

### Immediate Delivery Errors

With immediate delivery, errors affect the entire batch:

```python
try:
    with Tracker(delivery_type="immediate") as tracker:
        result = tracker.track_batch(records)
        print("All records processed successfully")
except Exception as e:
    print(f"Batch failed: {e}")
    # Handle the error (retry, log, etc.)
```

### Persistent Queue Errors

With persistent queue, individual records can fail and be retried:

```python
with Tracker(delivery_type="persistent_queue") as tracker:
    result = tracker.track_batch(records)
    print(f"Queued {len(result['response_ids'])} records")
    
    # Check queue status later
    stats = tracker.delivery.stats()
    if stats.get("total_failed", 0) > 0:
        print(f"Some records failed: {stats}")
```

## Performance Considerations

### Batch Size

While there's no hard limit, consider these guidelines:

- **Small batches (1-10 records)**: Optimal for real-time applications
- **Medium batches (10-100 records)**: Good for periodic processing
- **Large batches (100+ records)**: Use with caution, may hit API limits

### Memory Usage

Each record is kept in memory until sent. For very large batches, consider splitting into smaller chunks:

```python
def chunk_records(records, chunk_size=50):
    for i in range(0, len(records), chunk_size):
        yield records[i:i + chunk_size]

# Process large dataset in chunks
all_records = [...]  # Your large list of records

with Tracker() as tracker:
    for chunk in chunk_records(all_records, chunk_size=50):
        result = tracker.track_batch(chunk)
        print(f"Processed chunk of {len(chunk)} records")
```

## Migration from Individual Tracking

Converting from individual `track()` calls to `track_batch()`:

### Before (Individual Calls)

```python
with Tracker() as tracker:
    for session in sessions:
        tracker.track(
            "heygen::streaming-avatar",
            {"duration": session.duration},
            customer_key=session.customer_id,
            response_id=session.id,
        )
```

### After (Batch Call)

```python
# Build records list
records = [
    {
        "service_key": "heygen::streaming-avatar",
        "usage": {"duration": session.duration},
        "customer_key": session.customer_id,
        "response_id": session.id,
    }
    for session in sessions
]

# Send as batch
with Tracker() as tracker:
    result = tracker.track_batch(records)
```

**Benefits of migration:**
- Reduced HTTP overhead
- Better error handling options
- Consistent API key usage
- Improved performance for multiple records

## Real-World Example

Here's a complete example of tracking costs for a batch of HeyGen video sessions:

```python
import os
from datetime import datetime, timezone
from aicostmanager import Tracker

def track_heygen_sessions(sessions, is_development=False):
    """Track HeyGen session costs in batch."""
    
    # Choose API key based on environment
    api_key_name = "DEV_AICM_API_KEY" if is_development else "PROD_AICM_API_KEY"
    api_key = os.getenv(api_key_name)
    
    if not api_key:
        print(f"No {api_key_name} found, skipping tracking")
        return
    
    # Build batch records
    records = []
    for session in sessions:
        record = {
            "service_key": "heygen::streaming-avatar",
            "usage": {"duration": session.duration_seconds},
            "response_id": str(session.session_id),
            "timestamp": session.created_at,
        }
        
        # Add customer info if available
        if session.customer_id:
            record["customer_key"] = str(session.customer_id)
            
        # Add context metadata
        if session.video_id or session.user_id:
            record["context"] = {}
            if session.video_id:
                record["context"]["video_id"] = str(session.video_id)
            if session.user_id:
                record["context"]["user_id"] = str(session.user_id)
                
        records.append(record)
    
    # Track the batch
    env_type = "development" if is_development else "production"
    print(f"Tracking {len(records)} {env_type} HeyGen sessions")
    
    try:
        with Tracker(aicm_api_key=api_key, delivery_type="immediate") as tracker:
            result = tracker.track_batch(records)
            print(f"Successfully tracked {len(records)} sessions")
            return result
            
    except Exception as e:
        print(f"Failed to track {env_type} sessions: {e}")
        raise

# Usage
production_sessions = get_production_sessions()
development_sessions = get_development_sessions()

# Track each environment separately with correct API key
if production_sessions:
    track_heygen_sessions(production_sessions, is_development=False)

if development_sessions:
    track_heygen_sessions(development_sessions, is_development=True)
```

This approach ensures that production and development sessions are tracked with their respective API keys, avoiding the mixing issue you encountered with persistent queue delivery.
