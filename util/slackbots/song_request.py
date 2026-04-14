"""
WPGU Song Request Slackbot handlers.
Provides Claim / Approve / Deny buttons directly in the #wpgu_song-requests channel.
"""

import json
from threading import Thread

from constants import SLACK_BOT_TOKEN, WPGU_SONG_REQUESTS_ID
from util.slackbots._slackbot import app
from util.slackbots.general import dm_channel_by_id, dm_user_by_email
from db.song_request import update_request_status, get_song_request_by_id


def build_song_request_blocks(
    *,
    song_name: str,
    artist_name: str,
    submitter_mention: str,
    status: str = "pending",
    reviewer_name: str = None,
    rejection_reason: str = None,
    request_id=None,
) -> list:
    """Build Slack Block Kit blocks for a song request message."""

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":wpgu: New Song Request",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Song:*\n{song_name}"},
                {"type": "mrkdwn", "text": f"*Artist:*\n{artist_name}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Submitted by:* {submitter_mention}"},
        },
        {"type": "divider"},
    ]

    # Status context footer
    status_label = status.replace("_", " ").title()
    status_text = f"*Status:* {status_label}"
    if reviewer_name:
        status_text += f" by {reviewer_name}"
    if rejection_reason:
        status_text += f"\n*Reason:* {rejection_reason}"

    blocks.append(
        {"type": "context", "elements": [{"type": "mrkdwn", "text": status_text}]}
    )

    # Action buttons — shown while actionable
    if request_id and status == "pending":
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Claim", "emoji": True},
                        "action_id": "song_request_claim",
                        "value": json.dumps({"request_id": str(request_id)}),
                        "style": "primary",
                    },
                ],
            }
        )
    elif request_id and status == "in_progress":
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve",
                            "emoji": True,
                        },
                        "action_id": "song_request_approve",
                        "value": json.dumps({"request_id": str(request_id)}),
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Deny", "emoji": True},
                        "action_id": "song_request_deny",
                        "value": json.dumps({"request_id": str(request_id)}),
                        "style": "danger",
                    },
                ],
            }
        )

    return blocks


def post_song_request_to_slack(
    *,
    song_name: str,
    artist_name: str,
    submitter_slack_id: str,
    submitter_email: str,
    request_id,
) -> dict:
    """Post a new song request to the channel with interactive buttons."""

    if submitter_slack_id:
        submitter_mention = f"<@{submitter_slack_id}>"
    else:
        submitter_mention = submitter_email or "an anonymous listener"

    blocks = build_song_request_blocks(
        song_name=song_name,
        artist_name=artist_name,
        submitter_mention=submitter_mention,
        status="pending",
        request_id=request_id,
    )

    try:
        app.client.conversations_join(
            token=SLACK_BOT_TOKEN, channel=WPGU_SONG_REQUESTS_ID
        )
    except Exception:
        pass  # Already in channel or can't join — proceed anyway

    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=WPGU_SONG_REQUESTS_ID,
            text=f'New song request: "{song_name}" by "{artist_name}"',
            blocks=blocks,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[song_request] post_song_request_to_slack failed: {e}")
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Helper: resolve reviewer name from Slack user_id
# ---------------------------------------------------------------------------


def _get_reviewer_name(user_id: str) -> str:
    try:
        info = app.client.users_info(token=SLACK_BOT_TOKEN, user=user_id)
        return info.get("user", {}).get("real_name") or f"<@{user_id}>"
    except Exception:
        return f"<@{user_id}>"


def update_song_request_message(
    *,
    updated,
    message_ts,
    status,
    reviewer_name,
    channel_id=WPGU_SONG_REQUESTS_ID,
    rejection_reason=None,
    request_id=None,
):
    """Rebuild and push the full Slack message for a song request status change."""
    if not (channel_id and message_ts):
        return

    submitter_mention = (
        f"<@{updated.submitter_slack_id}>"
        if updated.submitter_slack_id
        else (updated.submitter_email or "an anonymous listener")
    )
    new_blocks = build_song_request_blocks(
        song_name=updated.song_name,
        artist_name=updated.artist_name,
        submitter_mention=submitter_mention,
        status=status,
        reviewer_name=reviewer_name,
        rejection_reason=rejection_reason,
        request_id=request_id,
    )
    try:
        app.client.chat_update(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            ts=message_ts,
            blocks=new_blocks,
            text=f'Song request "{updated.song_name}" — {status.replace("_", " ")}',
        )
    except Exception as e:
        print(f"[song_request] chat_update failed: {e}")


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


@app.action("song_request_claim")
def handle_song_request_claim(ack, body, logger):
    ack()
    Thread(target=_do_claim, args=(body, logger)).start()


def _do_claim(body, logger):
    try:
        user_id = (body.get("user") or {}).get("id")
        channel_id = (body.get("container") or {}).get("channel_id")
        message_ts = (body.get("container") or {}).get("message_ts")

        act = (body.get("actions") or [{}])[0]
        request_id = json.loads(act.get("value", "{}")).get("request_id")
        if not request_id:
            return

        reviewer_name = _get_reviewer_name(user_id)
        updated = update_request_status(
            request_id, "in_progress", reviewer_name=reviewer_name
        )
        if not updated:
            return

        update_song_request_message(
            status="in_progress",
            reviewer_name=reviewer_name,
            updated=updated,
            message_ts=message_ts,
            channel_id=channel_id,
            request_id=request_id,
        )

        app.client.chat_postEphemeral(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            user=user_id,
            text=f'✅ You claimed "*{updated.song_name}*" by "*{updated.artist_name}*". Use Approve or Deny when ready.',
        )

    except Exception as e:
        logger.error(f"[song_request_claim] error: {e}")


@app.action("song_request_approve")
def handle_song_request_approve(ack, body, logger):
    ack()
    Thread(target=_do_approve, args=(body, logger)).start()


def _do_approve(body, logger):
    try:
        user_id = (body.get("user") or {}).get("id")
        channel_id = (body.get("container") or {}).get("channel_id")
        message_ts = (body.get("container") or {}).get("message_ts")

        act = (body.get("actions") or [{}])[0]
        request_id = json.loads(act.get("value", "{}")).get("request_id")
        if not request_id:
            return

        reviewer_name = _get_reviewer_name(user_id)
        updated = update_request_status(
            request_id, "accepted", reviewer_name=reviewer_name
        )
        if not updated:
            return

        update_song_request_message(
            status="accepted",
            reviewer_name=reviewer_name,
            updated=updated,
            message_ts=message_ts,
            channel_id=channel_id,
        )

        # DM submitter
        if updated.is_imc_employee:
            msg = f'✅ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" has been approved!'
            if updated.submitter_slack_id:
                dm_channel_by_id(channel_id=updated.submitter_slack_id, text=msg)
            elif updated.submitter_email:
                dm_user_by_email(email=updated.submitter_email, text=msg)

    except Exception as e:
        logger.error(f"[song_request_approve] error: {e}")


@app.action("song_request_deny")
def handle_song_request_deny(ack, body, logger):
    """Opens a modal to collect an optional denial reason."""
    ack()
    # Modal open is fast — no thread needed, must happen before trigger_id expires
    try:
        trigger_id = body.get("trigger_id")
        act = (body.get("actions") or [{}])[0]
        request_id = json.loads(act.get("value", "{}")).get("request_id")
        channel_id = (body.get("container") or {}).get("channel_id")
        message_ts = (body.get("container") or {}).get("message_ts")

        app.client.views_open(
            token=SLACK_BOT_TOKEN,
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "song_request_deny_modal",
                "private_metadata": json.dumps(
                    {
                        "request_id": request_id,
                        "channel_id": channel_id,
                        "message_ts": message_ts,
                    }
                ),
                "title": {"type": "plain_text", "text": "Deny Song Request"},
                "submit": {"type": "plain_text", "text": "Deny"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "reason_block",
                        "optional": True,
                        "label": {"type": "plain_text", "text": "Reason (optional)"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "reason_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Enter a reason for denial...",
                            },
                        },
                    }
                ],
            },
        )
    except Exception as e:
        logger.error(f"[song_request_deny] error: {e}")


@app.view("song_request_deny_modal")
def handle_deny_modal_submission(ack, body, logger):
    ack()
    Thread(target=_do_deny, args=(body, logger)).start()


def _do_deny(body, logger):
    try:
        user_id = (body.get("user") or {}).get("id")
        meta = json.loads(body["view"].get("private_metadata", "{}"))
        request_id = meta.get("request_id")
        channel_id = meta.get("channel_id")
        message_ts = meta.get("message_ts")

        values = body["view"]["state"]["values"]
        rejection_reason = (
            values.get("reason_block", {}).get("reason_input", {}).get("value") or None
        )

        reviewer_name = _get_reviewer_name(user_id)
        updated = update_request_status(
            request_id,
            "declined",
            reviewer_name=reviewer_name,
            rejection_reason=rejection_reason,
        )
        if not updated:
            return

        update_song_request_message(
            status="declined",
            reviewer_name=reviewer_name,
            updated=updated,
            message_ts=message_ts,
            channel_id=channel_id,
            rejection_reason=rejection_reason,
        )

        # DM submitter
        reason_text = f"\n*Reason:* {rejection_reason}" if rejection_reason else ""
        if updated.is_imc_employee:
            msg = f'❌ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" was not approved.{reason_text}'
            if updated.submitter_slack_id:
                dm_channel_by_id(channel_id=updated.submitter_slack_id, text=msg)
            elif updated.submitter_email:
                dm_user_by_email(email=updated.submitter_email, text=msg)

    except Exception as e:
        logger.error(f"[song_request_deny_modal] error: {e}")
