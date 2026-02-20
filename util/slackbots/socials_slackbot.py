"""
Socials Slack bot — handles DI stories going to the social channel.

When a new story shows up (e.g. from RSS), we post it to the social media Slack channel
with title, link, writer, photographer, and photo. Reactions on the message (e.g. :instagram:)
record which platform it was posted to and we reply with the timestamp.

Last modified by Aryaa Rathi on Feb 19, 2026
"""

from __future__ import annotations
import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from gcsa.google_calendar import GoogleCalendar

from constants import (
    COURTESY_REQUESTS_CHANNEL_ID,
    SLACK_BOT_TOKEN,
    SOCIAL_MEDIA_GCAL_ID,
    SOCIAL_MEDIA_POSTS_CHANNEL_ID,
)
from util.security import get_creds
from util.slackbots._slackbot import app
from util.slackbots.general import (
    _lookup_user_id_by_email,
    dm_channel_by_id,
    reply_to_slack_message,
)
from db.socials_poster import (
    update_social,
    update_slack_details,
    get_story_by_slack_message,
)
from util.helpers.ap_datetime import ap_datetime
from util.social_posts import post_to_reddit, post_to_twitter

logger = logging.getLogger(__name__)

# Map Slack reaction names to our platform names (for update_social)
# Slack emoji names (without colons; from reaction_added event) → platform for DB
REACTION_TO_PLATFORM = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "reddit": "Reddit",
    "threads": "Threads",
    "twitter-x": "X",
}

# Calendar scope for socials shift lookup (same as copy_editing)
SOCIALS_GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_socials_on_shift_email() -> Optional[str]:
    """
    Get the email of the person on shift today from the socials Google Calendar.
    Returns first attendee's email or None;
    """
    if not SOCIAL_MEDIA_GCAL_ID:
        return None
    try:
        creds = get_creds(SOCIALS_GCAL_SCOPES)
        gc = GoogleCalendar(SOCIAL_MEDIA_GCAL_ID, credentials=creds)
    except Exception as e:
        logger.error(f"Failed to get Google Calendar credentials: {str(e)}")
        return None
    current_time = datetime.now(tz=ZoneInfo("America/Chicago"))
    today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    try:
        events = gc.get_events(
            today, tomorrow, single_events=True, order_by="startTime"
        )
    except Exception as e:
        logger.error(f"Failed to get Google Calendar events: {str(e)}")
        return None
    for event in events:
        if not getattr(event, "attendees", None):
            continue
        for attendee in event.attendees:
            email = getattr(attendee, "email", None)
            if email and not str(email).endswith("resource.calendar.google.com"):
                return email
    return None


def build_blocks_from_story(
    *,
    story_url: str,
    story_title: str,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    post_date: Optional[str] = None,
    image_url: Optional[str] = None,
    include_needs_visual_button: bool = False,
    story_url_for_button: Optional[str] = None,
    social_channel_id: Optional[str] = None,
    social_message_ts: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Build Slack Block Kit blocks for a story message with optional image and button.
    Returns (blocks, fallback text for notifications).
    """
    lines = [f"*<{story_url}|{story_title}>*"]
    if post_date:
        lines.append(f"Posted to website {post_date}")
    if writer_name:
        lines.append(f"Writer: {writer_name}")
    if photographer_name:
        lines.append(f"Photographer: {photographer_name}")

    blocks: List[Dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]

    if image_url:
        blocks.append(
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": story_title[:100],
            }
        )
    elif include_needs_visual_button and story_url_for_button is not None:
        value = json.dumps(
            {
                "story_url": story_url_for_button,
                "social_channel_id": social_channel_id or "",
                "social_message_ts": social_message_ts or "",
            }
        )
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Needs Visual",
                            "emoji": True,
                        },
                        "action_id": "social_needs_visual",
                        "value": value,
                    }
                ],
            }
        )

    fallback = f"{story_title} — {story_url}"
    return blocks, fallback


def post_story_to_social_channel(
    *,
    post_date: Optional[str] = None,
    story_url: str,
    story_title: str,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Post a new story to the social Slack channel with a parent message and thread reply.
    Tags the person on shift and stores message timestamp in the database.
    """
    if not SOCIAL_MEDIA_POSTS_CHANNEL_ID:
        return {"ok": False, "error": "SOCIAL_MEDIA_POSTS_CHANNEL_ID not set"}

    # Tag the person on shift today (from socials calendar), or fall back to default message
    email = get_socials_on_shift_email()
    slack_id = None
    if email:
        try:
            slack_id = _lookup_user_id_by_email(email)
        except Exception as e:
            logger.error(f"Failed to look up Slack ID for email {email}: {str(e)}")
    short_text = (
        f"<@{slack_id}> New story: {story_title}"
        if slack_id
        else f"New story: {story_title}"
    )
    channel_id = None
    message_ts = None
    try:
        res = dm_channel_by_id(
            channel_id=SOCIAL_MEDIA_POSTS_CHANNEL_ID, text=short_text, blocks=None
        )
        channel_id = res["channel"]
        message_ts = res["ts"]
    except Exception as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
        return {"ok": False, "error": str(e)}

    # Do not show "Needs Visual" button; if no image, message just has no image.
    thread_blocks, fallback = build_blocks_from_story(
        post_date=post_date,
        story_url=story_url,
        story_title=story_title,
        writer_name=writer_name,
        photographer_name=photographer_name,
        image_url=image_url,
        include_needs_visual_button=False,
        story_url_for_button=None,
        social_channel_id=None,
        social_message_ts=None,
    )
    try:
        res = reply_to_slack_message(
            channel_id=channel_id,
            thread_ts=message_ts,
            text=fallback,
            blocks=thread_blocks,
            reply_broadcast=False,
        )
    except Exception as e:
        logger.error(f"Failed to send threaded reply: {str(e)}")

    update_slack_details(story_url, message_ts)
    return {"ok": True, "channel": channel_id, "ts": message_ts}


# --- Needs Visual button: send to Photo Editors channel ---


@app.action("social_needs_visual")
def _handle_needs_visual(ack, body, logger):
    """
    Handle "Needs Visual" button click: send request to Photo Editors channel. Not in use right now.
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
        actions = body.get("actions") or [{}]
        raw_val = actions[0].get("value")
        if not raw_val:
            return
        payload = json.loads(raw_val)
        story_url = payload.get("story_url")
        if not story_url:
            return

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Needs visual for social post*\n<{story_url}|Story link>",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Visual added",
                            "emoji": True,
                        },
                        "action_id": "social_visual_added",
                        "value": json.dumps(
                            {
                                "story_url": story_url,
                                "social_channel_id": channel_id,
                                "social_message_ts": message_ts,
                            }
                        ),
                    }
                ],
            },
        ]
        if not COURTESY_REQUESTS_CHANNEL_ID:
            return
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=COURTESY_REQUESTS_CHANNEL_ID,
            text=f"Needs visual for social post: {story_url}",
            blocks=blocks,
        )
    except Exception as e:
        logger.error(f"[social_needs_visual] {e}")


# --- Visual added: open modal for image URL, then reply in original thread ---

VISUAL_ADDED_MODAL_CALLBACK = "social_visual_added_modal"


@app.action("social_visual_added")
def _handle_visual_added(ack, body, logger, client):
    """
    Handle "Visual added" button click: open modal to enter image URL. Not in use right now.
    """
    ack()
    logger.info(body)
    try:
        actions = body.get("actions") or [{}]
        raw_val = actions[0].get("value")
        if not raw_val:
            return
        payload = json.loads(raw_val)
        story_url = payload.get("story_url")
        social_channel_id = payload.get("social_channel_id")
        social_message_ts = payload.get("social_message_ts")
        if not all([story_url, social_channel_id, social_message_ts]):
            return

        private_metadata = json.dumps(
            {
                "story_url": story_url,
                "social_channel_id": social_channel_id,
                "social_message_ts": social_message_ts,
            }
        )
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": VISUAL_ADDED_MODAL_CALLBACK,
                "private_metadata": private_metadata,
                "title": {"type": "plain_text", "text": "Visual added"},
                "submit": {"type": "plain_text", "text": "Post to social thread"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "image_url_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "image_url_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "https://example.com/image.jpg",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Image URL (new photo/media for the story)",
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"[social_visual_added] {e}")


@app.view(VISUAL_ADDED_MODAL_CALLBACK)
def _handle_visual_added_modal_submit(ack, body, logger, view):
    """
    Handle visual added modal submission: post image to original social thread. Not in use right now.
    """
    ack()
    try:
        meta = json.loads(view.get("private_metadata") or "{}")
        social_channel_id = meta.get("social_channel_id")
        social_message_ts = meta.get("social_message_ts")
        values = view.get("state", {}).get("values", {})
        url_block = values.get("image_url_block", {})
        url_input = url_block.get("image_url_input", {})
        image_url = (url_input.get("value") or "").strip()

        if not social_channel_id or not social_message_ts:
            return

        if image_url:
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Visual added by photo team:"},
                },
                {"type": "image", "image_url": image_url, "alt_text": "Story visual"},
            ]
            reply_to_slack_message(
                channel_id=social_channel_id,
                thread_ts=social_message_ts,
                text="Visual added by photo team.",
                blocks=blocks,
            )
        else:
            reply_to_slack_message(
                channel_id=social_channel_id,
                thread_ts=social_message_ts,
                text="Visual added by photo team. (No image URL provided.)",
                blocks=None,
            )
    except Exception as e:
        logger.error(f"[social_visual_added_modal] {e}")


# --- Reaction added: if it's a platform emoji on our message, update DB and reply ---


@app.event("reaction_added")
def _on_reaction_added(event):
    """
    Handle reaction added event: when someone reacts with a platform emoji (e.g. :instagram:),
    mark that platform as posted in the database and reply with timestamp in thread.
    """
    logger.debug(f"Reaction added event: {event}")
    try:
        item = event.get("item") or {}
        if item.get("type") != "message":
            logger.debug("Reaction added to non-message item, ignoring.")
            return
        channel_id = item.get("channel")
        message_ts = item.get("ts")
        reaction = (event.get("reaction") or "").strip().lower()
        platform = REACTION_TO_PLATFORM.get(reaction)
        if not platform:
            logger.debug(
                f"Reaction '{reaction}' is not a recognized platform emoji, ignoring."
            )
            return
        if not channel_id or not message_ts or not reaction:
            logger.debug(
                "Missing channel_id, message_ts, or reaction in event, ignoring."
            )
            return

        story = get_story_by_slack_message(channel_id, message_ts)
        if not story:
            logger.debug(
                f"No story found for message {channel_id}:{message_ts}, ignoring reaction."
            )
            return

        story_url = story.get("story_url")
        if not story_url:
            logger.debug(
                f"Story for message {channel_id}:{message_ts} has no URL, cannot update, ignoring."
            )
            return

        now = datetime.now(ZoneInfo("America/Chicago"))
        time_str = ap_datetime(now)

        # See if we need to post this to Reddit or X
        if platform in ["Reddit", "X"]:
            logger.info(
                f"Reaction '{reaction}' added to story {story_url}, automatically posting to {platform}"
            )

            story_name = story.get("story_name")
            social_url = None
            if platform == "Reddit":
                try:
                    social_url, _ = post_to_reddit(title=story_name, url=story_url)
                except Exception:
                    pass
            elif platform == "X":
                try:
                    social_url, _ = post_to_twitter(title=story_name, url=story_url)
                except Exception:
                    pass

            if social_url:
                update_social(story_url, platform)

                # Send Slack message in thread confirming the update
                reply_to_slack_message(
                    channel_id=channel_id,
                    thread_ts=message_ts,
                    text=f"Automatically posted to {platform} at {time_str}.",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"Automatically posted to <{social_url}|{platform}> at {time_str}.",
                            },
                        }
                    ],
                )
            else:
                logger.error(
                    f"Failed to automatically post story {story_url} to {platform} after reaction."
                )
                reply_to_slack_message(
                    channel_id=channel_id,
                    thread_ts=message_ts,
                    text=f"Failed to automatically post to {platform} at {time_str}.",
                    blocks=None,
                )

        # Otherwise just notify that it was posted manually
        else:
            logger.info(
                f"Reaction '{reaction}' added to story {story_url}, marking as posted to {platform}"
            )

            update_social(story_url, platform)

            # Send Slack message in thread confirming the update
            reply_to_slack_message(
                channel_id=channel_id,
                thread_ts=message_ts,
                text=f"Posted to {platform} at {time_str}.",
                blocks=None,
            )
    except Exception as e:
        logger.error(f"Failed to send reaction added message: {str(e)}")


def notify_new_story_from_rss(
    story_url: str,
    story_title: str,
    post_date: Optional[str] = None,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called when a new (non-sponsored) story is picked up from RSS.
    Forwards to post_story_to_social_channel to post to Slack.
    """
    return post_story_to_social_channel(
        post_date=post_date,
        story_url=story_url,
        story_title=story_title,
        writer_name=writer_name,
        photographer_name=photographer_name,
        image_url=image_url,
    )
