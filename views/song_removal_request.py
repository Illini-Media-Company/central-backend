"""Authenticated JSON APIs for the WPGU song-removal workflow."""

from __future__ import annotations

from functools import wraps
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from constants import WPGU_SONG_REMOVAL_REVIEW_GROUPS
from db.employee_management import get_employee_card_by_email
from db.song_removal_request import SongRemovalRequestError
from util.slackbots.general import _lookup_user_id_by_email
from util.slackbots.song_removal_request import (
    post_report_to_slack,
    send_resolution_dm,
    send_submission_dm,
    sync_report_to_slack,
)
from util.song_removal_request import (
    claim_report,
    create_report,
    get_report,
    group_reports,
    options_payload,
    resolve_report,
    serialize_report,
    take_over_report,
)


logger = logging.getLogger(__name__)

song_removal_request_routes = Blueprint(
    "song_removal_request_routes",
    __name__,
    url_prefix="/wpgu-song-removal-requests/api",
)


def _error(code: str, message: str, status: int):
    return jsonify({"error": message, "code": code}), status


def _domain_error(exc: SongRemovalRequestError):
    return _error(exc.code, exc.message, exc.http_status)


@song_removal_request_routes.before_request
def require_api_login():
    """Keep this JSON API from inheriting the application's HTML login redirect."""

    if not current_user.is_authenticated:
        return _error(
            "authentication_required",
            "You must be logged in to access the song-removal API.",
            401,
        )


@song_removal_request_routes.errorhandler(403)
def api_forbidden(error):
    message = getattr(error, "description", None) or (
        "You do not have permission to perform this action."
    )
    return _error("forbidden", message, 403)


def reviewer_required(view):
    """Authorize reviewer routes while preserving the API's JSON error contract."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        groups = set(current_user.groups or [])
        if not groups.intersection(WPGU_SONG_REMOVAL_REVIEW_GROUPS):
            return _error(
                "forbidden",
                "This action is restricted to WPGU song-removal reviewers.",
                403,
            )
        return view(*args, **kwargs)

    return wrapped


def _employee_slack_id(email: str, *, allow_lookup: bool = False) -> str | None:
    employee = get_employee_card_by_email(email)
    if isinstance(employee, dict) and employee.get("slack_id"):
        return employee["slack_id"]
    if allow_lookup:
        try:
            return _lookup_user_id_by_email(email)
        except Exception:
            logger.exception("Failed to resolve Slack ID for %s", email)
    return None


def _reviewer_identity() -> dict[str, str | None]:
    return {
        "reviewer_name": current_user.name,
        "reviewer_email": current_user.email.lower(),
        "reviewer_slack_id": _employee_slack_id(current_user.email),
    }


def _safe_sync(report, *, allow_repost=False) -> dict:
    try:
        return sync_report_to_slack(report, allow_repost=allow_repost)
    except Exception as exc:
        logger.exception("Unexpected Slack synchronization failure")
        return {"ok": False, "error": str(exc)}


def _existing_sync_result(report) -> dict[str, bool]:
    """Describe saved Slack state without pretending an idempotent retry synced it."""

    return {"ok": bool(report.slack_ts) and not report.slack_error}


@song_removal_request_routes.route("/options", methods=["GET"])
@login_required
def options():
    return jsonify(options_payload()), 200


@song_removal_request_routes.route("/reports", methods=["POST"])
@login_required
def submit_report():
    try:
        payload = request.get_json(silent=True)
        slack_id = _employee_slack_id(current_user.email, allow_lookup=True)
        report = create_report(
            payload,
            submitter_name=current_user.name,
            submitter_email=current_user.email,
            submitter_slack_id=slack_id,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)

    slack_result = _safe_sync(report) if report.slack_ts else None
    if slack_result is None:
        try:
            slack_result = post_report_to_slack(report)
        except Exception as exc:
            logger.exception("Unexpected Slack post failure")
            slack_result = {"ok": False, "error": str(exc)}

    try:
        dm_result = send_submission_dm(report)
    except Exception as exc:
        logger.exception("Unexpected submitter DM failure")
        dm_result = {"ok": False, "error": str(exc)}

    refreshed = get_report(report.key.id())
    return (
        jsonify(
            {
                "message": "Song-removal report submitted.",
                "report": serialize_report(refreshed),
                "notifications": {
                    "slack_posted": bool(slack_result.get("ok")),
                    "submitter_dm_sent": bool(dm_result.get("ok")),
                },
            }
        ),
        201,
    )


@song_removal_request_routes.route("/reports", methods=["GET"])
@login_required
@reviewer_required
def list_reports():
    try:
        payload = group_reports(
            actor_email=current_user.email,
            status=request.args.get("status") or None,
            reason=request.args.get("reason") or None,
            query=request.args.get("q") or None,
        )
        return jsonify(payload), 200
    except SongRemovalRequestError as exc:
        return _domain_error(exc)


@song_removal_request_routes.route("/reports/<report_id>", methods=["GET"])
@login_required
@reviewer_required
def report_detail(report_id):
    try:
        report = get_report(report_id)
        return (
            jsonify(
                {"report": serialize_report(report, actor_email=current_user.email)}
            ),
            200,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)


@song_removal_request_routes.route("/reports/<report_id>/claim", methods=["POST"])
@login_required
@reviewer_required
def claim(report_id):
    try:
        report, changed = claim_report(report_id, **_reviewer_identity())
        slack_result = _safe_sync(report) if changed else _existing_sync_result(report)
        refreshed = get_report(report_id)
        return (
            jsonify(
                {
                    "message": "Song-removal report claimed.",
                    "changed": changed,
                    "slack_synced": bool(slack_result.get("ok")),
                    "report": serialize_report(
                        refreshed, actor_email=current_user.email
                    ),
                }
            ),
            200,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)


@song_removal_request_routes.route("/reports/<report_id>/take-over", methods=["POST"])
@login_required
@reviewer_required
def take_over(report_id):
    try:
        report, changed = take_over_report(report_id, **_reviewer_identity())
        slack_result = _safe_sync(report) if changed else _existing_sync_result(report)
        refreshed = get_report(report_id)
        return (
            jsonify(
                {
                    "message": "Song-removal report taken over.",
                    "changed": changed,
                    "slack_synced": bool(slack_result.get("ok")),
                    "report": serialize_report(
                        refreshed, actor_email=current_user.email
                    ),
                }
            ),
            200,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)


@song_removal_request_routes.route("/reports/<report_id>/resolve", methods=["POST"])
@login_required
@reviewer_required
def resolve(report_id):
    try:
        report, changed = resolve_report(
            report_id,
            request.get_json(silent=True),
            reviewer_email=current_user.email,
        )
        slack_result = _safe_sync(report) if changed else _existing_sync_result(report)
        if changed:
            try:
                dm_result = send_resolution_dm(report)
            except Exception as exc:
                logger.exception("Unexpected resolution DM failure")
                dm_result = {"ok": False, "error": str(exc)}
        else:
            dm_result = {
                "ok": bool(report.resolution_dm_sent_at),
                "already_sent": bool(report.resolution_dm_sent_at),
            }
        refreshed = get_report(report_id)
        return (
            jsonify(
                {
                    "message": "Song-removal report resolved.",
                    "changed": changed,
                    "slack_synced": bool(slack_result.get("ok")),
                    "submitter_dm_sent": bool(dm_result.get("ok")),
                    "report": serialize_report(
                        refreshed, actor_email=current_user.email
                    ),
                }
            ),
            200,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)


@song_removal_request_routes.route("/reports/<report_id>/retry-slack", methods=["POST"])
@login_required
@reviewer_required
def retry_slack(report_id):
    try:
        report = get_report(report_id)
        result = _safe_sync(report, allow_repost=True)
        if not result.get("ok"):
            return _error(
                "slack_sync_failed",
                "The report is saved, but Slack synchronization failed.",
                502,
            )
        refreshed = get_report(report_id)
        return (
            jsonify(
                {
                    "message": "Slack message synchronized.",
                    "report": serialize_report(
                        refreshed, actor_email=current_user.email
                    ),
                }
            ),
            200,
        )
    except SongRemovalRequestError as exc:
        return _domain_error(exc)
