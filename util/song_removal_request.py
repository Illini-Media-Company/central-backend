"""Shared validation, serialization, and workflow for song-removal reports."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from db.song_removal_request import (
    SONG_REMOVAL_FINAL_STATUSES,
    SONG_REMOVAL_REASONS,
    SONG_REMOVAL_STATUSES,
    SongRemovalRequest,
    SongRemovalRequestError,
    build_song_key,
    claim_song_removal_request,
    create_song_removal_request,
    get_all_song_removal_requests,
    get_song_removal_request,
    resolve_song_removal_request,
    take_over_song_removal_request,
)


SONG_NAME_MAX_LENGTH = 200
ARTIST_NAME_MAX_LENGTH = 200
SONG_VERSION_MAX_LENGTH = 100
DETAILS_MAX_LENGTH = 2000
RESOLUTION_NOTES_MAX_LENGTH = 2000
SEARCH_QUERY_MAX_LENGTH = 200

REASON_LABELS = {
    "profanity_or_lyrics": "Profanity or lyric content",
    "audio_defect": "Audio defect",
    "inappropriate_content": "Inappropriate content",
    "not_a_fit": "Not a fit",
    "other": "Other",
}
STATUS_LABELS = {
    "pending": "Pending",
    "in_progress": "In Progress",
    "actioned": "Actioned",
    "no_action": "No Action",
}


class SongRemovalValidationError(SongRemovalRequestError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, 400)


def _clean_string(
    data: dict[str, Any],
    field: str,
    *,
    required: bool,
    max_length: int,
) -> str | None:
    value = data.get(field)
    if value is None:
        if required:
            raise SongRemovalValidationError(
                f"missing_{field}", f"{field.replace('_', ' ').title()} is required."
            )
        return None
    if not isinstance(value, str):
        raise SongRemovalValidationError(
            f"invalid_{field}", f"{field.replace('_', ' ').title()} must be text."
        )
    value = value.strip()
    if required and not value:
        raise SongRemovalValidationError(
            f"missing_{field}", f"{field.replace('_', ' ').title()} is required."
        )
    if not value:
        return None
    if len(value) > max_length:
        raise SongRemovalValidationError(
            f"{field}_too_long",
            f"{field.replace('_', ' ').title()} must be {max_length} characters or fewer.",
        )
    return value


def validate_submission(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SongRemovalValidationError(
            "invalid_request_body", "Request body must be a JSON object."
        )

    song_name = _clean_string(
        data, "song_name", required=True, max_length=SONG_NAME_MAX_LENGTH
    )
    artist_name = _clean_string(
        data, "artist_name", required=True, max_length=ARTIST_NAME_MAX_LENGTH
    )
    song_version = _clean_string(
        data, "song_version", required=False, max_length=SONG_VERSION_MAX_LENGTH
    )
    details = _clean_string(
        data, "details", required=False, max_length=DETAILS_MAX_LENGTH
    )

    reason = data.get("reason")
    if not isinstance(reason, str) or reason not in SONG_REMOVAL_REASONS:
        raise SongRemovalValidationError(
            "invalid_reason", "Reason must be one of the supported reason values."
        )
    if reason == "other" and not details:
        raise SongRemovalValidationError(
            "details_required", "Details are required when the reason is Other."
        )

    return {
        "song_name": song_name,
        "artist_name": artist_name,
        "song_version": song_version,
        "reason": reason,
        "details": details,
    }


def validate_resolution(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        raise SongRemovalValidationError(
            "invalid_request_body", "Request body must be a JSON object."
        )
    status = data.get("status")
    if status not in SONG_REMOVAL_FINAL_STATUSES:
        raise SongRemovalValidationError(
            "invalid_resolution_status", "Status must be actioned or no_action."
        )
    notes = _clean_string(
        data,
        "resolution_notes",
        required=True,
        max_length=RESOLUTION_NOTES_MAX_LENGTH,
    )
    return {"status": status, "resolution_notes": notes}


def create_report(
    data: Any,
    *,
    submitter_name: str,
    submitter_email: str,
    submitter_slack_id: str | None,
) -> SongRemovalRequest:
    clean = validate_submission(data)
    return create_song_removal_request(
        **clean,
        submitter_name=submitter_name,
        submitter_email=submitter_email,
        submitter_slack_id=submitter_slack_id,
    )


def claim_report(
    report_id: int | str,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> tuple[SongRemovalRequest, bool]:
    return claim_song_removal_request(
        report_id,
        reviewer_name=reviewer_name,
        reviewer_email=reviewer_email,
        reviewer_slack_id=reviewer_slack_id,
    )


def take_over_report(
    report_id: int | str,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> tuple[SongRemovalRequest, bool]:
    return take_over_song_removal_request(
        report_id,
        reviewer_name=reviewer_name,
        reviewer_email=reviewer_email,
        reviewer_slack_id=reviewer_slack_id,
    )


def resolve_report(
    report_id: int | str,
    data: Any,
    *,
    reviewer_email: str,
) -> tuple[SongRemovalRequest, bool]:
    clean = validate_resolution(data)
    return resolve_song_removal_request(
        report_id,
        reviewer_email=reviewer_email,
        **clean,
    )


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def available_actions(report: SongRemovalRequest, actor_email: str | None) -> list[str]:
    # Actions are only meaningful for an authenticated reviewer.  In particular,
    # do not expose reviewer controls in the response returned to a submitter.
    if not actor_email:
        return []

    actions: list[str] = []
    actor_email = actor_email.lower()
    if report.status == "pending":
        actions.append("claim")
    elif report.status == "in_progress":
        if actor_email and report.reviewer_email == actor_email:
            actions.append("resolve")
        else:
            actions.append("take_over")
    if report.slack_error or not report.slack_ts:
        actions.append("retry_slack")
    return actions


def serialize_report(
    report: SongRemovalRequest, *, actor_email: str | None = None
) -> dict[str, Any]:
    return {
        "uid": report.key.id() if report.key else None,
        "song_name": report.song_name,
        "artist_name": report.artist_name,
        "song_version": report.song_version,
        "song_key": report.song_key,
        "reason": report.reason,
        "reason_label": REASON_LABELS[report.reason],
        "details": report.details,
        "submitter_name": report.submitter_name,
        "submitter_email": report.submitter_email,
        "submitter_slack_id": report.submitter_slack_id,
        "status": report.status,
        "status_label": STATUS_LABELS[report.status],
        "reviewer_name": report.reviewer_name,
        "reviewer_email": report.reviewer_email,
        "reviewer_slack_id": report.reviewer_slack_id,
        "resolution_notes": report.resolution_notes,
        "created_at": _iso_utc(report.created_at),
        "updated_at": _iso_utc(report.updated_at),
        "resolved_at": _iso_utc(report.resolved_at),
        "slack_channel_id": report.slack_channel_id,
        "slack_ts": report.slack_ts,
        "slack_error": report.slack_error,
        "slack_synced_at": _iso_utc(report.slack_synced_at),
        "available_actions": available_actions(report, actor_email),
    }


def get_report(report_id: int | str) -> SongRemovalRequest:
    report = get_song_removal_request(report_id)
    if not report:
        from db.song_removal_request import SongRemovalRequestNotFound

        raise SongRemovalRequestNotFound()
    return report


def group_reports(
    *,
    actor_email: str,
    status: str | None = None,
    reason: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    if status is not None and status not in SONG_REMOVAL_STATUSES:
        raise SongRemovalValidationError(
            "invalid_status_filter", "Unsupported status filter."
        )
    if reason is not None and reason not in SONG_REMOVAL_REASONS:
        raise SongRemovalValidationError(
            "invalid_reason_filter", "Unsupported reason filter."
        )
    if query is not None:
        if not isinstance(query, str):
            raise SongRemovalValidationError(
                "invalid_search_query", "Search query must be text."
            )
        query = query.strip().casefold()
        if len(query) > SEARCH_QUERY_MAX_LENGTH:
            raise SongRemovalValidationError(
                "search_query_too_long",
                f"Search query must be {SEARCH_QUERY_MAX_LENGTH} characters or fewer.",
            )

    all_reports = get_all_song_removal_requests()
    totals = Counter(report.song_key for report in all_reports)
    matching: list[SongRemovalRequest] = []
    for report in all_reports:
        if status and report.status != status:
            continue
        if reason and report.reason != reason:
            continue
        if query:
            haystack = " ".join(
                filter(
                    None,
                    (
                        report.song_name,
                        report.artist_name,
                        report.song_version,
                        report.details,
                    ),
                )
            ).casefold()
            if query not in haystack:
                continue
        matching.append(report)

    grouped: dict[str, list[SongRemovalRequest]] = {}
    for report in matching:
        grouped.setdefault(report.song_key, []).append(report)

    groups = []
    for song_key, reports in grouped.items():
        reports.sort(key=lambda item: item.created_at or datetime.min, reverse=True)
        newest = reports[0]
        groups.append(
            {
                "song_key": song_key,
                "song_name": newest.song_name,
                "artist_name": newest.artist_name,
                "song_version": newest.song_version,
                "report_count": totals[song_key],
                "matching_report_count": len(reports),
                "reports": [
                    serialize_report(report, actor_email=actor_email)
                    for report in reports
                ],
                "_sort_created_at": newest.created_at or datetime.min,
            }
        )
    groups.sort(key=lambda group: group["_sort_created_at"], reverse=True)
    for group in groups:
        group.pop("_sort_created_at", None)

    return {
        "groups": groups,
        "total_groups": len(groups),
        "matching_report_count": len(matching),
        "total_report_count": len(all_reports),
        "filters": {"status": status, "reason": reason, "q": query or None},
    }


def options_payload() -> dict[str, Any]:
    return {
        "reasons": [
            {"value": reason, "label": REASON_LABELS[reason]}
            for reason in SONG_REMOVAL_REASONS
        ],
        "statuses": [
            {"value": status, "label": STATUS_LABELS[status]}
            for status in SONG_REMOVAL_STATUSES
        ],
        "limits": {
            "song_name": SONG_NAME_MAX_LENGTH,
            "artist_name": ARTIST_NAME_MAX_LENGTH,
            "song_version": SONG_VERSION_MAX_LENGTH,
            "details": DETAILS_MAX_LENGTH,
            "resolution_notes": RESOLUTION_NOTES_MAX_LENGTH,
            "search_query": SEARCH_QUERY_MAX_LENGTH,
        },
    }


__all__ = [
    "SongRemovalRequestError",
    "SongRemovalValidationError",
    "build_song_key",
    "claim_report",
    "create_report",
    "get_report",
    "group_reports",
    "options_payload",
    "resolve_report",
    "serialize_report",
    "take_over_report",
]
