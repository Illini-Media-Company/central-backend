"""
This file defines the registry that maps check function names (the "fn" field
of a check definition in util/monitoring_checks.py) to the functions that run
them.

Check function contract:
    - Signature: fn(**params) -> dict
    - Return {"ok": True} on success, or
      {"ok": False, "error_type": str, "error_message": str,
       "http_status_code": int | None} on failure. error_type must be one of
      MONITORING_ERROR_TYPES in constants.py.
    - Raise on unexpected errors; the runner catches and records them.

Created by Gus Nophaket on Oct. 5, 2026
Last modified Oct. 5, 2026
"""

CHECK_REGISTRY = {}


def register(name):
    """Decorator that adds a check function to CHECK_REGISTRY under `name`."""

    def wrap(fn):
        if name in CHECK_REGISTRY and CHECK_REGISTRY[name] is not fn:
            raise ValueError(f"Check function '{name}' is already registered")
        CHECK_REGISTRY[name] = fn
        return fn

    return wrap
