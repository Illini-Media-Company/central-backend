"""
This file defines the helper functions the backend console monitoring runner
calls: deciding a check's status, saving its result, finishing a run, alert
state, and rebuilding the dashboard snapshot. All database access goes through
the functions in db/monitoring.py.

Created by Gus Nophaket on Oct. 4, 2026
Last modified Oct. 4, 2026
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from db.monitoring import (
    create_check_result,
    get_run,
    get_results_for_run,
    update_run,
    get_dashboard_snapshot,
    modify_dashboard_snapshot,
)


def compute_status(outcome_ok, response_time_ms, latency_threshold_ms):
    """
    Returns "failed" if the check failed, "degraded" if it passed but was slower
    than its latency threshold, else "healthy". A response time exactly equal
    to the threshold is healthy.
    """
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
    """
    Saves one check's outcome as a CheckResult and returns it.

    definition: a check definition dict (id, name, tier, severity,
        latency_threshold_ms, params).
    outcome: dict with status, response_time_ms, attempts, http_status_code,
        error_type, error_message, checked_at.

    Name, tier, severity, latency threshold and target are copied from the
    definition so history stays accurate if the definition changes later.
    """
    return create_check_result(
        run_id=run_id,
        check_id=definition["id"],
        status=outcome["status"],
        check_name=definition.get("name"),
        target=(definition.get("params") or {}).get("target"),
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
    """Returns a dict of total/healthy/degraded/failed counts for a list of CheckResults."""
    counts = {"total": len(results), "healthy": 0, "degraded": 0, "failed": 0}
    for result in results:
        counts[result.status] += 1
    return counts


def finish_run(run_id):
    """
    Marks a Run completed, sets its end time, and stores the status counts of
    its results. Returns the Run, or None if it doesn't exist.
    """
    counts = count_statuses(get_results_for_run(run_id))
    return update_run(
        run_id,
        run_status="completed",
        end_time=datetime.now(ZoneInfo("America/Chicago")),
        **counts,
    )


def is_alert_active(check_id):
    """
    Returns True if this check is in an ongoing failure that was already
    alerted on. Reads the DashboardSnapshot, so the runner must call this
    before update_snapshot() for the current run.
    """
    snapshot = get_dashboard_snapshot()
    for entry in (snapshot.checks or []) if snapshot else []:
        if entry["check_id"] == check_id:
            return entry.get("alert_active", False)
    return False


def next_alert_active(latest, previously_active):
    """
    Alert state after this result. Stays active for the whole failure streak,
    however long, so each outage sends exactly one alert. Clears on the first
    non-failed result.
    """
    return latest.status == "failed" and (latest.alert_sent or previously_active)


def _hour_key(dt):
    """ISO string for the start of dt's hour, with UTC offset so DST hours stay distinct."""
    return dt.replace(minute=0, second=0, microsecond=0).isoformat()


def add_to_hourly_counts(hourly_counts, latest, now):
    """
    Returns a new hourly_counts dict with this result added (critical tier only)
    and hours older than 7 days removed. Each value is {"up", "failed", "total"}.
    """
    counts = {
        hour: dict(c)
        for hour, c in hourly_counts.items()
        if datetime.fromisoformat(hour) >= now - timedelta(days=7)
    }
    if latest.tier == "critical" and latest.checked_at:
        hour = _hour_key(latest.checked_at)
        bucket = counts.setdefault(hour, {"up": 0, "failed": 0, "total": 0})
        bucket["total"] += 1
        if latest.status == "failed":
            bucket["failed"] += 1
        else:
            bucket["up"] += 1  # Degraded counts as up
    return counts


def window_rates(hourly_counts, now, hours):
    """
    Returns (uptime, error_rate) over the hourly buckets in the last `hours`
    hours, or (None, None) if there are no results. Accurate to within one hour.
    """
    cutoff = now - timedelta(hours=hours)
    buckets = [
        c for hour, c in hourly_counts.items() if datetime.fromisoformat(hour) >= cutoff
    ]
    total = sum(c["total"] for c in buckets)
    if not total:
        return None, None
    up = sum(c["up"] for c in buckets)
    failed = sum(c["failed"] for c in buckets)
    return round(up / total, 4), round(failed / total, 4)


def build_snapshot_entry(latest, previous_entry, now):
    """
    Builds one item of DashboardSnapshot.checks from the check's result in the
    run that just finished and its entry in the previous snapshot. Uptime comes
    from hourly counts carried in the entry, so no history query is needed.
    """
    previous_entry = previous_entry or {}
    hourly_counts = add_to_hourly_counts(
        previous_entry.get("hourly_counts", {}), latest, now
    )
    uptime_24h, error_rate_24h = window_rates(hourly_counts, now, 24)
    uptime_7d, _ = window_rates(hourly_counts, now, 24 * 7)
    return {
        "check_id": latest.check_id,
        "name": latest.check_name,
        "status": latest.status,
        # JsonProperty can't hold datetimes, so timestamps are ISO strings
        "last_checked_at": (
            latest.checked_at.isoformat() if latest.checked_at else None
        ),
        "response_time_ms": latest.response_time_ms,
        "uptime_24h": uptime_24h,
        "uptime_7d": uptime_7d,
        "error_rate_24h": error_rate_24h,
        "alert_active": next_alert_active(
            latest, previous_entry.get("alert_active", False)
        ),
        "hourly_counts": hourly_counts,
    }


def update_snapshot(run_id):
    """
    Updates the DashboardSnapshot after a run finishes. Checks that were not in
    this run (e.g. full-tier checks during a critical run) keep their previous
    entry. Returns the snapshot, or None if the run doesn't exist.

    Reads only the run, its results and the snapshot, so cost does not grow
    with history. Call it after finish_run() and after any alert for this run
    has been marked with alert_sent=True.
    """
    run = get_run(run_id)
    if not run:
        return None

    now = datetime.now(ZoneInfo("America/Chicago"))
    results = get_results_for_run(run_id)

    def build_checks(previous_checks):
        entries = {entry["check_id"]: entry for entry in previous_checks}
        for latest in results:
            entries[latest.check_id] = build_snapshot_entry(
                latest, entries.get(latest.check_id), now
            )
        return sorted(entries.values(), key=lambda e: e["check_id"])

    return modify_dashboard_snapshot(
        build_checks,
        last_run_id=run.uid,
        last_run_finished_at=run.end_time or now,
    )
