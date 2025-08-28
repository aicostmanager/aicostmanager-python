# PersistentDelivery Logging

`PersistentDelivery` emits extensive log messages to help monitor and troubleshoot the durable queue that sends usage data to AICostManager.  It uses Python's standard [`logging`](https://docs.python.org/3/library/logging.html) system and can be customized through constructor arguments or environment variables.

## Configuring Log Output

### Log Level

Set the verbosity with the ``log_level`` parameter or ``AICM_LOG_LEVEL`` environment variable.  The default is ``INFO``.  Use ``DEBUG`` to see detailed queue operations and worker activity.

```python
from aicostmanager import PersistentDelivery

delivery = PersistentDelivery(log_level="DEBUG")
```

```bash
export AICM_LOG_LEVEL=DEBUG
```

### Log Destination

By default logs are written to ``~/.config/aicostmanager/aicm.log``.  Provide ``log_file`` (or ``AICM_LOG_FILE``) to change the destination.  The parent directory is created automatically.

```python
delivery = PersistentDelivery(log_file="/var/log/aicm/delivery.log")
```

### Custom Logger

Pass an existing ``logging.Logger`` instance to integrate with application-wide logging.  If the supplied logger already has handlers configured, ``PersistentDelivery`` will not add another handler.

```python
import logging

logger = logging.getLogger("aicm.delivery")
logger.setLevel(logging.INFO)
# configure handlers / formatters as needed

delivery = PersistentDelivery(logger=logger)
```

## Logging Request and Response Bodies

For deep troubleshooting you can log full request and response bodies.  Redaction removes common sensitive fields such as ``authorization`` and ``api_key``.

Enable body logging with the ``log_bodies`` parameter or ``AICM_LOG_BODIES`` setting.

```python
delivery = PersistentDelivery(log_bodies=True)
```

```bash
export AICM_LOG_BODIES=true
```

## Example Output

With ``log_level="DEBUG"`` the component records queue activity:

```
2024-03-28 12:00:00 DEBUG Worker thread started
2024-03-28 12:00:00 DEBUG Enqueued message id=1
2024-03-28 12:00:01 DEBUG Sending 1 payload(s) (80 bytes) to https://aicostmanager.com/api/v1/track
2024-03-28 12:00:01 INFO Batch delivered to https://aicostmanager.com/api/v1/track with status 200
```

## Summary

* ``log_level`` / ``AICM_LOG_LEVEL`` – control verbosity
* ``log_file`` / ``AICM_LOG_FILE`` – write logs to a file
* ``logger`` – plug in a preconfigured ``Logger``
* ``log_bodies`` / ``AICM_LOG_BODIES`` – log request/response bodies with redaction

These options provide full visibility into the background worker and HTTP delivery process.

