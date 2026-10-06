"""Fail-open heartbeat recording and evaluation for App Engine cron routes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import make_response, request

from db.monitoring import (
    begin_cron_job,
    ensure_cron_job_heartbeat,
    finish_cron_job,
    get_cron_job_heartbeat,
)


logger = logging.getLogger(__name__)
CHICAGO_TZ = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class CronHealth:
    status: str
    error_type: str | None = None
    error_message: str | None = None


def _response_error(response):
    payload = response.get_json(silent=True)
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return f"Cron route returned HTTP {response.status_code}"


def track_cron_job(job_id, display_name):
    """Record genuine App Engine cron calls without affecting route behavior."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.headers.get("X-Appengine-Cron") != "true":
                return func(*args, **kwargs)

            execution_id = uuid4().hex
            tracking_started = False
            try:
                begin_cron_job(job_id, display_name, execution_id)
                tracking_started = True
            except Exception:
                logger.exception("Unable to start heartbeat for cron job %s", job_id)

            try:
                result = func(*args, **kwargs)
                response = make_response(result)
            except Exception as exc:
                if tracking_started:
                    try:
                        finish_cron_job(
                            job_id,
                            execution_id,
                            False,
                            http_status=500,
                            error_message=str(exc) or type(exc).__name__,
                        )
                    except Exception:
                        logger.exception(
                            "Unable to finish heartbeat for cron job %s", job_id
                        )
                raise

            if tracking_started:
                succeeded = 200 <= response.status_code < 300
                try:
                    finish_cron_job(
                        job_id,
                        execution_id,
                        succeeded,
                        http_status=response.status_code,
                        error_message=None if succeeded else _response_error(response),
                    )
                except Exception:
                    logger.exception(
                        "Unable to finish heartbeat for cron job %s", job_id
                    )
            return result

        return wrapper

    return decorator


def evaluate_cron_job(
    job_id,
    display_name,
    max_success_age_minutes,
    max_runtime_minutes,
    now=None,
):
    """Evaluate the latest heartbeat, including a first-deployment grace window."""
    now = now or datetime.now(CHICAGO_TZ)
    heartbeat = get_cron_job_heartbeat(job_id)
    if not heartbeat:
        heartbeat = ensure_cron_job_heartbeat(job_id, display_name, now=now)

    if not heartbeat.last_started_at:
        grace_ends = heartbeat.tracking_started_at + timedelta(
            minutes=max_success_age_minutes
        )
        if now <= grace_ends:
            return CronHealth(
                "degraded",
                "not_configured",
                "Scheduled job has not been observed yet",
            )
        return CronHealth(
            "failed",
            "stale",
            "Scheduled job has not run within its expected interval",
        )

    if heartbeat.last_status == "running":
        runtime = now - heartbeat.last_started_at
        if runtime > timedelta(minutes=max_runtime_minutes):
            return CronHealth(
                "failed",
                "stuck",
                f"Scheduled job has been running for {round(runtime.total_seconds() / 60)} minutes",
            )
        if not heartbeat.last_succeeded_at:
            return CronHealth("degraded", None, "Scheduled job is currently running")

    if heartbeat.last_status == "failed":
        return CronHealth(
            "failed",
            "job_failed",
            heartbeat.last_error or "Most recent scheduled execution failed",
        )

    if not heartbeat.last_succeeded_at:
        return CronHealth(
            "degraded", "not_configured", "No successful execution recorded yet"
        )

    age = now - heartbeat.last_succeeded_at
    if age > timedelta(minutes=max_success_age_minutes):
        return CronHealth(
            "failed",
            "stale",
            f"Last successful execution was {round(age.total_seconds() / 3600, 1)} hours ago",
        )

    if heartbeat.last_status == "running":
        return CronHealth("degraded", None, "Scheduled job is currently running")
    return CronHealth("healthy")
