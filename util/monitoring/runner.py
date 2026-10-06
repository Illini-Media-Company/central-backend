"""Orchestration for complete backend monitoring runs."""

from datetime import datetime
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

from constants import (
    MONITORING_RETENTION_DAYS,
    MONITORING_STUCK_RUN_MINUTES,
    MONITORING_TIERS,
    MONITORING_TRIGGERS,
)
from db.monitoring import (
    create_check_result,
    create_run,
    delete_old_monitoring_data,
    has_active_alert_for_check,
    acquire_monitoring_lease,
    release_monitoring_lease,
    update_check_result,
    update_run,
)
from util.monitoring.alerts import send_alert_transition
from util.monitoring.checks import CheckExecution, execute_check
from util.monitoring.definitions import (
    get_checks_for_tier,
    get_check_target,
)
from util.monitoring.snapshot import update_snapshot


logger = logging.getLogger(__name__)
CHICAGO_TZ = ZoneInfo("America/Chicago")


class MonitoringRunInProgress(RuntimeError):
    """Raised when another monitoring execution currently owns the lease."""


def _unexpected_execution(exc):
    return CheckExecution(
        checked_at=datetime.now(CHICAGO_TZ),
        response_time_ms=0,
        attempts=1,
        status="failed",
        error_type="unexpected_error",
        error_message=str(exc) or type(exc).__name__,
    )


def _execute_monitoring_run(tier, trigger):
    run = create_run(trigger=trigger, tier=tier)
    run_id = run.key.id()
    results = []

    for definition in get_checks_for_tier(tier):
        try:
            alert_active = has_active_alert_for_check(definition["id"])
        except Exception:
            logger.exception(
                "Unable to read alert state for monitoring check %s", definition["id"]
            )
            alert_active = False
        try:
            execution = execute_check(definition)
        except Exception as exc:
            logger.exception("Monitoring check %s crashed", definition["id"])
            execution = _unexpected_execution(exc)

        try:
            result = create_check_result(
                run_id=run_id,
                check_id=definition["id"],
                check_name=definition["name"],
                target=get_check_target(definition),
                tier=definition["tier"],
                severity=definition["severity"],
                latency_threshold_ms=definition["latency_threshold_ms"],
                checked_at=execution.checked_at,
                response_time_ms=execution.response_time_ms,
                attempts=execution.attempts,
                status=execution.status,
                http_status_code=execution.http_status_code,
                error_type=execution.error_type,
                error_message=execution.error_message,
            )
        except Exception:
            logger.exception("Unable to persist monitoring check %s", definition["id"])
            continue
        try:
            if send_alert_transition(definition, result, alert_active):
                updated_result = update_check_result(result.key.id(), alert_sent=True)
                if updated_result:
                    result = updated_result
        except Exception:
            logger.exception(
                "Unable to update alert state for monitoring check %s",
                definition["id"],
            )
        results.append(result)

    finished_at = datetime.now(CHICAGO_TZ)
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("healthy", "degraded", "failed")
    }
    update_run(
        run_id,
        run_status="completed",
        end_time=finished_at,
        total=len(results),
        **counts,
    )

    try:
        update_snapshot(run_id)
    except Exception:
        logger.exception("Unable to update backend monitoring dashboard snapshot")

    if tier == "full":
        try:
            delete_old_monitoring_data(MONITORING_RETENTION_DAYS)
        except Exception:
            logger.exception("Unable to clean up expired backend monitoring data")

    return {
        "run_id": run_id,
        "trigger": trigger,
        "tier": tier,
        "run_status": "completed",
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": finished_at.isoformat(),
        "total": len(results),
        **counts,
    }


def run_monitoring(tier, trigger):
    """Run one suite while rejecting concurrent monitoring executions."""
    if tier not in MONITORING_TIERS:
        raise ValueError(f"Invalid monitoring tier: {tier}")
    if trigger not in MONITORING_TRIGGERS:
        raise ValueError(f"Invalid monitoring trigger: {trigger}")

    lease_owner = uuid4().hex
    if not acquire_monitoring_lease(
        lease_owner, lease_minutes=MONITORING_STUCK_RUN_MINUTES
    ):
        raise MonitoringRunInProgress("A monitoring run is already in progress")
    try:
        return _execute_monitoring_run(tier, trigger)
    finally:
        try:
            release_monitoring_lease(lease_owner)
        except Exception:
            logger.exception("Unable to release backend monitoring runner lease")
