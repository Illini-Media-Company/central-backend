"""
This file defines the read-only API routes for the backend console monitoring
dashboard: current status, recent runs, one run's results, and one check's
history.

Created by Gus Nophaket on Oct. 5, 2026
Last modified Oct. 5, 2026
"""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_login import login_required

from constants import MONITORING_ACCESS_GROUPS
from db.monitoring import (
    get_dashboard_snapshot,
    get_recent_runs,
    get_run,
    get_results_for_run,
    get_results_for_check_since,
)
from util.security import restrict_to

# Imported so the check definitions are validated when the app starts
import util.monitoring_checks  # noqa: F401

monitoring_routes = Blueprint("monitoring_routes", __name__, url_prefix="/monitoring")

RUNS_DEFAULT_LIMIT = 20
RUNS_MAX_LIMIT = 100
HISTORY_DEFAULT_DAYS = 7
HISTORY_MAX_DAYS = 30  # Results are only kept for 30 days
HISTORY_CACHE_SECONDS = 5 * 60

# (check_id, days) -> (expires_at, payload). In memory is fine: the app runs on
# a single instance (app.yaml min/max_instances = 1).
_history_cache = {}


def _isoformat(value):
    return value.isoformat() if value else None


def _run_to_dict(run):
    return {
        "run_id": run.uid,
        "trigger": run.trigger,
        "tier": run.tier,
        "run_status": run.run_status,
        "start_time": _isoformat(run.start_time),
        "end_time": _isoformat(run.end_time),
        "total": run.total,
        "healthy": run.healthy,
        "degraded": run.degraded,
        "failed": run.failed,
    }


def _result_to_dict(result):
    return {
        "result_id": result.uid,
        "run_id": result.run.id() if result.run else None,
        "check_id": result.check_id,
        "check_name": result.check_name,
        "target": result.target,
        "tier": result.tier,
        "checked_at": _isoformat(result.checked_at),
        "response_time_ms": result.response_time_ms,
        "latency_threshold_ms": result.latency_threshold_ms,
        "attempts": result.attempts,
        "status": result.status,
        "http_status_code": result.http_status_code,
        "error_type": result.error_type,
        "error_message": result.error_message,
        "severity": result.severity,
        "alert_sent": result.alert_sent,
    }


def _int_arg(name, default, minimum, maximum):
    """Reads an int query arg. Returns (value, error message or None)."""
    raw = request.args.get(name)
    if raw is None:
        return default, None
    try:
        value = int(raw)
    except ValueError:
        return None, f"'{name}' must be an integer"
    if not minimum <= value <= maximum:
        return None, f"'{name}' must be between {minimum} and {maximum}"
    return value, None


@monitoring_routes.route("/status", methods=["GET"])
@login_required
@restrict_to(MONITORING_ACCESS_GROUPS)
def status():
    """Returns the DashboardSnapshot (one read)."""
    snapshot = get_dashboard_snapshot()
    if not snapshot:
        return (
            jsonify(
                {
                    "updated_at": None,
                    "last_run_id": None,
                    "last_run_finished_at": None,
                    "checks": [],
                }
            ),
            200,
        )

    # hourly_counts is internal bookkeeping for uptime, not for the frontend
    checks = [
        {k: v for k, v in entry.items() if k != "hourly_counts"}
        for entry in (snapshot.checks or [])
    ]
    return (
        jsonify(
            {
                "updated_at": _isoformat(snapshot.updated_at),
                "last_run_id": snapshot.last_run_id,
                "last_run_finished_at": _isoformat(snapshot.last_run_finished_at),
                "checks": checks,
            }
        ),
        200,
    )


@monitoring_routes.route("/runs", methods=["GET"])
@login_required
@restrict_to(MONITORING_ACCESS_GROUPS)
def list_runs():
    """Returns the most recent runs, newest first."""
    limit, error = _int_arg("limit", RUNS_DEFAULT_LIMIT, 1, RUNS_MAX_LIMIT)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"runs": [_run_to_dict(r) for r in get_recent_runs(limit)]}), 200


@monitoring_routes.route("/runs/<run_id>", methods=["GET"])
@login_required
@restrict_to(MONITORING_ACCESS_GROUPS)
def get_run_detail(run_id):
    """Returns one run and its check results."""
    run = get_run(run_id)
    if not run:
        return jsonify({"error": "Run not found."}), 404
    return (
        jsonify(
            {
                "run": _run_to_dict(run),
                "results": [_result_to_dict(r) for r in get_results_for_run(run_id)],
            }
        ),
        200,
    )


@monitoring_routes.route("/checks/<check_id>/history", methods=["GET"])
@login_required
@restrict_to(MONITORING_ACCESS_GROUPS)
def check_history(check_id):
    """Returns one check's results for the last `days` days, newest first. Cached 5 minutes."""
    days, error = _int_arg("days", HISTORY_DEFAULT_DAYS, 1, HISTORY_MAX_DAYS)
    if error:
        return jsonify({"error": error}), 400

    now = time.monotonic()
    # Drop expired entries so arbitrary check_ids can't grow the cache forever
    for key in [k for k, (expires, _) in _history_cache.items() if expires <= now]:
        del _history_cache[key]

    cached = _history_cache.get((check_id, days))
    if cached:
        return jsonify(cached[1]), 200

    since = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    payload = {
        "check_id": check_id,
        "days": days,
        "results": [
            _result_to_dict(r) for r in get_results_for_check_since(check_id, since)
        ],
    }
    _history_cache[(check_id, days)] = (now + HISTORY_CACHE_SECONDS, payload)
    return jsonify(payload), 200
