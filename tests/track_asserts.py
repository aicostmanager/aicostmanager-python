"""Shared assertions for validating /track responses in tests."""

from __future__ import annotations

from typing import Mapping, Sequence


_ALLOWED_STATUS_NO_EVENTS = {"queued", "completed"}
_ERROR_STATUSES = {"error", "service_key_unknown"}


def _as_list(errors: object) -> Sequence[str]:
    if isinstance(errors, (list, tuple)):
        return [str(e) for e in errors]
    if errors is None:
        return []
    return [str(errors)]


def assert_track_result_payload(result: Mapping[str, object]) -> None:
    """Validate the structure of a single result item from /track."""

    assert isinstance(result, Mapping), "result payload must be a mapping"
    response_id = result.get("response_id")
    assert isinstance(response_id, str) and response_id, "response_id must be present"

    status = result.get("status")
    if status is not None:
        assert isinstance(status, str), "status must be a string when provided"

    cost_events = result.get("cost_events")
    errors = _as_list(result.get("errors"))

    if cost_events:
        assert isinstance(cost_events, list), "cost_events must be a list when present"
        return

    if status in _ALLOWED_STATUS_NO_EVENTS:
        # Successful ingestion where processing happens asynchronously.
        assert not errors or isinstance(errors, list)
        return

    if status in _ERROR_STATUSES:
        assert errors, "error statuses must include descriptive messages"
        if status == "service_key_unknown":
            combined = " ".join(errors).lower()
            assert "not recognized" in combined or "queued for review" in combined
        return

    # Legacy servers may omit status but still provide errors
    assert errors, "results without cost_events must include errors or a known status"
