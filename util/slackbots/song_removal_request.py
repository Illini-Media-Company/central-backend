"""Slack notifications and interactive review for WPGU song-removal reports."""

from __future__ import annotations

import json
import logging
from threading import Thread
from typing import Any

from constants import (
    SLACK_BOT_TOKEN,
    WPGU_SONG_REMOVAL_REQUESTS_ID,
    WPGU_SONG_REMOVAL_REVIEW_GROUPS,
)
from db.song_removal_request import (
    SongRemovalRequest,
    SongRemovalRequestError,
    mark_song_removal_dm_sent,
    update_song_removal_slack_state,
)
from db.user import get_user
from util.slackbots._slackbot import app
from util.slackbots.general import (
    dm_channel_by_id,
    dm_user_by_email,
    update_message_blocks,
)
from util.song_removal_request import (
    REASON_LABELS,
    STATUS_LABELS,
    claim_report,
    get_report,
    resolve_report,
    take_over_report,
)


logger = logging.getLogger(__name__)


def _plain(text: str) -> dict[str, Any]:
    return {"type": "plain_text", "text": text, "emoji": True}


def build_song_removal_blocks(report: SongRemovalRequest) -> list[dict[str, Any]]:
    """Build blocks with employee-entered content confined to plain-text fields."""

    song_fields = [
        {"type": "plain_text", "text": f"Song\n{report.song_name}", "emoji": True},
        {
            "type": "plain_text",
            "text": f"Artist\n{report.artist_name}",
            "emoji": True,
        },
    ]
    if report.song_version:
        song_fields.append(
            {
                "type": "plain_text",
                "text": f"Version\n{report.song_version}",
                "emoji": True,
            }
        )

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": _plain(":wpgu: New Song Removal Report"),
        },
        {"type": "section", "fields": song_fields},
        {
            "type": "section",
            "fields": [
                {
                    "type": "plain_text",
                    "text": f"Reason\n{REASON_LABELS[report.reason]}",
                    "emoji": True,
                },
                {
                    "type": "plain_text",
                    "text": (
                        f"Submitted by\n{report.submitter_name} "
                        f"({report.submitter_email})"
                    ),
                    "emoji": True,
                },
            ],
        },
    ]
    if report.details:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": f"Details\n{report.details}",
                    "emoji": True,
                },
            }
        )

    status_text = f"Status: {STATUS_LABELS[report.status]}"
    if report.reviewer_name:
        status_text += f" — {report.reviewer_name}"
    blocks.extend(
        [
            {"type": "divider"},
            {
                "type": "context",
                "elements": [{"type": "plain_text", "text": status_text}],
            },
        ]
    )
    if report.resolution_notes:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": f"Resolution notes\n{report.resolution_notes}",
                    "emoji": True,
                },
            }
        )

    report_id = str(report.key.id()) if report.key else ""
    if report_id and report.status == "pending":
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": _plain("Claim"),
                        "action_id": "song_removal_claim",
                        "value": report_id,
                        "style": "primary",
                    }
                ],
            }
        )
    elif report_id and report.status == "in_progress":
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": _plain("Actioned"),
                        "action_id": "song_removal_actioned",
                        "value": report_id,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": _plain("No Action"),
                        "action_id": "song_removal_no_action",
                        "value": report_id,
                    },
                    {
                        "type": "button",
                        "text": _plain("Take Over"),
                        "action_id": "song_removal_take_over",
                        "value": report_id,
                    },
                ],
            }
        )
    return blocks


def _fallback_text(report: SongRemovalRequest) -> str:
    # Keep user-entered text out of Slack's mrkdwn-parsed fallback field so a
    # title such as <!channel> cannot trigger mentions. Full details remain in
    # plain-text Block Kit elements.
    return f"WPGU song removal report — {STATUS_LABELS[report.status]}"


def post_report_to_slack(report: SongRemovalRequest) -> dict[str, Any]:
    if not WPGU_SONG_REMOVAL_REQUESTS_ID:
        error = "WPGU_SONG_REMOVAL_REQUESTS_ID is not configured"
        update_song_removal_slack_state(report.key.id(), error=error)
        logger.error(error)
        return {"ok": False, "error": error}

    result = dm_channel_by_id(
        channel_id=WPGU_SONG_REMOVAL_REQUESTS_ID,
        text=_fallback_text(report),
        blocks=build_song_removal_blocks(report),
    )
    if result.get("ok"):
        update_song_removal_slack_state(
            report.key.id(),
            channel_id=result.get("channel"),
            message_ts=result.get("ts"),
            error=None,
            synced=True,
        )
    else:
        update_song_removal_slack_state(
            report.key.id(), error=str(result.get("error") or "unknown Slack error")
        )
    return result


def sync_report_to_slack(
    report: SongRemovalRequest, *, allow_repost: bool = False
) -> dict[str, Any]:
    channel_id = report.slack_channel_id or WPGU_SONG_REMOVAL_REQUESTS_ID
    if not channel_id:
        error = "WPGU_SONG_REMOVAL_REQUESTS_ID is not configured"
        update_song_removal_slack_state(report.key.id(), error=error)
        return {"ok": False, "error": error}

    if not report.slack_ts:
        return post_report_to_slack(report)

    result = update_message_blocks(
        channel=channel_id,
        ts=report.slack_ts,
        new_blocks=build_song_removal_blocks(report),
        text=_fallback_text(report),
    )
    if not result.get("ok") and allow_repost:
        error = str(result.get("error") or "")
        if "message_not_found" in error:
            return post_report_to_slack(report)

    if result.get("ok"):
        update_song_removal_slack_state(
            report.key.id(),
            channel_id=result.get("channel") or channel_id,
            message_ts=result.get("ts") or report.slack_ts,
            error=None,
            synced=True,
        )
    else:
        update_song_removal_slack_state(
            report.key.id(), error=str(result.get("error") or "unknown Slack error")
        )
    return result


def send_submission_dm(report: SongRemovalRequest) -> dict[str, Any]:
    if report.confirmation_dm_sent_at:
        return {"ok": True, "already_sent": True}
    text = (
        f'Your report for "{report.song_name}" by "{report.artist_name}" '
        "was submitted to the WPGU music team."
    )
    result = (
        dm_channel_by_id(channel_id=report.submitter_slack_id, text=text)
        if report.submitter_slack_id
        else dm_user_by_email(email=report.submitter_email, text=text)
    )
    if result.get("ok"):
        mark_song_removal_dm_sent(report.key.id(), resolution=False)
    return result


def send_resolution_dm(report: SongRemovalRequest) -> dict[str, Any]:
    if report.resolution_dm_sent_at:
        return {"ok": True, "already_sent": True}
    text = (
        f'Your report for "{report.song_name}" by "{report.artist_name}" was '
        f"resolved as {STATUS_LABELS[report.status]}.\n"
        f"Resolution: {report.resolution_notes}"
    )
    result = (
        dm_channel_by_id(channel_id=report.submitter_slack_id, text=text)
        if report.submitter_slack_id
        else dm_user_by_email(email=report.submitter_email, text=text)
    )
    if result.get("ok"):
        mark_song_removal_dm_sent(report.key.id(), resolution=True)
    return result


def _slack_actor(user_id: str) -> dict[str, str] | None:
    try:
        response = app.client.users_info(token=SLACK_BOT_TOKEN, user=user_id)
        slack_user = response.get("user") or {}
        profile = slack_user.get("profile") or {}
        email = (profile.get("email") or "").strip().lower()
        if not email:
            return None
        user = get_user(email)
        if not user or not set(user.groups or []) & set(
            WPGU_SONG_REMOVAL_REVIEW_GROUPS
        ):
            return None
        return {
            "name": profile.get("real_name") or slack_user.get("real_name") or email,
            "email": email,
            "slack_id": user_id,
        }
    except Exception:
        logger.exception("Failed to resolve or authorize Slack reviewer %s", user_id)
        return None


def _ephemeral(channel_id: str | None, user_id: str | None, text: str) -> None:
    if not channel_id or not user_id:
        return
    try:
        app.client.chat_postEphemeral(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            user=user_id,
            text=text,
        )
    except Exception:
        logger.exception("Failed to post song-removal ephemeral response")


def _action_context(body: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    user_id = (body.get("user") or {}).get("id")
    channel_id = (body.get("container") or {}).get("channel_id")
    action = (body.get("actions") or [{}])[0]
    return user_id, channel_id, action.get("value")


def _process_claim(body: dict[str, Any]) -> None:
    user_id, channel_id, report_id = _action_context(body)
    actor = _slack_actor(user_id) if user_id else None
    if not actor:
        _ephemeral(channel_id, user_id, "You are not authorized to review this report.")
        return
    try:
        report, changed = claim_report(
            report_id,
            reviewer_name=actor["name"],
            reviewer_email=actor["email"],
            reviewer_slack_id=actor["slack_id"],
        )
        if changed:
            sync_report_to_slack(report)
        _ephemeral(channel_id, user_id, "You claimed this song-removal report.")
    except SongRemovalRequestError as exc:
        _ephemeral(channel_id, user_id, exc.message)
    except Exception:
        logger.exception("Failed to claim song-removal report %s", report_id)
        _ephemeral(channel_id, user_id, "Unable to claim this report right now.")


def _process_take_over(body: dict[str, Any]) -> None:
    user_id, channel_id, report_id = _action_context(body)
    actor = _slack_actor(user_id) if user_id else None
    if not actor:
        _ephemeral(channel_id, user_id, "You are not authorized to review this report.")
        return
    try:
        report, changed = take_over_report(
            report_id,
            reviewer_name=actor["name"],
            reviewer_email=actor["email"],
            reviewer_slack_id=actor["slack_id"],
        )
        if changed:
            sync_report_to_slack(report)
        _ephemeral(channel_id, user_id, "You took over this song-removal report.")
    except SongRemovalRequestError as exc:
        _ephemeral(channel_id, user_id, exc.message)
    except Exception:
        logger.exception("Failed to take over song-removal report %s", report_id)
        _ephemeral(channel_id, user_id, "Unable to take over this report right now.")


@app.action("song_removal_claim")
def handle_song_removal_claim(ack, body):
    ack()
    Thread(target=_process_claim, args=(body,), daemon=True).start()


@app.action("song_removal_take_over")
def handle_song_removal_take_over(ack, body):
    ack()
    Thread(target=_process_take_over, args=(body,), daemon=True).start()


def _open_resolution_modal(ack, body, target_status: str) -> None:
    ack()
    user_id, channel_id, report_id = _action_context(body)
    actor = _slack_actor(user_id) if user_id else None
    if not actor:
        _ephemeral(channel_id, user_id, "You are not authorized to review this report.")
        return
    try:
        report = get_report(report_id)
        if report.status != "in_progress":
            _ephemeral(channel_id, user_id, "This report is no longer in progress.")
            return
        if report.reviewer_email != actor["email"]:
            _ephemeral(
                channel_id,
                user_id,
                "Only the current reviewer may resolve this report. Take it over first.",
            )
            return
        app.client.views_open(
            token=SLACK_BOT_TOKEN,
            trigger_id=body.get("trigger_id"),
            view={
                "type": "modal",
                "callback_id": "song_removal_resolution_modal",
                "private_metadata": json.dumps(
                    {
                        "report_id": str(report_id),
                        "status": target_status,
                        "channel_id": channel_id,
                    }
                ),
                "title": _plain("Resolve Song Report"),
                "submit": _plain("Save"),
                "close": _plain("Cancel"),
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "resolution_notes_block",
                        "label": _plain("Resolution notes"),
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "resolution_notes",
                            "multiline": True,
                            "max_length": 2000,
                        },
                    }
                ],
            },
        )
    except SongRemovalRequestError as exc:
        _ephemeral(channel_id, user_id, exc.message)
    except Exception:
        logger.exception("Failed to open song-removal resolution modal")
        _ephemeral(channel_id, user_id, "Unable to open the resolution form.")


@app.action("song_removal_actioned")
def handle_song_removal_actioned(ack, body):
    _open_resolution_modal(ack, body, "actioned")


@app.action("song_removal_no_action")
def handle_song_removal_no_action(ack, body):
    _open_resolution_modal(ack, body, "no_action")


def _process_resolution(body: dict[str, Any], metadata: dict[str, Any], notes: str):
    user_id = (body.get("user") or {}).get("id")
    channel_id = metadata.get("channel_id")
    actor = _slack_actor(user_id) if user_id else None
    if not actor:
        _ephemeral(channel_id, user_id, "You are not authorized to review this report.")
        return
    try:
        report, changed = resolve_report(
            metadata.get("report_id"),
            {"status": metadata.get("status"), "resolution_notes": notes},
            reviewer_email=actor["email"],
        )
        if changed:
            sync_report_to_slack(report)
            send_resolution_dm(report)
        _ephemeral(channel_id, user_id, "The song-removal report was resolved.")
    except SongRemovalRequestError as exc:
        _ephemeral(channel_id, user_id, exc.message)
    except Exception:
        logger.exception(
            "Failed to resolve song-removal report %s", metadata.get("report_id")
        )
        _ephemeral(channel_id, user_id, "Unable to resolve this report right now.")


@app.view("song_removal_resolution_modal")
def handle_song_removal_resolution_modal(ack, body):
    values = ((body.get("view") or {}).get("state") or {}).get("values") or {}
    notes = (
        values.get("resolution_notes_block", {})
        .get("resolution_notes", {})
        .get("value")
        or ""
    ).strip()
    if not notes:
        ack(
            response_action="errors",
            errors={"resolution_notes_block": "Resolution notes are required."},
        )
        return
    if len(notes) > 2000:
        ack(
            response_action="errors",
            errors={"resolution_notes_block": "Use 2,000 characters or fewer."},
        )
        return
    try:
        metadata = json.loads((body.get("view") or {}).get("private_metadata") or "{}")
    except json.JSONDecodeError:
        ack()
        return
    ack()
    Thread(
        target=_process_resolution,
        args=(body, metadata, notes),
        daemon=True,
    ).start()


__all__ = [
    "build_song_removal_blocks",
    "post_report_to_slack",
    "send_resolution_dm",
    "send_submission_dm",
    "sync_report_to_slack",
]
