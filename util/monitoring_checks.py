"""Compatibility facade for the contributed check-definition interface.

New code must use :mod:`util.monitoring.definitions`. ``CHECKS`` is generated
from that canonical registry, so this import path cannot diverge from the
checks that the production runner executes.
"""

from copy import deepcopy

from constants import MONITORING_SEVERITIES, MONITORING_TIERS
from util.monitoring.definitions import get_check_definitions
from util.monitoring_registry import CHECK_REGISTRY


class InvalidCheckDefinition(ValueError):
    """Raised when a legacy-shaped definition is invalid."""


def _legacy_definition(definition):
    params = deepcopy(definition["params"])
    if definition["kind"] == "http":
        function_name = "http_check"
        required_fields = params.get("required_fields", [])
        if len(required_fields) == 1:
            params.pop("required_fields")
            params["has_field"] = required_fields[0]
    elif params.get("handler") == "datastore":
        function_name = "check_datastore"
        params = {}
    else:
        function_name = "check_cron_heartbeat"
        params.pop("handler", None)
    return {
        "id": definition["id"],
        "name": definition["name"],
        "fn": function_name,
        "params": params,
        "tier": definition["tier"],
        "severity": definition["severity"],
        "timeout_ms": definition["timeout_ms"],
        "latency_threshold_ms": definition["latency_threshold_ms"],
        "enabled": definition["enabled"],
    }


CHECKS = [_legacy_definition(definition) for definition in get_check_definitions()]

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


def _is_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _definition_errors(definition, registry):
    if not isinstance(definition, dict):
        return ["definition is not a dict"]
    errors = []
    for field, field_type in _REQUIRED_FIELDS.items():
        if field not in definition:
            errors.append(f"missing '{field}'")
        elif field_type is not int and not isinstance(definition[field], field_type):
            errors.append(f"'{field}' must be {field_type.__name__}")
    unknown = set(definition) - set(_REQUIRED_FIELDS) - _OPTIONAL_FIELDS
    if unknown:
        errors.append(f"unknown fields {sorted(unknown)}")
    if isinstance(definition.get("id"), str) and not definition["id"].strip():
        errors.append("'id' must not be empty")
    if definition.get("tier") not in MONITORING_TIERS:
        errors.append(f"'tier' must be one of {MONITORING_TIERS}")
    if definition.get("severity") not in MONITORING_SEVERITIES:
        errors.append(f"'severity' must be one of {MONITORING_SEVERITIES}")
    if "timeout_ms" in definition and not _is_positive_int(definition["timeout_ms"]):
        errors.append("'timeout_ms' must be a positive int")
    threshold = definition.get("latency_threshold_ms")
    if threshold is not None and not _is_positive_int(threshold):
        errors.append("'latency_threshold_ms' must be a positive int or None")
    function_name = definition.get("fn")
    if isinstance(function_name, str) and function_name not in registry:
        errors.append(f"'fn' {function_name!r} is not in CHECK_REGISTRY")
    return errors


def validate_checks(checks, registry=None):
    """Validate callers still using the original definition shape."""
    registry = CHECK_REGISTRY if registry is None else registry
    errors = []
    seen_ids = set()
    for index, definition in enumerate(checks):
        label = (
            definition.get("id") if isinstance(definition, dict) else None
        ) or f"#{index}"
        errors.extend(
            f"check {label}: {error}"
            for error in _definition_errors(definition, registry)
        )
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
    """Return defensive copies of enabled legacy-shaped definitions."""
    if tier is not None and tier not in MONITORING_TIERS:
        raise ValueError(f"tier must be one of {MONITORING_TIERS} or None")
    return [
        deepcopy(definition)
        for definition in CHECKS
        if definition["enabled"] and (tier is None or definition["tier"] == tier)
    ]


validate_checks(CHECKS)

__all__ = [
    "CHECKS",
    "InvalidCheckDefinition",
    "load_checks",
    "validate_checks",
]
