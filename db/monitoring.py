"""
This file defines the Run, CheckResult and DashboardSnapshot classes used for
backend console monitoring. A Run is one execution of a tier of checks, a
CheckResult is the outcome of one check inside a Run, and DashboardSnapshot is
a single precomputed entity the dashboard reads in one call. All database
calls for monitoring must go through the helper functions in this file.

Created by Gus Nophaket on Oct. 3, 2026
Last modified Oct. 5, 2026
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
)

from . import client

DASHBOARD_SNAPSHOT_ID = "current"


def _truncate_error_message(prop, value):
    """Property validator that caps error messages so one noisy check can't bloat an entity."""
    if value is None:
        return None
    return value[:MONITORING_ERROR_MESSAGE_MAX_LENGTH]


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
    total = ndb.IntegerProperty(default=0)
    healthy = ndb.IntegerProperty(default=0)
    degraded = ndb.IntegerProperty(default=0)
    failed = ndb.IntegerProperty(default=0)


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
    # Only critical-tier results count toward uptime
    tier = ndb.StringProperty(choices=MONITORING_TIERS)

    # When the check started
    checked_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    response_time_ms = ndb.IntegerProperty()
    latency_threshold_ms = ndb.IntegerProperty()  # None = speed never degrades
    attempts = ndb.IntegerProperty(default=1)  # 1 or 2 (max one retry)

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
    critical-tier {up, failed, total} counts so uptime needs no history query.
    """

    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
    last_run_id = ndb.StringProperty()
    last_run_finished_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    checks = ndb.JsonProperty()


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
    with client.context():
        return Run.query().order(-Run.start_time).fetch(limit)


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


def find_stuck_runs(older_than_minutes=30):
    """Returns Runs still "running" that started more than older_than_minutes ago."""
    with client.context():
        cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(
            minutes=older_than_minutes
        )
        return Run.query(Run.run_status == "running", Run.start_time < cutoff).fetch()


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
        result = CheckResult(
            run=ndb.Key(Run, run_id),
            check_id=check_id,
            status=status,
            check_name=check_name,
            target=target,
            tier=tier,
            checked_at=checked_at,
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
    with client.context():
        return (
            CheckResult.query(CheckResult.check_id == check_id)
            .order(-CheckResult.checked_at)
            .fetch(limit)
        )


def get_results_for_check_since(check_id, since):
    """Returns every CheckResult for one check with checked_at >= since, newest first."""
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
    with client.context():
        cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days_old)
        keys = CheckResult.query(CheckResult.checked_at < cutoff).fetch(keys_only=True)
        if keys:
            ndb.delete_multi(keys)
        return len(keys)


################################################################################
############################## DASHBOARD SNAPSHOT ##############################
################################################################################


def get_dashboard_snapshot():
    """Returns the DashboardSnapshot, or None if no run has finished yet."""
    with client.context():
        return DashboardSnapshot.get_by_id(DASHBOARD_SNAPSHOT_ID)


def set_dashboard_snapshot(last_run_id, last_run_finished_at, checks):
    """Creates or overwrites the DashboardSnapshot and returns it."""
    with client.context():
        snapshot = DashboardSnapshot(
            id=DASHBOARD_SNAPSHOT_ID,
            last_run_id=last_run_id,
            last_run_finished_at=last_run_finished_at,
            checks=checks,
        )
        snapshot.put()
        return snapshot


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
