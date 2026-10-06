"""
This file defines the models and persistence helpers used for backend console
monitoring. It stores runs, individual results, the precomputed dashboard
snapshot, cron heartbeats, and the singleton execution lease. All database
calls for monitoring must go through the helper functions in this file.

Created by Gus Nophaket on Oct. 3, 2026
Last modified Oct. 6, 2026
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.cloud import ndb

from constants import (
    MONITORING_TRIGGERS,
    MONITORING_TIERS,
    MONITORING_RUN_STATUSES,
    MONITORING_CHECK_STATUSES,
    MONITORING_SEVERITIES,
    MONITORING_ERROR_TYPES,
    MONITORING_ERROR_MESSAGE_MAX_LENGTH,
    MONITORING_CRON_JOB_STATUSES,
)

from . import client

DASHBOARD_SNAPSHOT_ID = "current"


def _truncate_error_message(prop, value):
    """Property validator that caps error messages so one noisy check can't bloat an entity."""
    if value is None:
        return None
    return value[:MONITORING_ERROR_MESSAGE_MAX_LENGTH]


def _validate_nonnegative(prop, value):
    if value is not None and value < 0:
        raise ValueError(f"{prop._name} cannot be negative")
    return value


def _validate_attempts(prop, value):
    if value is not None and value not in (1, 2):
        raise ValueError("attempts must be 1 or 2")
    return value


def _validate_limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    return limit


def _validate_positive_days(days_old):
    if isinstance(days_old, bool) or not isinstance(days_old, int) or days_old < 1:
        raise ValueError("days_old must be a positive integer")
    return days_old


class Run(ndb.Model):
    """
    One execution of every enabled check in a tier. The key id is a readable
    string (e.g. "run_20261003_140000_critical") and serves as the run_id.

    A Run stuck on "running" past its expected duration means the runner died
    mid-run.
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    trigger = ndb.StringProperty(choices=MONITORING_TRIGGERS, required=True)
    tier = ndb.StringProperty(choices=MONITORING_TIERS, required=True)
    run_status = ndb.StringProperty(choices=MONITORING_RUN_STATUSES, default="running")

    start_time = ndb.DateTimeProperty(
        auto_now_add=True, tzinfo=ZoneInfo("America/Chicago")
    )
    # None until finished
    end_time = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))

    # Counts are set when the run finishes
    total = ndb.IntegerProperty(default=0, validator=_validate_nonnegative)
    healthy = ndb.IntegerProperty(default=0, validator=_validate_nonnegative)
    degraded = ndb.IntegerProperty(default=0, validator=_validate_nonnegative)
    failed = ndb.IntegerProperty(default=0, validator=_validate_nonnegative)


class CheckResult(ndb.Model):
    """
    The outcome of one check inside a Run. Fields copied from the check
    definition (name, tier, severity, latency threshold, target) are snapshots,
    so history stays accurate if the definition changes later.

    error_message must be a string; convert with str() before assigning.
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    run = ndb.KeyProperty(kind=Run, required=True)
    check_id = ndb.StringProperty(required=True)  # Stable id from the definition
    check_name = ndb.StringProperty()  # Display name snapshot
    target = ndb.StringProperty()  # From params.target for http checks, else None
    tier = ndb.StringProperty(choices=MONITORING_TIERS)

    # When the check started
    checked_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    response_time_ms = ndb.IntegerProperty(validator=_validate_nonnegative)
    latency_threshold_ms = ndb.IntegerProperty(
        validator=_validate_nonnegative
    )  # None = speed never degrades
    attempts = ndb.IntegerProperty(default=1, validator=_validate_attempts)

    status = ndb.StringProperty(choices=MONITORING_CHECK_STATUSES, required=True)
    http_status_code = ndb.IntegerProperty()  # None for non-http checks
    error_type = ndb.StringProperty(choices=MONITORING_ERROR_TYPES)
    error_message = ndb.TextProperty(validator=_truncate_error_message)

    severity = ndb.StringProperty(choices=MONITORING_SEVERITIES)
    alert_sent = ndb.BooleanProperty(default=False)


class DashboardSnapshot(ndb.Model):
    """
    Single entity (key id DASHBOARD_SNAPSHOT_ID) overwritten at the end of
    every run so the dashboard loads with one read.

    Each item in `checks` has: check_id, name, status, last_checked_at,
    response_time_ms, uptime_24h, uptime_7d, error_rate_24h, alert_active,
    hourly_counts. Store last_checked_at as an ISO 8601 string; JsonProperty
    can't hold datetimes. hourly_counts maps each hour of the last 7 days to
    {up, failed, total} counts so uptime needs no history query.
    """

    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
    last_run_id = ndb.StringProperty()
    last_run_finished_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    checks = ndb.JsonProperty()


class CronJobHeartbeat(ndb.Model):
    """Latest observed state for one App Engine cron job."""

    job_id = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    display_name = ndb.StringProperty(required=True)
    tracking_started_at = ndb.DateTimeProperty(
        required=True, tzinfo=ZoneInfo("America/Chicago")
    )
    last_started_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    last_completed_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    last_succeeded_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    last_status = ndb.StringProperty(choices=MONITORING_CRON_JOB_STATUSES)
    last_duration_ms = ndb.IntegerProperty(validator=_validate_nonnegative)
    last_http_status = ndb.IntegerProperty()
    last_error = ndb.TextProperty(validator=_truncate_error_message)
    execution_id = ndb.StringProperty()


class MonitoringLease(ndb.Model):
    """Singleton lease preventing scheduled and manual runs from overlapping."""

    owner_id = ndb.StringProperty(required=True)
    acquired_at = ndb.DateTimeProperty(
        required=True, tzinfo=ZoneInfo("America/Chicago")
    )
    expires_at = ndb.DateTimeProperty(required=True, tzinfo=ZoneInfo("America/Chicago"))


# Fields that can never be changed through the update helpers
_RUN_READ_ONLY_FIELDS = {"uid", "start_time"}
_CHECK_RESULT_READ_ONLY_FIELDS = {"uid", "run", "check_id"}


def _apply_updates(entity, fields, read_only):
    """Sets each field on the entity. Raises ValueError on unknown or read-only fields."""
    for name, value in fields.items():
        if name not in entity._properties or name in read_only:
            raise ValueError(f"Cannot update field '{name}' on {entity._get_kind()}")
        if name == "error_message" and value is not None:
            value = str(value)
        setattr(entity, name, value)


################################################################################
##################################### RUN ######################################
################################################################################


@ndb.transactional()
def _insert_run_if_absent(run_id, trigger, tier):
    if Run.get_by_id(run_id):
        return None
    run = Run(id=run_id, trigger=trigger, tier=tier)
    run.put()
    return run


def create_run(trigger, tier):
    """
    Creates a new Run with status "running" and returns it. The id looks like
    run_20261003_140000_critical; a numeric suffix is added if two runs of the
    same tier start in the same second.
    """
    base_id = f"run_{datetime.now(ZoneInfo('America/Chicago')):%Y%m%d_%H%M%S}_{tier}"
    with client.context():
        run_id = base_id
        suffix = 2
        while True:
            run = _insert_run_if_absent(run_id, trigger, tier)
            if run:
                return run
            run_id = f"{base_id}_{suffix}"
            suffix += 1


def get_run(run_id):
    """Returns the Run with this id, or None."""
    with client.context():
        return Run.get_by_id(run_id)


def get_recent_runs(limit=20):
    """Returns the most recent Runs, newest first."""
    _validate_limit(limit)
    with client.context():
        return Run.query().order(-Run.start_time).fetch(limit)


def get_stuck_runs(minutes=15, now=None):
    """Returns runs still marked running after the supplied age threshold."""
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
        raise ValueError("minutes must be a positive integer")
    now = now or datetime.now(ZoneInfo("America/Chicago"))
    cutoff = now - timedelta(minutes=minutes)
    with client.context():
        runs = Run.query(Run.run_status == "running", Run.start_time < cutoff).fetch()
    return sorted(runs, key=lambda run: run.start_time)


def update_run(run_id, **fields):
    """Updates the given fields on a Run. Returns the Run, or None if not found."""
    with client.context():
        run = Run.get_by_id(run_id)
        if not run:
            return None
        _apply_updates(run, fields, _RUN_READ_ONLY_FIELDS)
        run.put()
        return run


def delete_run(run_id):
    """Deletes a Run and all of its CheckResults. Returns False if not found."""
    with client.context():
        run_key = ndb.Key(Run, run_id)
        if not run_key.get():
            return False

        result_keys = CheckResult.query(CheckResult.run == run_key).fetch(
            keys_only=True
        )
        ndb.delete_multi(result_keys + [run_key])
        return True


################################################################################
################################# CHECK RESULT #################################
################################################################################


def create_check_result(
    run_id,
    check_id,
    status,
    check_name=None,
    target=None,
    tier=None,
    checked_at=None,
    response_time_ms=None,
    latency_threshold_ms=None,
    attempts=1,
    http_status_code=None,
    error_type=None,
    error_message=None,
    severity=None,
    alert_sent=False,
):
    """Creates a CheckResult attached to the given Run and returns it."""
    with client.context():
        run_key = ndb.Key(Run, run_id)
        if not run_key.get():
            raise ValueError(f"Run '{run_id}' does not exist")
        result = CheckResult(
            run=run_key,
            check_id=check_id,
            status=status,
            check_name=check_name,
            target=target,
            tier=tier,
            checked_at=checked_at or datetime.now(ZoneInfo("America/Chicago")),
            response_time_ms=response_time_ms,
            latency_threshold_ms=latency_threshold_ms,
            attempts=attempts,
            http_status_code=http_status_code,
            error_type=error_type,
            error_message=None if error_message is None else str(error_message),
            severity=severity,
            alert_sent=alert_sent,
        )
        result.put()
        return result


def get_check_result(uid):
    """Returns the CheckResult with this id, or None."""
    with client.context():
        return CheckResult.get_by_id(int(uid))


def get_results_for_run(run_id):
    """Returns every CheckResult in a Run, in the order the checks started."""
    with client.context():
        results = CheckResult.query(CheckResult.run == ndb.Key(Run, run_id)).fetch()
    # Sorted here instead of in the query so no extra composite index is needed
    return sorted(results, key=lambda r: (r.checked_at is None, r.checked_at))


def get_results_for_check(check_id, limit=20):
    """Returns the most recent CheckResults for one check, newest first."""
    if limit is not None:
        _validate_limit(limit)
    with client.context():
        return (
            CheckResult.query(CheckResult.check_id == check_id)
            .order(-CheckResult.checked_at)
            .fetch(limit)
        )


def get_latest_result_for_check(check_id):
    """Returns the newest result for a check, or None when it has never run."""
    results = get_results_for_check(check_id, limit=1)
    return results[0] if results else None


def has_active_alert_for_check(check_id):
    """Return whether the current consecutive failure streak was alerted.

    Recent results are authoritative when they include a recovery or the
    original alerted failure. If retention has removed that original result,
    fall back to the snapshot's durable transition state.
    """
    for result in get_results_for_check(check_id, limit=None):
        if result.status != "failed":
            return False
        if result.alert_sent:
            return True
    snapshot = get_dashboard_snapshot()
    for entry in (snapshot.checks or []) if snapshot else []:
        if entry.get("check_id") == check_id:
            return bool(entry.get("alert_active"))
    return False


def get_results_for_check_since(check_id, since):
    """Returns results for one check at or after ``since``, newest first."""
    if not isinstance(since, datetime):
        raise ValueError("since must be a datetime")
    with client.context():
        return (
            CheckResult.query(
                CheckResult.check_id == check_id, CheckResult.checked_at >= since
            )
            .order(-CheckResult.checked_at)
            .fetch()
        )


def update_check_result(uid, **fields):
    """Updates the given fields on a CheckResult. Returns it, or None if not found."""
    with client.context():
        result = CheckResult.get_by_id(int(uid))
        if not result:
            return None
        _apply_updates(result, fields, _CHECK_RESULT_READ_ONLY_FIELDS)
        result.put()
        return result


def delete_check_result(uid):
    """Deletes one CheckResult. Returns False if not found."""
    with client.context():
        result_key = ndb.Key(CheckResult, int(uid))
        if not result_key.get():
            return False
        result_key.delete()
        return True


def delete_old_check_results(days_old=30):
    """Deletes CheckResults older than days_old. Returns how many were deleted."""
    _validate_positive_days(days_old)
    with client.context():
        cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days_old)
        keys = CheckResult.query(CheckResult.checked_at < cutoff).fetch(keys_only=True)
        if keys:
            ndb.delete_multi(keys)
        return len(keys)


def delete_old_monitoring_data(days_old=30):
    """Delete expired results and runs, returning deletion counts.

    Old running records are abandoned executions, not active work. Retaining
    them forever would make the watcher health endpoint permanently report a
    stuck run after the history-retention window has elapsed.
    """
    _validate_positive_days(days_old)
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days_old)
    with client.context():
        result_keys = CheckResult.query(CheckResult.checked_at < cutoff).fetch(
            keys_only=True
        )
        run_keys = Run.query(Run.start_time < cutoff).fetch(keys_only=True)
        if result_keys or run_keys:
            ndb.delete_multi(result_keys + run_keys)
    return {"check_results": len(result_keys), "runs": len(run_keys)}


################################################################################
############################## DASHBOARD SNAPSHOT ##############################
################################################################################


def get_dashboard_snapshot():
    """Returns the DashboardSnapshot, or None if no run has finished yet."""
    with client.context():
        return DashboardSnapshot.get_by_id(DASHBOARD_SNAPSHOT_ID)


def modify_dashboard_snapshot(build_checks, last_run_id, last_run_finished_at):
    """
    Read-modify-writes the DashboardSnapshot in a transaction so two runs
    finishing at the same time can't overwrite each other's counts.

    build_checks(previous_checks) -> new checks list. It may run more than once
    if the transaction retries, so it must not have side effects.
    """
    with client.context():

        def txn():
            previous = DashboardSnapshot.get_by_id(DASHBOARD_SNAPSHOT_ID)
            snapshot = DashboardSnapshot(
                id=DASHBOARD_SNAPSHOT_ID,
                last_run_id=last_run_id,
                last_run_finished_at=last_run_finished_at,
                checks=build_checks((previous.checks or []) if previous else []),
            )
            snapshot.put()
            return snapshot

        return ndb.transaction(txn)


def check_datastore_connection(timeout_seconds=3):
    """Performs a harmless strongly-consistent key lookup to verify Datastore."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    with client.context():
        ndb.Key(DashboardSnapshot, DASHBOARD_SNAPSHOT_ID).get(timeout=timeout_seconds)
    return True


################################################################################
############################## MONITORING LEASE ###############################
################################################################################


MONITORING_LEASE_ID = "active"


@ndb.transactional()
def _acquire_monitoring_lease(owner_id, now, expires_at):
    lease = MonitoringLease.get_by_id(MONITORING_LEASE_ID)
    if lease and lease.expires_at > now:
        return False
    MonitoringLease(
        id=MONITORING_LEASE_ID,
        owner_id=owner_id,
        acquired_at=now,
        expires_at=expires_at,
    ).put()
    return True


def acquire_monitoring_lease(owner_id, lease_minutes, now=None):
    """Atomically acquire the runner lease, replacing it only after expiry."""
    if not owner_id:
        raise ValueError("owner_id is required")
    if (
        isinstance(lease_minutes, bool)
        or not isinstance(lease_minutes, int)
        or lease_minutes < 1
    ):
        raise ValueError("lease_minutes must be a positive integer")
    now = now or datetime.now(ZoneInfo("America/Chicago"))
    with client.context():
        return _acquire_monitoring_lease(
            owner_id, now, now + timedelta(minutes=lease_minutes)
        )


@ndb.transactional()
def _release_monitoring_lease(owner_id):
    lease = MonitoringLease.get_by_id(MONITORING_LEASE_ID)
    if not lease or lease.owner_id != owner_id:
        return False
    lease.key.delete()
    return True


def release_monitoring_lease(owner_id):
    """Release the lease only when it is still owned by this execution."""
    if not owner_id:
        raise ValueError("owner_id is required")
    with client.context():
        return _release_monitoring_lease(owner_id)


################################################################################
############################ CRON JOB HEARTBEATS ###############################
################################################################################


@ndb.transactional(retries=0)
def _ensure_cron_job_heartbeat(job_id, display_name, now):
    heartbeat = CronJobHeartbeat.get_by_id(job_id)
    if heartbeat:
        if heartbeat.display_name != display_name:
            heartbeat.display_name = display_name
            heartbeat.put()
        return heartbeat
    heartbeat = CronJobHeartbeat(
        id=job_id,
        display_name=display_name,
        tracking_started_at=now,
    )
    heartbeat.put()
    return heartbeat


def ensure_cron_job_heartbeat(job_id, display_name, now=None):
    """Create a placeholder used to distinguish rollout grace from staleness."""
    if not job_id or not display_name:
        raise ValueError("job_id and display_name are required")
    now = now or datetime.now(ZoneInfo("America/Chicago"))
    with client.context():
        return _ensure_cron_job_heartbeat(job_id, display_name, now)


@ndb.transactional(retries=0)
def _begin_cron_job(job_id, display_name, execution_id, started_at):
    heartbeat = CronJobHeartbeat.get_by_id(job_id)
    if not heartbeat:
        heartbeat = CronJobHeartbeat(
            id=job_id,
            display_name=display_name,
            tracking_started_at=started_at,
        )
    heartbeat.display_name = display_name
    heartbeat.last_started_at = started_at
    heartbeat.last_status = "running"
    heartbeat.last_duration_ms = None
    heartbeat.last_http_status = None
    heartbeat.last_error = None
    heartbeat.execution_id = execution_id
    heartbeat.put()
    return heartbeat


def begin_cron_job(job_id, display_name, execution_id, started_at=None):
    """Mark a genuine scheduled execution as running."""
    if not job_id or not display_name or not execution_id:
        raise ValueError("job_id, display_name, and execution_id are required")
    started_at = started_at or datetime.now(ZoneInfo("America/Chicago"))
    with client.context():
        return _begin_cron_job(job_id, display_name, execution_id, started_at)


@ndb.transactional(retries=0)
def _finish_cron_job(
    job_id,
    execution_id,
    succeeded,
    completed_at,
    http_status,
    error_message,
):
    heartbeat = CronJobHeartbeat.get_by_id(job_id)
    if not heartbeat or heartbeat.execution_id != execution_id:
        return None
    heartbeat.last_completed_at = completed_at
    heartbeat.last_status = "succeeded" if succeeded else "failed"
    if heartbeat.last_started_at:
        heartbeat.last_duration_ms = max(
            0,
            round((completed_at - heartbeat.last_started_at).total_seconds() * 1000),
        )
    heartbeat.last_http_status = http_status
    heartbeat.last_error = (
        None if succeeded else str(error_message or "Cron job failed")
    )
    if succeeded:
        heartbeat.last_succeeded_at = completed_at
    heartbeat.put()
    return heartbeat


def finish_cron_job(
    job_id,
    execution_id,
    succeeded,
    http_status=None,
    error_message=None,
    completed_at=None,
):
    """Finish an execution unless a newer overlapping execution replaced it."""
    if not job_id or not execution_id:
        raise ValueError("job_id and execution_id are required")
    completed_at = completed_at or datetime.now(ZoneInfo("America/Chicago"))
    with client.context():
        return _finish_cron_job(
            job_id,
            execution_id,
            bool(succeeded),
            completed_at,
            http_status,
            error_message,
        )


def get_cron_job_heartbeat(job_id):
    with client.context():
        return CronJobHeartbeat.get_by_id(job_id)


def get_cron_job_heartbeats():
    with client.context():
        return sorted(
            CronJobHeartbeat.query().fetch(),
            key=lambda heartbeat: heartbeat.display_name.lower(),
        )
