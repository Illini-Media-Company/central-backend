"""Datastore model and persistence helpers for WPGU song-removal reports."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata

from google.cloud import ndb

from db import client


SONG_REMOVAL_REASONS = (
    "profanity_or_lyrics",
    "audio_defect",
    "inappropriate_content",
    "not_a_fit",
    "other",
)
SONG_REMOVAL_STATUSES = ("pending", "in_progress", "actioned", "no_action")
SONG_REMOVAL_FINAL_STATUSES = ("actioned", "no_action")


class SongRemovalRequestError(Exception):
    """Base error with an API-safe code and HTTP status."""

    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class SongRemovalRequestNotFound(SongRemovalRequestError):
    def __init__(self):
        super().__init__("report_not_found", "Song-removal report not found.", 404)


class SongRemovalTransitionConflict(SongRemovalRequestError):
    def __init__(self, message: str):
        super().__init__("invalid_status_transition", message, 409)


class SongRemovalOwnershipError(SongRemovalRequestError):
    def __init__(self):
        super().__init__(
            "report_not_owned",
            "Only the reviewer who claimed this report may resolve it.",
            403,
        )


def normalize_song_component(value: str | None) -> str:
    """Normalize user-entered song identity text without discarding punctuation."""

    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(
        str.maketrans({"\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-"})
    )
    return re.sub(r"\s+", " ", normalized).strip()


def build_song_key(song_name: str, artist_name: str, song_version: str | None) -> str:
    return "|".join(
        (
            normalize_song_component(song_name),
            normalize_song_component(artist_name),
            normalize_song_component(song_version),
        )
    )


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SongRemovalRequest(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    song_name = ndb.StringProperty(required=True)
    artist_name = ndb.StringProperty(required=True)
    song_version = ndb.StringProperty()
    song_key = ndb.StringProperty(required=True)

    reason = ndb.StringProperty(required=True, choices=SONG_REMOVAL_REASONS)
    details = ndb.TextProperty()

    submitter_name = ndb.StringProperty(required=True)
    submitter_email = ndb.StringProperty(required=True)
    submitter_slack_id = ndb.StringProperty()

    status = ndb.StringProperty(
        required=True, choices=SONG_REMOVAL_STATUSES, default="pending"
    )
    reviewer_name = ndb.StringProperty()
    reviewer_email = ndb.StringProperty()
    reviewer_slack_id = ndb.StringProperty()
    resolution_notes = ndb.TextProperty()

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    resolved_at = ndb.DateTimeProperty()

    slack_channel_id = ndb.StringProperty()
    slack_ts = ndb.StringProperty()
    slack_error = ndb.TextProperty()
    slack_synced_at = ndb.DateTimeProperty()

    confirmation_dm_sent_at = ndb.DateTimeProperty()
    resolution_dm_sent_at = ndb.DateTimeProperty()


def create_song_removal_request(
    *,
    song_name: str,
    artist_name: str,
    song_version: str | None,
    reason: str,
    details: str | None,
    submitter_name: str,
    submitter_email: str,
    submitter_slack_id: str | None,
) -> SongRemovalRequest:
    with client.context():
        report = SongRemovalRequest(
            song_name=song_name,
            artist_name=artist_name,
            song_version=song_version,
            song_key=build_song_key(song_name, artist_name, song_version),
            reason=reason,
            details=details,
            submitter_name=submitter_name,
            submitter_email=submitter_email.lower(),
            submitter_slack_id=submitter_slack_id,
        )
        report.put()
        return report


def get_song_removal_request(report_id: int | str) -> SongRemovalRequest | None:
    try:
        parsed_id = int(report_id)
    except (TypeError, ValueError):
        return None
    with client.context():
        return SongRemovalRequest.get_by_id(parsed_id)


def get_all_song_removal_requests() -> list[SongRemovalRequest]:
    with client.context():
        return SongRemovalRequest.query().order(-SongRemovalRequest.created_at).fetch()


def _apply_reviewer(report, *, name: str, email: str, slack_id: str | None) -> None:
    report.reviewer_name = name
    report.reviewer_email = email.lower()
    report.reviewer_slack_id = slack_id


def _apply_claim(
    report: SongRemovalRequest,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> bool:
    """Apply a claim and return whether the entity changed."""

    reviewer_email = reviewer_email.lower()
    if report.status == "pending":
        report.status = "in_progress"
        _apply_reviewer(
            report,
            name=reviewer_name,
            email=reviewer_email,
            slack_id=reviewer_slack_id,
        )
        return True
    if report.status == "in_progress" and report.reviewer_email == reviewer_email:
        return False
    raise SongRemovalTransitionConflict(
        "Only a pending report may be claimed. Use take-over for an in-progress report."
    )


def _apply_take_over(
    report: SongRemovalRequest,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> bool:
    reviewer_email = reviewer_email.lower()
    if report.status != "in_progress":
        raise SongRemovalTransitionConflict(
            "Only an in-progress report may be taken over."
        )
    if report.reviewer_email == reviewer_email:
        return False
    _apply_reviewer(
        report,
        name=reviewer_name,
        email=reviewer_email,
        slack_id=reviewer_slack_id,
    )
    return True


def _apply_resolution(
    report: SongRemovalRequest,
    *,
    status: str,
    resolution_notes: str,
    reviewer_email: str,
) -> bool:
    reviewer_email = reviewer_email.lower()
    if status not in SONG_REMOVAL_FINAL_STATUSES:
        raise SongRemovalTransitionConflict("Invalid final report status.")

    if report.status in SONG_REMOVAL_FINAL_STATUSES:
        if (
            report.status == status
            and report.reviewer_email == reviewer_email
            and report.resolution_notes == resolution_notes
        ):
            return False
        raise SongRemovalTransitionConflict(
            "Resolved reports are final and cannot be changed."
        )

    if report.status != "in_progress":
        raise SongRemovalTransitionConflict(
            "The report must be claimed before it can be resolved."
        )
    if report.reviewer_email != reviewer_email:
        raise SongRemovalOwnershipError()

    report.status = status
    report.resolution_notes = resolution_notes
    report.resolved_at = _utc_now_naive()
    return True


def _transactional_update(
    report_id: int | str, updater
) -> tuple[SongRemovalRequest, bool]:
    try:
        parsed_id = int(report_id)
    except (TypeError, ValueError) as exc:
        raise SongRemovalRequestNotFound() from exc

    with client.context():

        @ndb.transactional()
        def transaction():
            report = SongRemovalRequest.get_by_id(parsed_id)
            if not report:
                raise SongRemovalRequestNotFound()
            changed = updater(report)
            if changed:
                report.put()
            return report, changed

        return transaction()


def claim_song_removal_request(
    report_id: int | str,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> tuple[SongRemovalRequest, bool]:
    return _transactional_update(
        report_id,
        lambda report: _apply_claim(
            report,
            reviewer_name=reviewer_name,
            reviewer_email=reviewer_email,
            reviewer_slack_id=reviewer_slack_id,
        ),
    )


def take_over_song_removal_request(
    report_id: int | str,
    *,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_slack_id: str | None,
) -> tuple[SongRemovalRequest, bool]:
    return _transactional_update(
        report_id,
        lambda report: _apply_take_over(
            report,
            reviewer_name=reviewer_name,
            reviewer_email=reviewer_email,
            reviewer_slack_id=reviewer_slack_id,
        ),
    )


def resolve_song_removal_request(
    report_id: int | str,
    *,
    status: str,
    resolution_notes: str,
    reviewer_email: str,
) -> tuple[SongRemovalRequest, bool]:
    return _transactional_update(
        report_id,
        lambda report: _apply_resolution(
            report,
            status=status,
            resolution_notes=resolution_notes,
            reviewer_email=reviewer_email,
        ),
    )


def update_song_removal_slack_state(
    report_id: int | str,
    *,
    channel_id: str | None = None,
    message_ts: str | None = None,
    error: str | None = None,
    synced: bool = False,
) -> SongRemovalRequest:
    def updater(report):
        if channel_id is not None:
            report.slack_channel_id = channel_id
        if message_ts is not None:
            report.slack_ts = message_ts
        report.slack_error = error
        if synced:
            report.slack_synced_at = _utc_now_naive()
        return True

    report, _ = _transactional_update(report_id, updater)
    return report


def mark_song_removal_dm_sent(
    report_id: int | str, *, resolution: bool
) -> SongRemovalRequest:
    def updater(report):
        field = "resolution_dm_sent_at" if resolution else "confirmation_dm_sent_at"
        if getattr(report, field):
            return False
        setattr(report, field, _utc_now_naive())
        return True

    report, _ = _transactional_update(report_id, updater)
    return report
