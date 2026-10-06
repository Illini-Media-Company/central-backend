"""Declarative definitions for the backend monitoring checks."""

from copy import deepcopy
from urllib.parse import urlparse

from constants import (
    GOOGLE_OAUTH_DISCOVERY_URL,
    MONITORING_BASE_URL,
    MONITORING_SEVERITIES,
    MONITORING_TIERS,
)


CHECK_DEFINITIONS = (
    {
        "id": "datastore",
        "name": "Datastore",
        "kind": "function",
        "tier": "critical",
        "severity": "major",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {"handler": "datastore"},
    },
    {
        "id": "google_oauth_discovery",
        "name": "Google OAuth discovery",
        "kind": "http",
        "tier": "critical",
        "severity": "major",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1500,
        "enabled": True,
        "params": {
            "target": GOOGLE_OAUTH_DISCOVERY_URL,
            "expected_status": 200,
            "expected_json_type": "dict",
            "required_fields": ["authorization_endpoint", "token_endpoint"],
        },
    },
    {
        "id": "cron_socials_rss_listener",
        "name": "Socials RSS listener schedule",
        "kind": "function",
        "tier": "critical",
        "severity": "major",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {
            "handler": "cron_heartbeat",
            "job_id": "socials_rss_listener",
            "job_name": "Socials RSS listener",
            "max_success_age_minutes": 90,
            "max_runtime_minutes": 15,
        },
    },
    {
        "id": "events_categories_api",
        "name": "Events categories API",
        "kind": "http",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 5000,
        "latency_threshold_ms": 2000,
        "enabled": True,
        "params": {
            "target": "/api/events/categories",
            "expected_status": 200,
            "expected_json_type": "list",
            "min_items": 1,
        },
    },
    {
        "id": "advertiser_metrics_sites_api",
        "name": "Advertiser metrics sites API",
        "kind": "http",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 5000,
        "latency_threshold_ms": 2000,
        "enabled": True,
        "params": {
            "target": "/api/advertiser-metrics/sites",
            "expected_status": 200,
            "expected_json_type": "dict",
            "required_fields": ["sites"],
        },
    },
    {
        "id": "cron_delete_expired_events",
        "name": "Expired-event cleanup schedule",
        "kind": "function",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {
            "handler": "cron_heartbeat",
            "job_id": "delete_expired_events",
            "job_name": "Expired-event cleanup",
            "max_success_age_minutes": 1800,
            "max_runtime_minutes": 30,
        },
    },
    {
        "id": "cron_cu_calendar_sync_30d",
        "name": "30-day calendar sync schedule",
        "kind": "function",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {
            "handler": "cron_heartbeat",
            "job_id": "cu_calendar_sync_30d",
            "job_name": "30-day calendar sync",
            "max_success_age_minutes": 11520,
            "max_runtime_minutes": 60,
        },
    },
    {
        "id": "cron_cu_calendar_sync_year",
        "name": "Annual calendar sync schedule",
        "kind": "function",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {
            "handler": "cron_heartbeat",
            "job_id": "cu_calendar_sync_year",
            "job_name": "Annual calendar sync",
            "max_success_age_minutes": 532800,
            "max_runtime_minutes": 120,
        },
    },
    {
        "id": "cron_wpgu_song_requests_cleanup",
        "name": "WPGU song-request cleanup schedule",
        "kind": "function",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": 3000,
        "latency_threshold_ms": 1000,
        "enabled": True,
        "params": {
            "handler": "cron_heartbeat",
            "job_id": "wpgu_song_requests_cleanup",
            "job_name": "WPGU song-request cleanup",
            "max_success_age_minutes": 11520,
            "max_runtime_minutes": 30,
        },
    },
)


def _is_http_target(value):
    if value.startswith("/"):
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_check_definitions(definitions):
    """Validate the registry at import time and return it unchanged."""
    seen_ids = set()
    required = {
        "id",
        "name",
        "kind",
        "tier",
        "severity",
        "timeout_ms",
        "latency_threshold_ms",
        "enabled",
        "params",
    }
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("Monitoring check definitions must be dictionaries")
        missing = required - definition.keys()
        if missing:
            raise ValueError(
                f"Check definition is missing fields: {', '.join(sorted(missing))}"
            )
        unknown = definition.keys() - required
        if unknown:
            raise ValueError(
                f"Check definition has unknown fields: {', '.join(sorted(unknown))}"
            )
        check_id = definition["id"]
        if not isinstance(check_id, str) or not check_id.strip():
            raise ValueError("Check ids must be non-empty strings")
        if check_id in seen_ids:
            raise ValueError(f"Duplicate monitoring check id: {check_id}")
        seen_ids.add(check_id)
        if not isinstance(definition["name"], str) or not definition["name"].strip():
            raise ValueError(f"Check name must be a non-empty string: {check_id}")
        if definition["kind"] not in {"http", "function"}:
            raise ValueError(f"Invalid kind for monitoring check {check_id}")
        if definition["tier"] not in MONITORING_TIERS:
            raise ValueError(f"Invalid tier for monitoring check {check_id}")
        if definition["severity"] not in MONITORING_SEVERITIES:
            raise ValueError(f"Invalid severity for monitoring check {check_id}")
        if not isinstance(definition["enabled"], bool):
            raise ValueError(
                f"enabled must be a boolean for monitoring check {check_id}"
            )
        timeout_ms = definition["timeout_ms"]
        if (
            isinstance(timeout_ms, bool)
            or not isinstance(timeout_ms, int)
            or timeout_ms < 1
        ):
            raise ValueError(f"timeout_ms must be a positive integer for {check_id}")
        latency_threshold_ms = definition["latency_threshold_ms"]
        if (
            isinstance(latency_threshold_ms, bool)
            or not isinstance(latency_threshold_ms, int)
            or latency_threshold_ms < 0
        ):
            raise ValueError(
                f"latency_threshold_ms must be a nonnegative integer for {check_id}"
            )

        params = definition["params"]
        if not isinstance(params, dict):
            raise ValueError(f"params must be a dictionary for {check_id}")
        if definition["kind"] == "http":
            target = params.get("target")
            if not isinstance(target, str) or not _is_http_target(target):
                raise ValueError(f"Invalid HTTP target for monitoring check {check_id}")
            method = params.get("method", "GET")
            if not isinstance(method, str) or method.upper() != "GET":
                raise ValueError(f"Only GET monitoring checks are allowed: {check_id}")
            expected_status = params.get("expected_status")
            if (
                isinstance(expected_status, bool)
                or not isinstance(expected_status, int)
                or not 100 <= expected_status <= 599
            ):
                raise ValueError(
                    f"Invalid expected_status for monitoring check {check_id}"
                )
            if params.get("expected_json_type") not in {None, "dict", "list"}:
                raise ValueError(
                    f"Invalid expected_json_type for monitoring check {check_id}"
                )
            required_fields = params.get("required_fields", [])
            if not isinstance(required_fields, list) or not all(
                isinstance(field, str) and field for field in required_fields
            ):
                raise ValueError(
                    f"required_fields must be a list of strings for {check_id}"
                )
            if not isinstance(params.get("expected_values", {}), dict):
                raise ValueError(f"expected_values must be a dictionary for {check_id}")
            minimum = params.get("min_items")
            if minimum is not None and (
                isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0
            ):
                raise ValueError(f"min_items must be nonnegative for {check_id}")
        elif params.get("handler") not in {"datastore", "cron_heartbeat"}:
            raise ValueError(
                f"Unknown function handler for monitoring check {check_id}"
            )
        elif params.get("handler") == "cron_heartbeat":
            required_cron_params = {
                "job_id",
                "job_name",
                "max_success_age_minutes",
                "max_runtime_minutes",
            }
            missing_cron_params = required_cron_params - params.keys()
            if missing_cron_params:
                raise ValueError(
                    f"Cron heartbeat check {check_id} is missing: "
                    f"{', '.join(sorted(missing_cron_params))}"
                )
            for field in ("job_id", "job_name"):
                value = params[field]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"{field} must be a non-empty string for {check_id}"
                    )
            for field in ("max_success_age_minutes", "max_runtime_minutes"):
                value = params[field]
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise ValueError(
                        f"{field} must be a positive integer for {check_id}"
                    )
    return definitions


validate_check_definitions(CHECK_DEFINITIONS)


def get_check_definitions():
    """Return defensive copies so callers cannot mutate the global registry."""
    return [deepcopy(definition) for definition in CHECK_DEFINITIONS]


def get_check_definition(check_id):
    """Return one check definition, or None when the id is not registered."""
    for definition in CHECK_DEFINITIONS:
        if definition["id"] == check_id:
            return deepcopy(definition)
    return None


def get_checks_for_tier(tier):
    """Return enabled checks selected by a critical or full run."""
    if tier not in MONITORING_TIERS:
        raise ValueError(f"Invalid monitoring tier: {tier}")
    return [
        deepcopy(definition)
        for definition in CHECK_DEFINITIONS
        if definition["enabled"]
        and (tier == "full" or definition["tier"] == "critical")
    ]


def resolve_http_target(target):
    """Resolve application-relative check targets against the configured backend."""
    if target.startswith("/"):
        return f"{MONITORING_BASE_URL.rstrip('/')}{target}"
    return target


def get_check_target(definition):
    """Return the concrete route, dependency, or scheduled-job identifier."""
    params = definition["params"]
    return params.get("target", params.get("job_id", params.get("handler")))
