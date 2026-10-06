"""Transactional dashboard snapshot helpers for backend monitoring."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from constants import (
    MONITORING_CRITICAL_STALE_HOURS,
    MONITORING_FULL_STALE_HOURS,
)
from db.monitoring import (
    create_check_result,
    get_dashboard_snapshot,
    get_results_for_run,
    get_run,
    modify_dashboard_snapshot,
    update_run,
)
from util.monitoring.definitions import get_check_definitions, get_check_target


CHICAGO_TZ = ZoneInfo("America/Chicago")


def compute_status(outcome_ok, response_time_ms, latency_threshold_ms):
    """Return the persisted health state for a raw check outcome."""
    if not outcome_ok:
        return "failed"
    if (
        latency_threshold_ms is not None
        and response_time_ms is not None
        and response_time_ms > latency_threshold_ms
    ):
        return "degraded"
    return "healthy"


def save_result(run_id, definition, outcome):
    """Persist one normalized outcome while snapshotting its definition fields."""
    params = definition.get("params") or {}
    return create_check_result(
        run_id=run_id,
        check_id=definition["id"],
        status=outcome["status"],
        check_name=definition.get("name"),
        target=params.get("target", params.get("job_id", params.get("handler"))),
        tier=definition.get("tier"),
        severity=definition.get("severity"),
        latency_threshold_ms=definition.get("latency_threshold_ms"),
        checked_at=outcome.get("checked_at"),
        response_time_ms=outcome.get("response_time_ms"),
        attempts=outcome.get("attempts", 1),
        http_status_code=outcome.get("http_status_code"),
        error_type=outcome.get("error_type"),
        error_message=outcome.get("error_message"),
    )


def count_statuses(results):
    """Count final results by status."""
    counts = {"total": len(results), "healthy": 0, "degraded": 0, "failed": 0}
    for result in results:
        counts[result.status] += 1
    return counts


def finish_run(run_id):
    """Mark a run complete using the results that were successfully persisted."""
    counts = count_statuses(get_results_for_run(run_id))
    return update_run(
        run_id,
        run_status="completed",
        end_time=datetime.now(CHICAGO_TZ),
        **counts,
    )


def is_alert_active(check_id):
    """Return the alert state recorded in the current dashboard snapshot."""
    snapshot = get_dashboard_snapshot()
    for entry in (snapshot.checks or []) if snapshot else []:
        if entry["check_id"] == check_id:
            return entry.get("alert_active", False)
    return False


def next_alert_active(latest, previously_active):
    """Carry alert state through a failure streak and clear it on recovery."""
    return latest.status == "failed" and (latest.alert_sent or previously_active)


def _hour_key(value):
    return value.replace(minute=0, second=0, microsecond=0).isoformat()


def _prune_hourly_counts(hourly_counts, now):
    cutoff = now - timedelta(days=7)
    return {
        hour: dict(values)
        for hour, values in (hourly_counts or {}).items()
        if datetime.fromisoformat(hour) >= cutoff
    }


def add_to_hourly_counts(hourly_counts, latest, now):
    """Add a result to seven days of immutable hourly uptime counters."""
    counts = _prune_hourly_counts(hourly_counts, now)
    if latest.checked_at:
        hour = _hour_key(latest.checked_at)
        bucket = counts.setdefault(hour, {"up": 0, "failed": 0, "total": 0})
        bucket["total"] += 1
        if latest.status == "failed":
            bucket["failed"] += 1
        else:
            bucket["up"] += 1
    return counts


def window_rates(hourly_counts, now, hours):
    """Return percentage uptime and error rate for the requested window."""
    cutoff = now - timedelta(hours=hours)
    buckets = [
        values
        for hour, values in (hourly_counts or {}).items()
        if datetime.fromisoformat(hour) >= cutoff
    ]
    total = sum(values["total"] for values in buckets)
    if not total:
        return None, None
    up = sum(values["up"] for values in buckets)
    failed = sum(values["failed"] for values in buckets)
    return round(up / total * 100, 2), round(failed / total * 100, 2)


def _stale_hours(tier):
    return (
        MONITORING_CRITICAL_STALE_HOURS
        if tier == "critical"
        else MONITORING_FULL_STALE_HOURS
    )


def _is_stale(last_checked_at, tier, now):
    if not last_checked_at:
        return True
    if isinstance(last_checked_at, str):
        last_checked_at = datetime.fromisoformat(last_checked_at)
    return last_checked_at < now - timedelta(hours=_stale_hours(tier))


def build_snapshot_entry(latest, previous_entry, now, definition=None):
    """Build the rich dashboard entry for a result from the completed run."""
    previous_entry = previous_entry or {}
    hourly_counts = add_to_hourly_counts(
        previous_entry.get("hourly_counts", {}), latest, now
    )
    uptime_24h, error_rate_24h = window_rates(hourly_counts, now, 24)
    uptime_7d, _ = window_rates(hourly_counts, now, 24 * 7)
    tier = getattr(latest, "tier", None) or (definition or {}).get("tier")
    severity = getattr(latest, "severity", None) or (definition or {}).get("severity")
    target = getattr(latest, "target", None)
    if target is None and definition:
        target = get_check_target(definition)
    checked_at = getattr(latest, "checked_at", None)
    return {
        "check_id": latest.check_id,
        "name": getattr(latest, "check_name", None) or (definition or {}).get("name"),
        "target": target,
        "tier": tier,
        "severity": severity,
        "status": latest.status,
        "last_checked_at": checked_at.isoformat() if checked_at else None,
        "response_time_ms": getattr(latest, "response_time_ms", None),
        "uptime_24h": uptime_24h,
        "uptime_7d": uptime_7d,
        "error_rate_24h": error_rate_24h,
        "alert_active": next_alert_active(
            latest, previous_entry.get("alert_active", False)
        ),
        "stale": _is_stale(checked_at, tier, now),
        "error_type": getattr(latest, "error_type", None),
        "error_message": getattr(latest, "error_message", None),
        "hourly_counts": hourly_counts,
    }


def _preserved_snapshot_entry(definition, previous_entry, now):
    """Keep an unexecuted check while refreshing metadata and staleness."""
    entry = dict(previous_entry or {})
    entry.update(
        {
            "check_id": definition["id"],
            "name": definition["name"],
            "target": get_check_target(definition),
            "tier": definition["tier"],
            "severity": definition["severity"],
        }
    )
    entry.setdefault("status", "unknown")
    entry.setdefault("last_checked_at", None)
    entry.setdefault("response_time_ms", None)
    entry.setdefault("uptime_24h", None)
    entry.setdefault("uptime_7d", None)
    entry.setdefault("error_rate_24h", None)
    entry.setdefault("alert_active", False)
    entry.setdefault("error_type", None)
    entry.setdefault("error_message", None)
    hourly_counts = _prune_hourly_counts(entry.get("hourly_counts", {}), now)
    uptime_24h, error_rate_24h = window_rates(hourly_counts, now, 24)
    uptime_7d, _ = window_rates(hourly_counts, now, 24 * 7)
    entry["hourly_counts"] = hourly_counts
    entry["uptime_24h"] = uptime_24h
    entry["uptime_7d"] = uptime_7d
    entry["error_rate_24h"] = error_rate_24h
    entry["stale"] = _is_stale(entry["last_checked_at"], definition["tier"], now)
    return entry


def update_snapshot(run_id):
    """Transactionally update all enabled check entries after a completed run."""
    run = get_run(run_id)
    if not run:
        return None

    now = datetime.now(CHICAGO_TZ)
    results = get_results_for_run(run_id)
    definitions = {
        definition["id"]: definition
        for definition in get_check_definitions()
        if definition["enabled"]
    }
    results_by_id = {result.check_id: result for result in results}

    def build_checks(previous_checks):
        previous_by_id = {
            entry["check_id"]: entry
            for entry in previous_checks
            if entry.get("check_id")
        }
        entries = {}
        for check_id, definition in definitions.items():
            latest = results_by_id.get(check_id)
            if latest:
                entries[check_id] = build_snapshot_entry(
                    latest, previous_by_id.get(check_id), now, definition
                )
            else:
                entries[check_id] = _preserved_snapshot_entry(
                    definition, previous_by_id.get(check_id), now
                )

        # Preserve a result from an older compatible runner even if its
        # definition was removed between the start and finish of the run.
        for check_id, latest in results_by_id.items():
            if check_id not in entries:
                entries[check_id] = build_snapshot_entry(
                    latest, previous_by_id.get(check_id), now
                )
        return sorted(entries.values(), key=lambda entry: entry["check_id"])

    persisted_run_id = getattr(run, "uid", None)
    if not persisted_run_id and getattr(run, "key", None):
        persisted_run_id = run.key.id()
    return modify_dashboard_snapshot(
        build_checks,
        last_run_id=persisted_run_id or run_id,
        last_run_finished_at=run.end_time or now,
    )
