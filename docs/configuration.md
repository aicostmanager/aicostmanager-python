# Configuration & Environment Variables

This guide summarizes the configuration options, environment variables, and INI behavior used by the SDK.

## Environment Variables

- `AICM_API_KEY` (required): Your AICostManager API key
- `AICM_API_BASE` (default `https://aicostmanager.com`): Base URL of the service
- `AICM_API_URL` (default `/api/v1`): API path prefix
- `AICM_INI_PATH` (default `~/.config/aicostmanager/AICM.INI`): Path to SDK INI file
- `AICM_DELIVERY_MODE` (`sync` | `async`, default `sync`): Delivery mode
- `AICM_DELIVERY_ON_FULL` (`block` | `raise` | `backpressure`, default `backpressure`): Queue overflow behavior

All env vars can be overridden via constructor arguments.

## INI File Behavior

The SDK persists lightweight state in an INI file:

- `[configs]` section: cached configuration payload and last `etag`
- `[triggered_limits]` section: cached triggered limits payload
- `[delivery]` section: persisted `timeout` value used as batch interval

The INI file is read with duplicate section handling and atomic writes to
avoid corruption. A simple file lock is used to prevent race conditions.

## Triggered Limits Refresh

- During client initialization, the SDK fetches `/configs` and (if unchanged) then `/triggered-limits`
- If the INI cache lacks triggered limit payloads, the SDK fetches limits from the API and stores them
- Delivery responses can also update triggered limits automatically

## Delivery Modes and Overflow

Set delivery mode globally via `AICM_DELIVERY_MODE` or per-wrapper using `delivery_mode`.

Overflow behavior when the queue is full:

- `block`: wait until space is available
- `raise`: raise `queue.Full`
- `backpressure` (default): drop the oldest payload; increments `total_discarded` and optionally invokes `on_discard`

Inspect metrics using `get_global_delivery_health()`.


