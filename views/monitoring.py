"""Health, execution, and history routes for backend monitoring."""

from datetime import datetime, timedelta
import logging
from threading import Lock
import time
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_login import login_required

from constants import (
    MONITORING_STUCK_RUN_MINUTES,
    MONITORING_TIERS,
    MONITORING_WATCHER_STALE_HOURS,
    TOOLS_ADMIN_ACCESS_GROUPS,
)
from db.monitoring import (
    check_datastore_connection,
    get_dashboard_snapshot,
    get_cron_job_heartbeats,
    get_recent_runs,
    get_results_for_check,
    get_results_for_check_since,
    get_results_for_run,
    get_run,
    get_stuck_runs,
)
from util.monitoring import (
    MonitoringRunInProgress,
    get_check_definition,
    get_check_definitions,
    run_monitoring,
)
from util.security import csrf, restrict_to


logger = logging.getLogger(__name__)
monitoring_routes = Blueprint("monitoring_routes", __name__)
CHICAGO_TZ = ZoneInfo("America/Chicago")
_history_cache = {}
_history_cache_lock = Lock()
HISTORY_CACHE_SECONDS = 5 * 60


def _isoformat(value):
    return value.isoformat() if value else None


def _run_json(run):
    run_id = run.key.id() if getattr(run, "key", None) else run.uid
    return {
        "run_id": run_id,
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


def _result_json(result):
    result_id = result.key.id() if getattr(result, "key", None) else result.uid
    return {
        "id": result_id,
        "run_id": result.run.id(),
        "check_id": result.check_id,
        "check_name": result.check_name,
        "target": result.target,
        "tier": result.tier,
        "severity": result.severity,
        "checked_at": _isoformat(result.checked_at),
        "response_time_ms": result.response_time_ms,
        "latency_threshold_ms": result.latency_threshold_ms,
        "attempts": result.attempts,
        "status": result.status,
        "http_status_code": result.http_status_code,
        "error_type": result.error_type,
        "error_message": result.error_message,
        "alert_sent": result.alert_sent,
    }


def _legacy_result_json(result):
    payload = _result_json(result)
    payload["result_id"] = payload.pop("id")
    return payload


def _snapshot_json(snapshot):
    if not snapshot:
        return {
            "updated_at": None,
            "last_run_id": None,
            "last_run_finished_at": None,
            "checks": [],
        }
    return {
        "updated_at": _isoformat(snapshot.updated_at),
        "last_run_id": snapshot.last_run_id,
        "last_run_finished_at": _isoformat(snapshot.last_run_finished_at),
        "checks": [
            {key: value for key, value in entry.items() if key != "hourly_counts"}
            for entry in snapshot.checks or []
        ],
    }


def _deprecated(response, successor):
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{successor}>; rel="successor-version"'
    return response


def _cron_definition_by_job_id():
    return {
        definition["params"]["job_id"]: definition
        for definition in get_check_definitions()
        if definition["params"].get("handler") == "cron_heartbeat"
    }


def _cron_heartbeat_json(heartbeat, now, definitions):
    definition = definitions.get(heartbeat.key.id())
    max_age = definition["params"]["max_success_age_minutes"] if definition else None
    reference = heartbeat.last_succeeded_at or heartbeat.tracking_started_at
    overdue = bool(
        max_age and reference and now > reference + timedelta(minutes=max_age)
    )
    return {
        "job_id": heartbeat.key.id(),
        "display_name": heartbeat.display_name,
        "last_status": heartbeat.last_status,
        "tracking_started_at": _isoformat(heartbeat.tracking_started_at),
        "last_started_at": _isoformat(heartbeat.last_started_at),
        "last_completed_at": _isoformat(heartbeat.last_completed_at),
        "last_succeeded_at": _isoformat(heartbeat.last_succeeded_at),
        "last_duration_ms": heartbeat.last_duration_ms,
        "last_http_status": heartbeat.last_http_status,
        "last_error": heartbeat.last_error,
        "overdue": overdue,
    }


def _parse_limit():
    raw_limit = request.args.get("limit", "20")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer between 1 and 100") from exc
    if not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    return limit


@monitoring_routes.route("/health/live", methods=["GET"])
def health_live():
    return jsonify({"status": "ok"}), 200


@monitoring_routes.route("/health/ready", methods=["GET"])
def health_ready():
    try:
        check_datastore_connection()
    except Exception:
        logger.exception("Backend readiness Datastore check failed")
        return (
            jsonify({"status": "not_ready", "dependencies": {"datastore": "failed"}}),
            503,
        )
    return jsonify({"status": "ready", "dependencies": {"datastore": "ok"}}), 200


@monitoring_routes.route("/health/monitoring", methods=["GET"])
def health_monitoring():
    """Generic external signal for a stale or stuck in-application watcher."""
    try:
        snapshot = get_dashboard_snapshot()
        stuck_runs = get_stuck_runs(MONITORING_STUCK_RUN_MINUTES)
        cutoff = datetime.now(CHICAGO_TZ) - timedelta(
            hours=MONITORING_WATCHER_STALE_HOURS
        )
        healthy = bool(
            snapshot
            and snapshot.last_run_finished_at
            and snapshot.last_run_finished_at >= cutoff
            and not stuck_runs
        )
    except Exception:
        logger.exception("Monitoring heartbeat health check failed")
        healthy = False
    return jsonify({"status": "ok" if healthy else "not_ready"}), (
        200 if healthy else 503
    )


@monitoring_routes.route("/cron/backend-monitoring/<tier>", methods=["GET", "POST"])
@csrf.exempt
def cron_monitoring(tier):
    if request.headers.get("X-Appengine-Cron") != "true":
        logger.warning("Unauthorized backend monitoring cron request")
        return jsonify({"error": "Unauthorized"}), 403
    if tier not in MONITORING_TIERS:
        return jsonify({"error": "Invalid monitoring tier"}), 400
    trigger = "pre_peak" if tier == "critical" else "scheduled"
    try:
        return jsonify(run_monitoring(tier=tier, trigger=trigger)), 200
    except MonitoringRunInProgress as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception:
        logger.exception("Backend monitoring cron run failed")
        return jsonify({"error": "Monitoring run failed"}), 500


@monitoring_routes.route("/api/monitoring/runs", methods=["POST"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def create_manual_run():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    tier = payload.get("tier")
    if tier not in MONITORING_TIERS:
        return jsonify({"error": "tier must be 'critical' or 'full'"}), 400
    try:
        return jsonify(run_monitoring(tier=tier, trigger="manual")), 200
    except MonitoringRunInProgress as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception:
        logger.exception("Manual backend monitoring run failed")
        return jsonify({"error": "Monitoring run failed"}), 500


@monitoring_routes.route("/api/monitoring/dashboard", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def dashboard():
    snapshot = get_dashboard_snapshot()
    last_run = (
        get_run(snapshot.last_run_id) if snapshot and snapshot.last_run_id else None
    )
    stuck_runs = get_stuck_runs(MONITORING_STUCK_RUN_MINUTES)
    cron_heartbeats = get_cron_job_heartbeats()
    now = datetime.now(CHICAGO_TZ)
    cron_definitions = _cron_definition_by_job_id()
    return (
        jsonify(
            {
                "snapshot": (_snapshot_json(snapshot) if snapshot else None),
                "last_run": _run_json(last_run) if last_run else None,
                "stuck_runs": [_run_json(run) for run in stuck_runs],
                "cron_jobs": [
                    _cron_heartbeat_json(heartbeat, now, cron_definitions)
                    for heartbeat in cron_heartbeats
                ],
            }
        ),
        200,
    )


@monitoring_routes.route("/api/monitoring/runs", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def list_runs():
    try:
        limit = _parse_limit()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"runs": [_run_json(run) for run in get_recent_runs(limit)]}), 200


@monitoring_routes.route("/api/monitoring/runs/<run_id>", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def run_detail(run_id):
    run = get_run(run_id)
    if not run:
        return jsonify({"error": "Monitoring run not found"}), 404
    return (
        jsonify(
            {
                "run": _run_json(run),
                "results": [
                    _result_json(result) for result in get_results_for_run(run_id)
                ],
            }
        ),
        200,
    )


@monitoring_routes.route("/api/monitoring/checks/<check_id>", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def check_history(check_id):
    definition = get_check_definition(check_id)
    if not definition:
        return jsonify({"error": "Monitoring check not found"}), 404
    try:
        limit = _parse_limit()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    results = get_results_for_check(check_id, limit)
    return (
        jsonify(
            {
                "check": definition,
                "results": [_result_json(result) for result in results],
            }
        ),
        200,
    )


# Compatibility routes retained for the dashboard work already contributed on
# this branch. New clients may use /api/monitoring while the frontend can keep
# using its original /monitoring contract.
@monitoring_routes.route("/monitoring/status", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def legacy_status():
    return _deprecated(
        jsonify(_snapshot_json(get_dashboard_snapshot())),
        "/api/monitoring/dashboard",
    )


@monitoring_routes.route("/monitoring/runs", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def legacy_list_runs():
    try:
        limit = _parse_limit()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return _deprecated(
        jsonify({"runs": [_run_json(run) for run in get_recent_runs(limit)]}),
        "/api/monitoring/runs",
    )


@monitoring_routes.route("/monitoring/runs/<run_id>", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def legacy_run_detail(run_id):
    run = get_run(run_id)
    if not run:
        return jsonify({"error": "Run not found."}), 404
    return _deprecated(
        jsonify(
            {
                "run": _run_json(run),
                "results": [
                    _legacy_result_json(result)
                    for result in get_results_for_run(run_id)
                ],
            }
        ),
        f"/api/monitoring/runs/{run_id}",
    )


@monitoring_routes.route("/monitoring/checks/<check_id>/history", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def legacy_check_history(check_id):
    if not get_check_definition(check_id):
        return jsonify({"error": "Monitoring check not found"}), 404
    raw_days = request.args.get("days", "7")
    try:
        days = int(raw_days)
    except ValueError:
        return jsonify({"error": "'days' must be an integer"}), 400
    if not 1 <= days <= 30:
        return jsonify({"error": "'days' must be between 1 and 30"}), 400

    now = time.monotonic()
    cache_key = (check_id, days)
    with _history_cache_lock:
        expired_keys = [
            key for key, (expires, _) in _history_cache.items() if expires <= now
        ]
        for key in expired_keys:
            _history_cache.pop(key, None)
        cached = _history_cache.get(cache_key)
    if cached:
        return _deprecated(jsonify(cached[1]), f"/api/monitoring/checks/{check_id}")

    since = datetime.now(CHICAGO_TZ) - timedelta(days=days)
    payload = {
        "check_id": check_id,
        "days": days,
        "results": [
            _legacy_result_json(result)
            for result in get_results_for_check_since(check_id, since)
        ],
    }
    with _history_cache_lock:
        _history_cache[cache_key] = (now + HISTORY_CACHE_SECONDS, payload)
    return _deprecated(jsonify(payload), f"/api/monitoring/checks/{check_id}")
