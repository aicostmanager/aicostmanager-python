# Deepgram

AICostManager supports tracking usage for Deepgram's transcription and text to speech services.

## Websocket transcription

Use the `deepgram_websocket_transcription` service key to report websocket transcription usage. Payloads must include:

- `model` – e.g. `nova-3` or `nova-2`
- `language`
- `duration` in seconds
- optional `keywords` list for terms spotting

Quantity is calculated as minutes (`duration / 60`). Cost units are configured per model and language combination, for example `nova-3-eng-wo-terms`, `nova-3-eng-w-terms`, `nova-3-multilingual`, and `nova-2`.

Example:

```python
tracker.track(
    "deepgram",
    "deepgram::deepgram_websocket_transcription",
    {"model": "nova-3", "language": "en", "duration": 120, "keywords": []},
    response_id="dg-transcription-nova3-en-no-terms",
    timestamp="2025-01-01T00:00:00Z",
)
```

## Streaming text to speech

The `deepgram_streaming_tts` service tracks Deepgram's streaming text to speech. Required fields:

- `model`: `"aura-1"` or `"aura-2"`
- `char_count`: number of characters synthesized

Quantity is measured per thousand characters (`char_count / 1000`). Cost units are `text-to-speech-aura-1` and `text-to-speech-aura-2`.

Example:

```python
tracker.track(
    "deepgram",
    "deepgram::deepgram_streaming_tts",
    {"model": "aura-2", "char_count": 1500},
    response_id="dg-tts-aura2-1500",
    timestamp="2025-01-01T00:00:00Z",
)
```

Both services work with immediate delivery or persistent queue delivery. When using a persistent queue, create the tracker inside a `with Tracker(...):` block to ensure any queued usage is flushed on exit.
