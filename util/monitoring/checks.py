"""Executors for HTTP and in-process monitoring checks."""

from dataclasses import dataclass
from datetime import datetime
import time
from zoneinfo import ZoneInfo

import requests

from constants import (
    MONITORING_MAX_ATTEMPTS,
    MONITORING_RETRY_DELAY_SECONDS,
    MONITORING_VERIFY_LOCAL_TLS,
)
from db.monitoring import check_datastore_connection
from util.monitoring.cron_health import evaluate_cron_job
from util.monitoring.definitions import resolve_http_target


CHICAGO_TZ = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class CheckExecution:
    checked_at: datetime
    response_time_ms: int
    attempts: int
    status: str
    http_status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None


class CheckFailure(Exception):
    def __init__(self, error_type, message, http_status_code=None):
        super().__init__(message)
        self.error_type = error_type
        self.http_status_code = http_status_code


def _value_at_path(payload, path):
    value = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise CheckFailure("invalid_response", f"Missing JSON field: {path}")
        value = value[part]
    return value


def _validate_payload(payload, params):
    expected_type = params.get("expected_json_type")
    type_map = {"dict": dict, "list": list}
    if expected_type and not isinstance(payload, type_map[expected_type]):
        raise CheckFailure(
            "invalid_response", f"Expected a JSON {expected_type} response"
        )
    for path in params.get("required_fields", []):
        _value_at_path(payload, path)
    for path, expected in params.get("expected_values", {}).items():
        actual = _value_at_path(payload, path)
        if actual != expected:
            raise CheckFailure(
                "invalid_response",
                f"JSON field {path} was {actual!r}, expected {expected!r}",
            )
    minimum = params.get("min_items")
    if minimum is not None and len(payload) < minimum:
        raise CheckFailure(
            "invalid_response", f"Expected at least {minimum} response items"
        )


def _execute_http(definition, request_get):
    params = definition["params"]
    timeout_seconds = definition["timeout_ms"] / 1000
    response = request_get(
        resolve_http_target(params["target"]),
        timeout=timeout_seconds,
        allow_redirects=False,
        verify=(
            MONITORING_VERIFY_LOCAL_TLS if params["target"].startswith("/") else True
        ),
    )
    expected_status = params["expected_status"]
    if response.status_code != expected_status:
        error_type = (
            "auth_failed" if response.status_code in {401, 403} else "bad_status"
        )
        response_body = getattr(response, "text", "").strip()[:200]
        body_suffix = f"; response: {response_body}" if response_body else ""
        raise CheckFailure(
            error_type,
            f"Received HTTP {response.status_code}; expected {expected_status}{body_suffix}",
            response.status_code,
        )
    if any(
        key in params
        for key in (
            "expected_json_type",
            "required_fields",
            "expected_values",
            "min_items",
        )
    ):
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise CheckFailure(
                "invalid_response", "Response was not valid JSON"
            ) from exc
        _validate_payload(payload, params)
    return response.status_code


def _check_datastore(timeout_seconds):
    return check_datastore_connection(timeout_seconds=timeout_seconds)


def _check_cron_heartbeat(definition):
    params = definition["params"]
    return evaluate_cron_job(
        params["job_id"],
        params["job_name"],
        params["max_success_age_minutes"],
        params["max_runtime_minutes"],
    )


def _execute_function(definition):
    handler_name = definition["params"]["handler"]
    if handler_name == "datastore":
        result = _check_datastore(timeout_seconds=definition["timeout_ms"] / 1000)
    elif handler_name == "cron_heartbeat":
        result = _check_cron_heartbeat(definition)
    else:
        raise CheckFailure(
            "not_configured", f"Unknown monitoring function handler: {handler_name}"
        )
    if result is False:
        raise CheckFailure("invalid_response", f"Function check {handler_name} failed")
    if getattr(result, "status", None) == "failed":
        raise CheckFailure(result.error_type, result.error_message)
    return result


def execute_check(
    definition,
    request_get=requests.get,
    sleep=time.sleep,
    monotonic=time.monotonic,
):
    """Execute a definition with one retry and return a normalized final result."""
    checked_at = datetime.now(CHICAGO_TZ)
    started = monotonic()
    last_error = None
    http_status_code = None

    for attempt in range(1, MONITORING_MAX_ATTEMPTS + 1):
        try:
            function_health = None
            if definition["kind"] == "http":
                http_status_code = _execute_http(definition, request_get)
            else:
                function_health = _execute_function(definition)
                http_status_code = None
            duration_ms = max(0, round((monotonic() - started) * 1000))
            slow = duration_ms > definition["latency_threshold_ms"]
            reported_status = getattr(function_health, "status", None)
            return CheckExecution(
                checked_at=checked_at,
                response_time_ms=duration_ms,
                attempts=attempt,
                status=(
                    "degraded"
                    if slow or attempt > 1 or reported_status == "degraded"
                    else "healthy"
                ),
                http_status_code=http_status_code,
                error_type=getattr(function_health, "error_type", None),
                error_message=getattr(function_health, "error_message", None),
            )
        except requests.Timeout as exc:
            last_error = CheckFailure("timeout", str(exc) or "Request timed out")
        except requests.ConnectionError as exc:
            last_error = CheckFailure(
                "connection_error", str(exc) or "Connection failed"
            )
        except CheckFailure as exc:
            last_error = exc
            http_status_code = exc.http_status_code
        except (
            Exception
        ) as exc:  # A check must never prevent later checks from running.
            last_error = CheckFailure(
                "unexpected_error", str(exc) or type(exc).__name__
            )

        if attempt < MONITORING_MAX_ATTEMPTS:
            sleep(MONITORING_RETRY_DELAY_SECONDS)

    duration_ms = max(0, round((monotonic() - started) * 1000))
    return CheckExecution(
        checked_at=checked_at,
        response_time_ms=duration_ms,
        attempts=MONITORING_MAX_ATTEMPTS,
        status="failed",
        http_status_code=http_status_code,
        error_type=last_error.error_type,
        error_message=str(last_error),
    )


def _legacy_outcome(execution):
    """Adapt a canonical execution to the contributed registry contract."""
    return {
        "ok": execution.status != "failed",
        "status": execution.status,
        "checked_at": execution.checked_at,
        "response_time_ms": execution.response_time_ms,
        "attempts": execution.attempts,
        "http_status_code": execution.http_status_code,
        "error_type": execution.error_type,
        "error_message": execution.error_message,
    }


def check_datastore(timeout_ms=3000):
    """Compatibility executor backed by the production Datastore check."""
    definition = {
        "id": "datastore",
        "name": "Datastore",
        "kind": "function",
        "tier": "critical",
        "severity": "major",
        "timeout_ms": timeout_ms,
        "latency_threshold_ms": timeout_ms,
        "enabled": True,
        "params": {"handler": "datastore"},
    }
    return _legacy_outcome(execute_check(definition))


def http_check(
    target,
    expected_status=200,
    has_field=None,
    timeout_ms=5000,
    **params,
):
    """Compatibility HTTP executor backed by the canonical retry machinery."""
    required_fields = list(params.pop("required_fields", []))
    if has_field:
        required_fields.append(has_field)
    check_params = {
        "target": target,
        "expected_status": expected_status,
        **params,
    }
    if required_fields:
        check_params["expected_json_type"] = check_params.get(
            "expected_json_type", "dict"
        )
        check_params["required_fields"] = required_fields
    definition = {
        "id": "compatibility_http_check",
        "name": "Compatibility HTTP check",
        "kind": "http",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": timeout_ms,
        "latency_threshold_ms": timeout_ms,
        "enabled": True,
        "params": check_params,
    }
    return _legacy_outcome(execute_check(definition))


def check_cron_heartbeat(**params):
    """Compatibility executor backed by the canonical cron health evaluator."""
    timeout_ms = params.pop("timeout_ms", 3000)
    definition = {
        "id": params.get("job_id", "compatibility_cron_check"),
        "name": params.get("job_name", "Scheduled job"),
        "kind": "function",
        "tier": "full",
        "severity": "minor",
        "timeout_ms": timeout_ms,
        "latency_threshold_ms": timeout_ms,
        "enabled": True,
        "params": {"handler": "cron_heartbeat", **params},
    }
    return _legacy_outcome(execute_check(definition))


COMPATIBILITY_CHECK_REGISTRY = {
    "check_datastore": check_datastore,
    "http_check": http_check,
    "check_cron_heartbeat": check_cron_heartbeat,
}


def register_compatibility_check(name):
    """Preserve the former decorator API without creating a second registry."""

    def decorator(function):
        if (
            name in COMPATIBILITY_CHECK_REGISTRY
            and COMPATIBILITY_CHECK_REGISTRY[name] is not function
        ):
            raise ValueError(f"Check function '{name}' is already registered")
        COMPATIBILITY_CHECK_REGISTRY[name] = function
        return function

    return decorator
