from __future__ import annotations
import os, json
from typing import Any, Dict, List, Optional

from constants import SLACK_BOT_TOKEN, ENV
from util.slackbot import app
from db.photo_request import get_photo_request_by_uid, claim_photo_request


PHOTO_REQUESTS_CHANNEL_ID = "C09NCRWU8T1" if ENV == "dev" else "YYYYYY"


# helpers
def _lookup_user_id_by_email(email: str) -> Optional[str]:
    try:
        return app.client.users_lookupByEmail(email=email)["user"]["id"]
    except Exception as e:
        print(f"[photo_request] users_lookupByEmail({email}) failed: {e}")
        return None


def dm_user_by_email(
    email: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    uid = _lookup_user_id_by_email(email)
    if not uid:
        return {"ok": False, "error": f"user_not_found:{email}"}
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=uid,  # DM via user id
            text=text,
            blocks=blocks or None,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[photo_request] DM failed: {e}")
        return {"ok": False, "error": str(e)}


def _label_for_request(req: dict, default: str = "this request") -> str:
    """Choose a label for the request without ever returning 'False'."""

    def _st(x):
        if x is None or isinstance(x, bool):
            return None
        s = str(x).strip()
        return s or None

    # 1) specificEvent
    ev = _st(req.get("specificEvent"))
    if ev:
        return ev

    # 2) first sentence of memo
    memo = _st(req.get("memo"))
    if memo:
        return memo.split(".")[0].strip() or default

    # 3) fallback
    return default


def ensure_claim_button(
    blocks: List[Dict[str, Any]], request_id: str
) -> List[Dict[str, Any]]:
    """
    Appends a Claim button if none is present.
    We support both action_ids: 'photo_claim' (preferred) and 'actionId-0' (your example).
    The button's value stores a JSON with at least request_id.
    """
    has_actions = any(b.get("type") == "actions" for b in blocks)
    if has_actions:
        # (Assume caller already put the button in)
        return blocks

    btn_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Claim this photo",
                    "emoji": True,
                },
                "action_id": "photo_claim",  # prefer this id
                "value": json.dumps({"request_id": request_id}),
            }
        ],
    }
    return blocks + [{"type": "divider"}, btn_block]


def post_photo_blocks(
    *,
    blocks: List[Dict[str, Any]],
    request_id: str,
    channel_id: Optional[str] = None,
    fallback_text: str = "New photo request",
) -> Dict[str, Any]:
    ch = channel_id or PHOTO_REQUESTS_CHANNEL_ID
    if not ch:
        return {"ok": False, "error": "photo_channel_not_configured"}
    final_blocks = ensure_claim_button(blocks, request_id=request_id)
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=ch,
            text=fallback_text,  # Slack requires a text fallback
            blocks=final_blocks,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[photo_request] post_photo_blocks failed: {e}")
        return {"ok": False, "error": str(e)}


def update_message_blocks(
    channel: str, ts: str, new_blocks: List[Dict[str, Any]], text: Optional[str] = None
) -> Dict[str, Any]:
    try:
        res = app.client.chat_update(
            token=SLACK_BOT_TOKEN,
            channel=channel,
            ts=ts,
            blocks=new_blocks,
            text=text or "Updated",
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[photo_request] chat_update failed: {e}")
        return {"ok": False, "error": str(e)}


# claim button handlers
def _handle_claim_generic(ack, body, logger):
    """
    Handles both 'photo_claim' and legacy 'actionId-0' button presses.
    - Updates DB (claim_photo_request)
    - Updates Slack message (remove actions, add 'Claimed by')
    - confirm to claimer
    - DMs claimer + requester
    """
    ack()
    logger.info(body)

    try:
        user_id = body["user"]["id"]  # Slack ID of claimer
        channel_id = body["channel"]["id"]  # Channel where the message lives
        message = body["message"]
        message_ts = message["ts"]
        original_blocks = message.get("blocks", [])

        # request_id is embedded in the button value (JSON)
        act = body.get("actions", [{}])[0]
        raw_val = act.get("value")
        try:
            import json

            request_id = str(json.loads(raw_val).get("request_id")) if raw_val else None
        except Exception:
            request_id = None

        if not request_id:
            logger.error("[photo_claim] Missing request_id in button value")
            try:
                app.client.chat_postEphemeral(
                    token=SLACK_BOT_TOKEN,
                    channel=channel_id,
                    user=user_id,
                    text="Sorry — couldn’t identify this request.",
                )
            except Exception:
                pass
            return

        #  fetch the existing request
        try:
            req = get_photo_request_by_uid(int(request_id))
        except Exception as e:
            logger.error(f"[photo_claim] DB fetch failed for {request_id}: {e}")
            req = None

        #  get claimer email/name from Slack
        try:
            user_info = app.client.users_info(token=SLACK_BOT_TOKEN, user=user_id)
            claimer_profile = user_info.get("user", {}).get("profile", {})
            claimer_email = claimer_profile.get("email")  # may be None if hidden
            claimer_name = user_info.get("user", {}).get("real_name") or f"<@{user_id}>"
        except Exception as e:
            logger.error(f"[photo_claim] users_info failed for {user_id}: {e}")
            claimer_email, claimer_name = None, f"<@{user_id}>"

        #  update DB
        try:
            claim_photo_request(
                uid=int(request_id),
                photogName=claimer_name,
                photogEmail=claimer_email,
            )
            logger.info(
                f"[photo_claim] DB updated: request {request_id} → {claimer_name} ({claimer_email})"
            )
        except Exception as e:
            logger.error(f"[photo_claim] DB update failed for {request_id}: {e}")

        # update the Slack message: strip actions, append context 'claimed by'
        new_blocks = [b for b in original_blocks if b.get("type") != "actions"]
        # add a context footer
        new_blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"✅ *Claimed by* <@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Request ID:* `{request_id}`"},
                ],
            }
        )
        try:
            update_message_blocks(
                channel_id, message_ts, new_blocks, text="Photo request (claimed)"
            )
        except Exception as e:
            logger.error(f"[photo_claim] chat_update failed: {e}")

        #  ephemeral confirmation to claimer
        try:
            app.client.chat_postEphemeral(
                token=SLACK_BOT_TOKEN,
                channel=channel_id,
                user=user_id,
                text="✅ You successfully claimed this photo request!",
            )
        except Exception:
            pass

        label = _label_for_request(req or {})

        #  DMs: claimer + requester
        try:
            # DM claimer
            if claimer_email:
                dm_user_by_email(
                    email=claimer_email,
                    text=f"✅ You claimed photo request: {label}",
                )
        except Exception as e:
            logger.error(f"[photo_claim] Claimer DM failed: {e}")

        try:
            # DM requester
            submitter_email = (req or {}).get("submitterEmail")
            if submitter_email:
                dm_user_by_email(
                    email=submitter_email,
                    text=f"📸 Your photo request '{label}' has been claimed by <@{user_id}>.",
                )
        except Exception as e:
            logger.error(f"[photo_claim] Requester DM failed: {e}")

    except Exception as e:
        logger.error(f"[photo_slack] claim handler error: {e}")


# Prefer this id going forward
@app.action("photo_claim")
def _photo_claim(ack, body, logger):
    _handle_claim_generic(ack, body, logger)


# Backward-compat with example action_id
@app.action("actionId-0")
def _photo_claim_legacy(ack, body, logger):
    _handle_claim_generic(ack, body, logger)


def build_blocks_from_request(req: dict) -> list:
    """
    Build Slack Block Kit for a photo request with your exact style and rules.
    Enforces that all 'text' values are strings (Slack requirement).
    """

    # --- helper: to safe string or None if empty
    def _st(val) -> Optional[str]:
        if val is None:
            return None
        # Some ORMs may return non-primitive types; always stringify
        s = str(val).strip()
        return s if s else None

    # submitter mention
    submitter_mention = _st(req.get("submitterName")) or "Someone"
    submitter_slack_id = _st(req.get("submitterSlackId"))
    if submitter_slack_id:
        submitter_mention = f"<@{submitter_slack_id}>"

    # DI dept suffix
    di_dept_suffix = ""
    dest = _st(req.get("destination"))
    dept = _st(req.get("department"))
    if dest == "The Daily Illini" and dept:
        di_dept_suffix = f" for *{dept}*"

    blocks: list = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":dailyillini: The Daily Illini",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"New photo request from {submitter_mention}{di_dept_suffix}:",
            },
        },
        {"type": "divider"},
    ]

    # --- main rich_text content
    rich_elems = []

    label = _label_for_request(req)

    rich_elems = []

    # Title always shown now (never "False")
    rich_elems.append(
        {
            "type": "rich_text_section",
            "elements": [{"type": "text", "text": label, "style": {"bold": True}}],
        }
    )

    memo = _st(req.get("memo"))
    if memo:
        rich_elems.append(
            {
                "type": "rich_text_quote",
                "elements": [{"type": "text", "text": memo}],
            }
        )

    more_info = _st(req.get("moreInfo"))
    if more_info:
        rich_elems.extend(
            [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Additional details:"}],
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": more_info}],
                },
            ]
        )

    if rich_elems:
        blocks.append({"type": "rich_text", "elements": rich_elems})

    # Reference link
    reference_url = _st(req.get("referenceURL"))
    if reference_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{reference_url}|Reference link>*",
                },
            }
        )

    # Event details (only if there is a specific event)
    if req.get("specificEvent"):
        event_elems = [
            {
                "type": "rich_text_section",
                "elements": [
                    {"type": "text", "text": "Event Details", "style": {"bold": True}}
                ],
            }
        ]

        # datetime
        dt = req.get("eventDateTime")
        if dt:
            try:
                dt_text = dt.strftime("%A, %b %d at %I:%M %p").lstrip("0")
                event_elems.append(
                    {
                        "type": "rich_text_section",
                        "elements": [{"type": "text", "text": dt_text}],
                    }
                )
            except Exception:
                pass  # if it's not a datetime, skip

        # location (italic)
        loc = _st(req.get("eventLocation"))
        if loc:
            event_elems.append(
                {
                    "type": "rich_text_section",
                    "elements": [
                        {"type": "text", "text": loc, "style": {"italic": True}}
                    ],
                }
            )

        # press credentials line (only if truthy)
        if bool(req.get("pressPass")):
            requester = _st(req.get("pressPassRequester"))
            line = "Press credentials required"
            if requester:
                line += (
                    ", to be requested by editor"
                    if requester == "editor"
                    else f", to be requested by {requester}"
                )
            line += "."
            event_elems.append(
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": line}],
                }
            )

        if len(event_elems) > 1:
            blocks.append({"type": "divider"})
            blocks.append({"type": "rich_text", "elements": event_elems})

    # Due date
    due = req.get("dueDate")
    if due:
        try:
            due_text = due.strftime("%A, %b %d")
            blocks.extend(
                [
                    {"type": "divider"},
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": f"Photo due by {due_text}",
                                        "style": {"bold": True},
                                    }
                                ],
                            }
                        ],
                    },
                ]
            )
        except Exception:
            pass

    return blocks
