# Multi-Tenant & Client Tracking Guide

AICostManager provides powerful tools for tracking and organizing LLM costs across multiple clients, projects, and departments. This guide covers everything you need to implement client-based cost tracking and billing.

## Overview

Multi-tenant cost tracking allows you to:

- **Track costs per client** for accurate billing and invoicing
- **Organize usage by project** or department for internal cost allocation
- **Set client-specific budgets** and alerts
- **Generate detailed reports** for customer billing
- **Query usage data** with flexible filtering options

## Basic Client Tracking

### Method 1: Constructor Parameters

The most straightforward way to track client usage is by setting client information when creating the `CostManager`:

```python
from aicostmanager import CostManager
import openai

client = openai.OpenAI(api_key="your-openai-key")

# Track all usage for a specific client
tracked_client = CostManager(
    client,
    client_customer_key="acme_corp",
    context={
        "project": "customer_support_bot",
        "user_id": "support_agent_123",
        "environment": "production",
        "department": "customer_success"
    }
)

# All API calls will be tagged with this client info
response = tracked_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Help with billing question"}]
)
```

### Method 2: Dashboard Organization

Currently, all usage is automatically tracked and can be organized via the [AICostManager dashboard](https://aicostmanager.com):

```python
from aicostmanager import CostManager
import openai

client = openai.OpenAI(api_key="your-openai-key")
tracked_client = CostManager(client)

# Usage is tracked automatically
response = tracked_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Customer inquiry"}]
)

# Later, organize and allocate costs via dashboard:
# 1. Visit aicostmanager.com dashboard
# 2. Filter usage by time period, model, or API calls
# 3. Assign costs to clients or projects
# 4. Generate billing reports
```

## Advanced Multi-Tenant Patterns

### Per-Client Instances

For applications serving multiple clients, create separate `CostManager` instances:

```python
from aicostmanager import CostManager
import openai

class AIServiceProvider:
    def __init__(self):
        self.base_client = openai.OpenAI(api_key="your-openai-key")
        self.client_trackers = {}
    
    def get_client_tracker(self, customer_id, project=None):
        """Get or create a tracker for a specific client."""
        key = f"{customer_id}_{project or 'default'}"
        
        if key not in self.client_trackers:
            self.client_trackers[key] = CostManager(
                self.base_client,
                client_customer_key=customer_id,
                context={
                    "project": project,
                    "service_type": "ai_assistant"
                }
            )
        
        return self.client_trackers[key]
    
    def process_request(self, customer_id, project, user_message):
        """Process a request with proper client tracking."""
        tracker = self.get_client_tracker(customer_id, project)
        
        response = tracker.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_message}]
        )
        
        return response.choices[0].message.content

# Usage
service = AIServiceProvider()

# Each client's usage is tracked separately
response1 = service.process_request("acme_corp", "chatbot", "Hello!")
response2 = service.process_request("tech_startup", "assistant", "Help me code")
```

### Context Switching

For applications that handle multiple clients in the same session:

```python
from aicostmanager import CostManager
import openai

class MultiTenantLLMService:
    def __init__(self):
        self.base_client = openai.OpenAI(api_key="your-openai-key")
    
    def create_completion(self, customer_id, model, messages, **kwargs):
        """Create completion with client tracking."""
        # Create tracker with client context
        tracker = CostManager(
            self.base_client,
            client_customer_key=customer_id,
            context={
                "session_type": "api_call",
                "model_requested": model,
                "message_count": len(messages)
            }
        )
        
        return tracker.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )

# Usage in API endpoint or service
service = MultiTenantLLMService()

# Each call automatically tagged with client info
response = service.create_completion(
    customer_id="client_123",
    model="gpt-4o-mini", 
    messages=[{"role": "user", "content": "Business question"}]
)
```

## Querying Usage Data

### Basic Usage Queries

Query usage data programmatically using the AICostManager API:

```python
import requests
from datetime import date, timedelta
from aicostmanager import CostManagerClient
from aicostmanager.models import UsageEventFilters

client = CostManagerClient(aicm_api_key="your-aicm-api-key")

# Get usage for a specific client
filters = UsageEventFilters(
    client_customer_key="acme_corp",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    limit=100
)

# Iterate through all usage events
for event in client.iter_usage_events(filters):
    print(f"Event: {event.event_id}")
    print(f"Model: {event.usage.get('model')}")
    print(f"Tokens: {event.usage.get('total_tokens')}")
    print(f"Cost: ${event.usage.get('cost', 0):.4f}")
    print("---")
```

### Advanced Filtering

```python
from aicostmanager.models import UsageEventFilters

# Filter by multiple criteria
filters = UsageEventFilters(
    client_customer_key="tech_startup",
    service_id="openai",
    start_date=date(2024, 1, 1),
    limit=50
)

# Get usage summary
events = list(client.iter_usage_events(filters))
total_cost = sum(event.usage.get('cost', 0) for event in events)
total_tokens = sum(event.usage.get('total_tokens', 0) for event in events)

print(f"Client: tech_startup")
print(f"Total Events: {len(events)}")
print(f"Total Cost: ${total_cost:.2f}")
print(f"Total Tokens: {total_tokens:,}")
```

### Generating Client Reports

```python
from collections import defaultdict
from datetime import date, timedelta

def generate_client_report(client_id, days=30):
    """Generate a usage report for a specific client."""
    client = CostManagerClient()
    
    filters = UsageEventFilters(
        client_customer_key=client_id,
        start_date=date.today() - timedelta(days=days),
        limit=1000
    )
    
    # Collect usage data
    usage_by_model = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0})
    
    for event in client.iter_usage_events(filters):
        model = event.usage.get('model', 'unknown')
        usage_by_model[model]["calls"] += 1
        usage_by_model[model]["tokens"] += event.usage.get('total_tokens', 0)
        usage_by_model[model]["cost"] += event.usage.get('cost', 0)
    
    # Generate report
    print(f"Usage Report for {client_id}")
    print(f"Period: Last {days} days")
    print("=" * 50)
    
    total_cost = 0
    for model, stats in usage_by_model.items():
        print(f"Model: {model}")
        print(f"  Calls: {stats['calls']:,}")
        print(f"  Tokens: {stats['tokens']:,}")
        print(f"  Cost: ${stats['cost']:.2f}")
        total_cost += stats['cost']
        print()
    
    print(f"Total Cost: ${total_cost:.2f}")
    return usage_by_model

# Generate reports for clients
acme_usage = generate_client_report("acme_corp")
startup_usage = generate_client_report("tech_startup")
```

## Customer Management

### Creating Customers

Use the AICostManager API to manage customer records:

```python
from aicostmanager import CostManagerClient
from aicostmanager.models import CustomerIn

client = CostManagerClient()

# Create a new customer
new_customer = CustomerIn(
    client_customer_key="enterprise_client_001",
    name="Enterprise Corp",
    description="Large enterprise customer with chatbot integration"
)

created_customer = client.create_customer(new_customer)
print(f"Created customer: {created_customer.uuid}")
```

### Listing and Filtering Customers

```python
from aicostmanager.models import CustomerFilters

# Get all customers
customers = list(client.iter_customers())

# Filter customers
filters = CustomerFilters(limit=50)
filtered_customers = list(client.iter_customers(filters))

for customer in customers:
    print(f"Customer: {customer.name}")
    print(f"Key: {customer.client_customer_key}")
    print(f"UUID: {customer.uuid}")
    print("---")
```

## Budget Management & Alerts

### Setting Client Budgets

Monitor and control spending per client:

```python
from aicostmanager.models import UsageLimitIn, ThresholdType, Period

# Set monthly budget for a client
budget_limit = UsageLimitIn(
    name="Acme Corp Monthly Budget",
    threshold_type=ThresholdType.COST,
    amount=500.00,  # $500 monthly limit
    period=Period.MONTHLY,
    client_customer_key="acme_corp"
)

created_limit = client.create_usage_limit(budget_limit)
print(f"Budget created: {created_limit.uuid}")
```

### Monitoring Budget Status

```python
# Check triggered limits for a client
triggered = client.config_manager.get_triggered_limits(
    client_customer_key="acme_corp"
)

for limit in triggered:
    print(f"Alert: Client {limit.client_customer_key}")
    print(f"Limit: ${limit.amount} {limit.period}")
    print(f"Type: {limit.threshold_type}")
```

## Best Practices

### 1. Consistent Client Identifiers

Use consistent, meaningful client identifiers:

```python
# Good: Clear, consistent naming
client_ids = [
    "acme_corp_prod",
    "acme_corp_staging", 
    "startup_xyz_main",
    "enterprise_001_chatbot"
]

# Avoid: Unclear or inconsistent naming
# "client1", "cust_a", "random_uuid_string"
```

### 2. Structured Context Data

Use structured context data for better organization:

```python
context = {
    "environment": "production",  # production, staging, development
    "service_type": "chatbot",    # chatbot, assistant, translation
    "user_tier": "premium",       # free, basic, premium, enterprise  
    "project": "customer_support",
    "version": "v2.1"
}
```

### 3. Regular Usage Monitoring

Implement regular usage monitoring:

```python
import schedule
import time

def daily_usage_check():
    """Check daily usage for all clients."""
    for client_id in get_active_clients():
        usage = get_daily_usage(client_id)
        if usage['cost'] > get_client_daily_limit(client_id):
            send_alert(client_id, usage)

# Schedule daily checks
schedule.every().day.at("09:00").do(daily_usage_check)

while True:
    schedule.run_pending()
    time.sleep(3600)  # Check every hour
```

### 4. Graceful Error Handling

Handle tracking errors gracefully:

```python
def safe_create_completion(client_id, **kwargs):
    """Create completion with error handling."""
    try:
        tracker = CostManager(
            openai_client,
            client_customer_key=client_id,
            context={"source": "api_v2"}
        )
        return tracker.chat.completions.create(**kwargs)
    except Exception as e:
        # Log error but don't fail the request
        logger.error(f"Tracking failed for {client_id}: {e}")
        # Fallback to untracked client
        return openai_client.chat.completions.create(**kwargs)
```

## Billing Integration

### Export for Accounting Systems

Generate billing data compatible with accounting systems:

```python
import csv
from datetime import date, timedelta

def export_billing_data(start_date, end_date, output_file):
    """Export billing data to CSV for accounting systems."""
    client = CostManagerClient()
    
    filters = UsageEventFilters(
        start_date=start_date,
        end_date=end_date,
        limit=10000
    )
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Date', 'Client_ID', 'Service', 'Model', 
            'Calls', 'Tokens', 'Cost', 'Project'
        ])
        
        for event in client.iter_usage_events(filters):
            context = event.context or {}
            writer.writerow([
                event.timestamp[:10],  # Date only
                event.client_customer_key or 'unassigned',
                event.service_id,
                event.usage.get('model', ''),
                1,  # Call count
                event.usage.get('total_tokens', 0),
                event.usage.get('cost', 0),
                context.get('project', '')
            ])

# Export last month's data
last_month_start = date.today().replace(day=1) - timedelta(days=1)
last_month_start = last_month_start.replace(day=1)
last_month_end = date.today().replace(day=1) - timedelta(days=1)

export_billing_data(last_month_start, last_month_end, 'billing_data.csv')
```

## Troubleshooting

### Common Issues

**Issue: Client tracking not working**
```python
# Check if client_customer_key is being set
payloads = tracker.get_tracked_payloads()
print(payloads[0].get('client_customer_key'))  # Should not be None
```

**Issue: Missing usage data**
```python
# Check API key and permissions
try:
    events = list(client.iter_usage_events(UsageEventFilters(limit=1)))
    print(f"API working: {len(events)} events found")
except Exception as e:
    print(f"API error: {e}")
```

**Issue: Context data not appearing**
```python
# Verify context is being passed correctly
tracker = CostManager(
    client,
    client_customer_key="test_client",
    context={"debug": True}
)
# Check tracked payloads for context data
```

For additional support, visit the [AICostManager documentation](https://aicostmanager.com/docs) or contact [support@aicostmanager.com](mailto:support@aicostmanager.com). 