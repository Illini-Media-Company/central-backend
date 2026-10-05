"""
This file defines every monitoring check (CHECKS) and the loader that validates
them. Every check has the same shape; anything check-specific goes in `params`.

The definitions are validated when this module is imported, so a bad
definition fails the app at startup instead of during a run.

Created by Gus Nophaket on Oct. 5, 2026
Last modified Oct. 5, 2026
"""

from constants import MONITORING_TIERS, MONITORING_SEVERITIES

# Imported so its @register decorators run before validation
import util.monitoring_check_functions  # noqa: F401
from util.monitoring_registry import CHECK_REGISTRY

CHECKS = [
    {
        "id": "datastore",  # Stable key, never rename
        "name": "Datastore",  # Display name for dashboard/Slack
        "fn": "check_datastore",  # Name in CHECK_REGISTRY
        "params": {},
        "tier": "critical",  # critical (every 10 min) | full (3-4x/day)
        "severity": "major",  # major = Slack alert | minor = dashboard only
        "timeout_ms": 3000,
        "latency_threshold_ms": 500,  # Optional; None = don't mark degraded on speed
        "enabled": True,
    },
    {
        "id": "song_requests_api",
        "name": "Song Requests API",
        "fn": "http_check",
        "params": {
            "target": "/api/song-requests",
            "expected_status": 200,
            "has_field": "requests",
        },
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 5000,
        "latency_threshold_ms": 1000,
        "enabled": False,  # TODO: route checks deferred pending decision
    },
]

# Required fields and their types
_REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "fn": str,
    "params": dict,
    "tier": str,
    "severity": str,
    "timeout_ms": int,
    "enabled": bool,
}
_OPTIONAL_FIELDS = {"latency_threshold_ms"}


class InvalidCheckDefinition(ValueError):
    """Raised when one or more check definitions are invalid."""


def _is_positive_int(value):
    # bool is a subclass of int, so rule it out explicitly
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _definition_errors(definition, registry):
    """Returns a list of problems with one check definition."""
    if not isinstance(definition, dict):
        return ["definition is not a dict"]

    errors = []
    for field, field_type in _REQUIRED_FIELDS.items():
        if field not in definition:
            errors.append(f"missing '{field}'")
        elif field_type is int:
            continue  # Checked below with a stricter rule
        elif not isinstance(definition[field], field_type):
            errors.append(f"'{field}' must be {field_type.__name__}")

    unknown = set(definition) - set(_REQUIRED_FIELDS) - _OPTIONAL_FIELDS
    if unknown:
        errors.append(f"unknown fields {sorted(unknown)}")

    if isinstance(definition.get("id"), str) and not definition["id"].strip():
        errors.append("'id' must not be empty")
    if "tier" in definition and definition["tier"] not in MONITORING_TIERS:
        errors.append(f"'tier' must be one of {MONITORING_TIERS}")
    if "severity" in definition and definition["severity"] not in MONITORING_SEVERITIES:
        errors.append(f"'severity' must be one of {MONITORING_SEVERITIES}")
    if "timeout_ms" in definition and not _is_positive_int(definition["timeout_ms"]):
        errors.append("'timeout_ms' must be a positive int")

    threshold = definition.get("latency_threshold_ms")
    if threshold is not None and not _is_positive_int(threshold):
        errors.append("'latency_threshold_ms' must be a positive int or None")

    fn = definition.get("fn")
    if isinstance(fn, str) and fn not in registry:
        errors.append(f"'fn' {fn!r} is not in CHECK_REGISTRY")

    return errors


def validate_checks(checks, registry=None):
    """
    Validates every check definition. Raises InvalidCheckDefinition listing
    every problem found, so one deploy shows all of them at once.
    """
    registry = CHECK_REGISTRY if registry is None else registry
    errors = []
    seen_ids = set()

    for index, definition in enumerate(checks):
        label = (
            definition.get("id") if isinstance(definition, dict) else None
        ) or f"#{index}"
        errors += [
            f"check {label}: {e}" for e in _definition_errors(definition, registry)
        ]

        check_id = definition.get("id") if isinstance(definition, dict) else None
        if isinstance(check_id, str):
            if check_id in seen_ids:
                errors.append(f"check {check_id}: duplicate 'id'")
            seen_ids.add(check_id)

    if errors:
        raise InvalidCheckDefinition(
            "Invalid monitoring check definitions:\n  " + "\n  ".join(errors)
        )


def load_checks(tier=None):
    """
    Returns the enabled check definitions, optionally only those in `tier`.
    Returns copies, so callers can't change CHECKS by accident.
    """
    if tier is not None and tier not in MONITORING_TIERS:
        raise ValueError(f"tier must be one of {MONITORING_TIERS} or None")
    return [
        dict(definition)
        for definition in CHECKS
        if definition["enabled"] and (tier is None or definition["tier"] == tier)
    ]


# Fail loudly at import (app startup) if any definition is invalid
validate_checks(CHECKS)
