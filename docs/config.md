# Configuration

The SDK reads its settings from an `AICM.INI` file. Only the API key is taken
from the environment by default. Provide the key directly when constructing a
`Tracker` or set it in the `AICM_API_KEY` environment variable.

The INI file location defaults to `~/.config/aicostmanager/AICM.INI` and can be
overridden by passing `ini_path` to `Tracker` or setting `AICM_INI_PATH` in the
environment.

## Settings

All configuration keys are fully capitalised and prefixed with `AICM_`.

| Setting | Default | Description |
| --- | --- | --- |
| `AICM_API_BASE` | `https://aicostmanager.com` | Base URL for the API |
| `AICM_API_URL` | `/api/v1` | API path prefix |
| `AICM_DELIVERY_TYPE` | `IMMEDIATE`* | Delivery strategy (`IMMEDIATE`, `MEM_QUEUE`, `PERSISTENT_QUEUE`) |
| `AICM_DB_PATH` | – | Path to SQLite database for persistent queue |
| `AICM_TIMEOUT` | `10.0` | HTTP timeout in seconds |
| `AICM_POLL_INTERVAL` | `0.1` | Poll interval for persistent queue workers |
| `AICM_BATCH_INTERVAL` | `0.5` | Flush interval for queued deliveries |
| `AICM_MAX_ATTEMPTS` | `3` | Retry attempts for HTTP failures |
| `AICM_MAX_RETRIES` | `5` | Reschedule attempts for queued items |
| `AICM_QUEUE_SIZE` | `10000` | Maximum queued payloads in memory |
| `AICM_MAX_BATCH_SIZE` | `1000` | Maximum payloads delivered per batch |
| `AICM_LOG_FILE` | – | Path to a log file |
| `AICM_LOG_LEVEL` | `INFO` | Logging level |
| `AICM_LOG_BODIES` | `false` | Include request bodies in logs |
| `AICM_LIMITS_ENABLED` | `false` | Enable triggered limit checks during delivery |

\* If `AICM_DB_PATH` is set and `AICM_DELIVERY_TYPE` is not specified, the
tracker defaults to `PERSISTENT_QUEUE`.

