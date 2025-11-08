from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from constants import SLACK_BOT_TOKEN, ENV
from util.slackbots._slackbot import app
from db.photo_request import (
    claim_photo_request,
    complete_photo_request,
    update_photo_request,
    get_id_from_slack_claim_ts,
)
from util.helpers.ap_datetime import ap_daydate, ap_daydatetime, ap_datetime

from constants import (
    PHOTO_REQUESTS_CHANNEL_ID,
    COURTESY_REQUESTS_CHANNEL_ID,
)


# helpers
def _lookup_user_id_by_email(email: str) -> Optional[str]:
    try:
        return app.client.users_lookupByEmail(email=email)["user"]["id"]
    except Exception as e:
        print(f"[photo_request] users_lookupByEmail({email}) failed: {e}")
        return None


def get_slack_emoji(destination: Optional[str]) -> str:
    """Return a Slack emoji code based on the destination."""
    dest_map = {
        "The Daily Illini": "dailyillini",
        "Illio Yearbook": "illio",
        "WPGU": "wpgu",
        "Chambana Eats": "chambanaeats",
        "Marketing": "imc",
        "Other": "imc",
    }
    return dest_map.get(destination, "imc")  # default to IMC


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


def dm_user_by_id(
    user_id: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """DM a Slack user by their Slack user id."""
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=user_id,
            text=text,
            blocks=blocks or None,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[photo_request] DM by id failed: {e}")
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


def send_claimer_confirmation(
    *,
    request_id: int | str,
    label: str,
    submitter_id: str,
    user_id: str | None = None,
    email: str | None = None,
) -> dict:
    """
    Send the exact same DM to the claimer (API or Slack-claim).
    Prefers DM by Slack user_id; falls back to email lookup, then email DM.
    """
    msg_text = (
        f'✅ You claimed "*{label}*" submitted by <@{submitter_id}>.\n\n'
        "When the photos are ready and uploaded, reply to this message with the *Google Drive folder* link, or use the IMC Console."
    )

    # Prefer user_id (always works if we have it)
    if user_id:
        res = dm_user_by_id(user_id=user_id, text=msg_text)

    # Try to resolve user_id from email, then DM by id
    elif email:
        try:
            uid = _lookup_user_id_by_email(email)
            if uid:
                res = dm_user_by_id(user_id=uid, text=msg_text)
            else:
                # Fallback to email-based DM
                res = dm_user_by_email(email=email, text=msg_text)
        except Exception:
            # Fallback to email-based DM
            res = dm_user_by_email(email=email, text=msg_text)

    if isinstance(res, dict) and res.get("ok"):
        try:
            update_photo_request(
                uid=int(request_id),
                claimSlackChannel=res.get("channel"),
                claimSlackTs=res.get("ts"),
            )

            return {"ok": True, "message": res}

        except Exception as _e:
            print(f"[photo_submit] storing slack ids failed: {_e}")
            return {"ok": False, "error": "no_recipient"}

    return {"ok": False, "error": "no_recipient"}


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
    courtesy: Optional[bool],
    fallback_text: str = "New photo request",
) -> Dict[str, Any]:
    """
    Post a photo request to Slack, ensure a Claim button exists,
    and persist Slack identifiers (channel, ts) onto the request
    so we can update the message later.
    """
    ch = channel_id or PHOTO_REQUESTS_CHANNEL_ID
    if courtesy:
        ch = COURTESY_REQUESTS_CHANNEL_ID
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
    - Updates DB (claimTimestamp/photog*)
    - Rebuilds Slack message from updated record (so Status footer flips to Claimed)
    - Sends confirmation DM to claimer
    - DMs requester and updates original requstor message
    """
    ack()
    logger.info(body)

    try:
        channel_id = (body.get("channel") or {}).get("id") or (
            body.get("container") or {}
        ).get("channel_id")
        message_ts = (body.get("message") or {}).get("ts") or (
            body.get("container") or {}
        ).get("message_ts")
        user_id = (body.get("user") or {}).get("id")

        if not user_id:
            logger.error("[photo_claim] Missing user_id in action payload")
            return

        # Parse request_id from the button value
        act = (body.get("actions") or [{}])[0]
        raw_val = act.get("value")
        try:
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
                    text="Sorry, I couldn’t identify this request.",
                )
            except Exception:
                pass
            return

        # Get claimer identity from Slack (email may be None if hidden)
        try:
            user_info = app.client.users_info(token=SLACK_BOT_TOKEN, user=user_id)
            claimer_profile = user_info.get("user", {}).get("profile", {})
            claimer_email = claimer_profile.get("email")
            claimer_name = user_info.get("user", {}).get("real_name") or f"<@{user_id}>"
        except Exception as e:
            logger.error(f"[photo_claim] users_info failed for {user_id}: {e}")
            claimer_email, claimer_name = None, f"<@{user_id}>"

        try:
            claim_request(uid=int(request_id), name=claimer_name, email=claimer_email)
        except Exception as e:
            logger.error(f"[photo_claim] DB claim_request failed for {request_id}: {e}")

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


def build_blocks_from_request(req: dict) -> tuple[list, str]:
    """
    Build Slack Block Kit for a photo request with your exact style and rules.
    Enforces that all 'text' values are strings (Slack requirement).
    Also returns a simple string version for screen readers.
    """

    # --- helper: to safe string or None if empty
    def _st(val) -> Optional[str]:
        if val is None:
            return None
        # Some ORMs may return non-primitive types; always stringify
        s = str(val).strip()
        return s if s else None

    # submitter mention
    submitter_name = _st(req.get("submitterName")) or "Someone"
    submitter_slack_id = _st(req.get("submitterSlackId"))
    if submitter_slack_id:
        submitter_mention = f"<@{submitter_slack_id}>"

    # DI dept suffix
    di_dept_suffix = ""
    dest = _st(req.get("destination"))
    dept = _st(req.get("department"))
    if dest == "The Daily Illini" and dept:
        di_dept_suffix = f" for *{dept}*"

    slack_emoji = get_slack_emoji(dest)

    # Create the first block with the header displaying the destination and the person who submitted the request
    blocks: list = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":{slack_emoji}: {dest}",
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

    # Add header to the fallback text
    fallback_text = (
        f"New photo request from {submitter_name} for {dest}{di_dept_suffix}."
    )

    # --- main rich_text content
    rich_elems = []

    label = _label_for_request(req)

    rich_elems = []

    # Append the title for the "memo" section
    # Title always shown now (never "False")
    rich_elems.append(
        {
            "type": "rich_text_section",
            "elements": [{"type": "text", "text": label, "style": {"bold": True}}],
        }
    )

    # Append the memo
    memo = _st(req.get("memo"))
    if memo:
        rich_elems.append(
            {
                "type": "rich_text_quote",
                "elements": [{"type": "text", "text": memo}],
            }
        )
        fallback_text += f"\nMemo: {memo}"

    # Append the "Specific details" section
    specific_details = _st(req.get("specificDetails"))
    if specific_details:
        rich_elems.extend(
            [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Specific details:"}],
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": specific_details}],
                },
            ]
        )
        fallback_text += f"\nSpecific details: {specific_details}"

    # Append the "More info" section (if present)
    more_info = _st(req.get("moreInfo"))
    if more_info:
        rich_elems.extend(
            [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "More info:"}],
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": more_info}],
                },
            ]
        )
        fallback_text += f"\nMore Info: {more_info}"

    if rich_elems:
        blocks.append({"type": "rich_text", "elements": rich_elems})

    # Append the reference link as a hyperlink
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
        fallback_text += f"\nReference URL: {reference_url}"

    # Append event details (only if there is a specific event)
    if req.get("specificEvent"):
        event_elems = [
            {
                "type": "rich_text_section",
                "elements": [
                    {"type": "text", "text": "Event Details", "style": {"bold": True}}
                ],
            }
        ]
        fallback_text += f"\nEvent Details:"

        # Append the date and time of the event (formatted to AP style)
        dt = req.get("eventDateTime")
        if dt:
            try:
                dt_text = ap_daydatetime(dt)
                event_elems.append(
                    {
                        "type": "rich_text_section",
                        "elements": [{"type": "text", "text": dt_text}],
                    }
                )
                fallback_text += f"\n\tDate/Time: {dt_text}"
            except Exception:
                pass  # if it's not a datetime, skip

        # Append the location of the event (italic)
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
            fallback_text += f"\n\tLocation: {loc}"

        # Append the press credential requestor line (only if truthy)
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
            fallback_text += (
                f"\n\tPress credentials required, requested by {requester}."
            )

        if len(event_elems) > 1:
            blocks.append({"type": "divider"})
            blocks.append({"type": "rich_text", "elements": event_elems})

    # Append the due date
    due = req.get("dueDate")
    if due:
        try:
            due_text = ap_daydate(due)  # Convert to AP style
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
            fallback_text += f"\nPhoto Due Date: {due_text}"
        except Exception:
            pass

    # Status footer (display if the request is submitted/claimed/completed)
    status = (str(req.get("status") or "submitted")).lower()
    photog = req.get("photogEmail")
    photog_slack_id = req.get("photogSlackId")
    drive = req.get("driveURL")
    status_text = f"*Status:* {status.capitalize()}"
    fallback_text += f"\nStatus: {status.capitalize()}"
    if status == "claimed" and photog:
        claim_time = req.get("claimTimestamp")
        claim_time = ap_datetime(claim_time)
        status_text += f" by <@{photog_slack_id}> on {claim_time}"
    if status == "completed":
        if photog:
            complete_time = req.get("completedTimestamp")
            complete_time = ap_datetime(complete_time)
            status_text += f" by <@{photog_slack_id}> on {complete_time}"
        if drive:
            status_text += f" — <{drive}|Drive folder>"
    blocks.extend(
        [
            {"type": "divider"},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": status_text}]},
        ]
    )

    return blocks, fallback_text


def _extract_drive_url(text: str) -> Optional[str]:
    """
    Parses a Google Drive link out of a message body.
    If the message contains a valid Drive URL, this function
    returns the URL. Otherwise, it returns None
    """

    rx = re.compile(r"https?://drive\.google\.com/[^\s>]+")
    m = rx.search(text or "")
    return m.group(0) if m else None


@app.event("message")
def _on_dm_message(body, logger, event):
    """
    Function is called on Slack message events. When a message is posted
    in a channel that the bot user is in, this function will run.

    Handles replies in a thread by the photographer when they complete
    a photo request. First checks that the message was in a direct message
    channel, then checks that it was a reply in a thread. Checks that the
    parent message in the thread is relevant to any photo request. Validates
    that the user provided input is a valid Google Drive URL, then replies
    to confirm receipt of the message. Also completes the photo request.
    """

    try:
        ev = event
        # Ignore bot messages / edits / channel messages
        if ev.get("bot_id"):
            return
        if ev.get("channel_type") != "im":
            return
        user_id = ev.get("user")
        text = (ev.get("text") or "").strip()
        if not user_id or not text:
            return

        # We only care about thread replies
        thread_ts = None
        if "thread_ts" in ev and ev.get("thread_ts") != ev.get("ts"):
            thread_ts = ev.get(
                "thread_ts"
            )  # ts of the parent message, the one we stored in the db

        channel = ev.get("channel")

        if not thread_ts or not channel:
            return

        print(channel, thread_ts)

        req = get_id_from_slack_claim_ts(channel, thread_ts)

        if not req:
            return  # Simply return if this message isn't one we care about so we don't break other code

        # Make sure the link is a valid Google Drive URL
        drive = _extract_drive_url(text)
        if not drive:
            # Let the user know if the link was invalid
            try:
                res = app.client.chat_postMessage(
                    token=SLACK_BOT_TOKEN,
                    channel=user_id,
                    text=f"That doesn't look like a Google Drive link to me, could you try again?",
                    thread_ts=thread_ts,
                )
                return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
            except Exception as e:
                print(f"[dm_link] DM by id failed: {e}")
                return {"ok": False, "error": str(e)}

        # Check if the request has already been completed
        if req.get("status") == "completed":
            # Let the user know it was already completed
            try:
                res = app.client.chat_postMessage(
                    token=SLACK_BOT_TOKEN,
                    channel=user_id,
                    text=f"This request has already been completed.",
                    thread_ts=thread_ts,
                )
                return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
            except Exception as e:
                print(f"[dm_link] DM by id failed: {e}")
                return {"ok": False, "error": str(e)}

        # Complete the request
        try:
            complete_request(uid=req.get("uid"), driveURL=drive)
        except Exception as e:
            logger.error(
                f"[dm_link] DB complete_request failed for {req.get('uid')}: {e}"
            )

    except Exception as e:
        logger.error(f"[dm_link] handler error: {e}")


def claim_request(uid: int, name: str, email: str):
    """
    Claim a photo request. Called by both the API and when a user clicks the claim
    button in Slack. Claims the request via the database. DMs the claimer a
    confirmation message. Updates the original message sent in the channel to
    reflect the new claimed status as well as the claimer and timestamp. Notifies
    the requestor that their request has been claimed.

    :param uid: The UID of the request to claim
    :type uid: int
    :param name: The name of the photographer that claimed the request
    :type name: string
    :param email: The email address of the photographer that claimed the request
    :returns: Message and HTTP status code
    :rtype: tuple
    """

    # DB: mark as claimed
    updated = claim_photo_request(uid=int(uid), photogName=name, photogEmail=email)
    if not updated:
        return {"error": "not found"}, 400

    # DM claimer
    try:
        label = _label_for_request(updated)
        send_claimer_confirmation(
            request_id=uid,
            label=label,
            email=email,
            submitter_id=updated.get("submitterSlackId"),
        )
    except Exception as e:
        print(f"[api_claim] DM to claimer failed: {e}")
        return {"error": f"[api_claim] DM to claimer failed: {e}"}, 400

    # Update the original channel message to reflect 'claimed'
    try:
        ch = updated.get("slackChannel")
        ts = updated.get("slackTs")
        if ch and ts:
            new_blocks, fallback_text = build_blocks_from_request(updated)

            # remove any action buttons in the original post
            new_blocks = [b for b in new_blocks if b.get("type") != "actions"]

            update_message_blocks(ch, ts, new_blocks, text=fallback_text)

            # Now update the original message that was sent to the submitter
            sub_ch = updated.get("submitSlackChannel")
            sub_ts = updated.get("submitSlackTs")
            if sub_ch and sub_ts:
                update_message_blocks(sub_ch, sub_ts, new_blocks, text=fallback_text)

    except Exception as e:
        print(f"[api_claim] Slack update failed: {e}")
        return {"error": f"[api_claim] Slack update failed: {e}"}, 400

    # notify the requester
    try:
        submitter = updated.get("submitterEmail")
        if submitter:
            label = _label_for_request(updated)
            dm_user_by_email(
                email=submitter,
                text=f"📸 Your photo request \"*{label}*\" has been *claimed* by <@{updated.get('photogSlackId')}>.",
            )
    except Exception as e:
        print(f"[api_claim] DM to requester failed: {e}")
        return {"error": f"[api_claim] DM to requester failed: {e}"}, 400

    return {"message": "claimed", "request": updated}, 200


def complete_request(uid: int, driveURL: str):
    """
    Complete a photo request. Called by both the API and when a user replies to a
    confirmation message in Slack. Completes the request via the database. Updates
    the original message sent to both the channel and the requestor to reflect the
    new completed status as well as the photographer and completion timestamp.
    Notifies the requestor that their request has been completed. Replies in a
    thread to the claimer confirming that the request has been completed.

    :param uid: The UID of the request to complete
    :type uid: int
    :param driveURL: The URL of the folder containing the photos
    :type driveURL: string
    :returns: Message and HTTP status code
    :rtype: tuple
    """
    # DB: mark as completed
    updated = complete_photo_request(uid=int(uid), driveURL=driveURL)
    if not updated:
        return {"error": "not found"}, 400

    # Update the original channel message to reflect 'completed'
    try:
        ch = updated.get("slackChannel")
        ts = updated.get("slackTs")
        if ch and ts:
            new_blocks, fallback_text = build_blocks_from_request(updated)

            # remove any action buttons in the original post
            new_blocks = [b for b in new_blocks if b.get("type") != "actions"]

            update_message_blocks(ch, ts, new_blocks, text=fallback_text)

            # Now update the original message that was sent to the submitter
            sub_ch = updated.get("submitSlackChannel")
            sub_ts = updated.get("submitSlackTs")
            if sub_ch and sub_ts:
                update_message_blocks(sub_ch, sub_ts, new_blocks, text=fallback_text)

    except Exception as e:
        print(f"[api_complete] Slack update failed: {e}")
        return {"error": f"[api_complete] Slack update failed: {e}"}, 400

    # notify the requester. Only include the link if its not for The DI or Illio
    try:
        submitter = updated.get("submitterEmail")
        if submitter:
            label = _label_for_request(updated)
            message_text = f'✅ Your photo request "*{label}*" has been completed!'

            if updated.get("destination") not in ("The Daily Illini", "Illio Yearbook"):
                message_text += " Here's the link to your photos: "
                message_text += updated.get("driveURL")

            dm_user_by_email(
                email=submitter,
                text=message_text,
            )
    except Exception as e:
        print(f"[api_complete] DM to requester failed: {e}")
        return {"error": f"[api_complete] DM to requester failed: {e}"}, 400

    # Reply in a thread to the claimer's message
    claim_ch = updated.get("claimSlackChannel")
    claim_ts = updated.get("claimSlackTs")
    if claim_ch and claim_ts:
        try:
            res = app.client.chat_postMessage(
                token=SLACK_BOT_TOKEN,
                channel=updated.get("photogSlackId"),
                text=f"✅ I got the link! This photo request is now complete.\n{updated.get('driveURL')}",
                thread_ts=claim_ts,
            )
            return {"ok": True, "channel": res["channel"], "ts": res["ts"]}, 200
        except Exception as e:
            print(f"[photo_request] DM by id failed: {e}")
            return {"ok": False, "error": str(e)}, 400

    return {
        "ok": False,
        "error": "[api_complete] Could not send confirmation to claimer.",
    }, 400
