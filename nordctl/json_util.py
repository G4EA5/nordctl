"""JSON-safe serialization helpers for API responses."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any


def sanitize_for_json(value: Any, _seen: set[int] | None = None) -> Any:
    """Return a tree with no circular references — safe for json.dumps."""
    if _seen is None:
        _seen = set()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    oid = id(value)
    if oid in _seen:
        return None
    if isinstance(value, dict):
        _seen.add(oid)
        return {str(k): sanitize_for_json(v, _seen) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        _seen.add(oid)
        return [sanitize_for_json(v, _seen) for v in value]
    return str(value)
