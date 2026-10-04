"""
This file defines the Run, CheckResult and DashboardSnapshot classes used for
backend console monitoring. A Run is one execution of a tier of checks, a
CheckResult is the outcome of one check inside a Run, and DashboardSnapshot is
a single precomputed entity the dashboard reads in one call.

Created by Gus Nophaket on Oct. 3, 2026
Last modified Oct. 3, 2026
"""

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
    response_time_ms, uptime_24h, uptime_7d, error_rate_24h, alert_active.
    Store last_checked_at as an ISO 8601 string; JsonProperty can't hold datetimes.
    """

    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
    last_run_id = ndb.StringProperty()
    last_run_finished_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    checks = ndb.JsonProperty()
