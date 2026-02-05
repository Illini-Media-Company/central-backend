"""
Socials Slack bot — handles DI stories going to the social channel.

When a new story shows up (e.g. from RSS), we post it to the social media Slack channel
with title, link, writer, photographer, and photo. No photo? We show a "Needs Visual"
button that kicks over to the Photo Editors channel. When they add media, we reply in
the original thread with the new image. Reactions on the message (e.g. :instagram:)
record which platform it was posted to and we reply with the timestamp.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from constants import (
    COURTESY_REQUESTS_CHANNEL_ID,
    SLACK_BOT_TOKEN,
    SOCIAL_MEDIA_POSTS_CHANNEL_ID,
)
from util.slackbots._slackbot import app
from db.di_social_story import client as db_client
from db.di_social_story import DiSocialStory
from db.di_social_story import update_social
from util.helpers.ap_datetime import ap_datetime

# Map Slack reaction names to our platform names (for update_social)
REACTION_TO_PLATFORM = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "reddit": "Reddit",
    "twitter": "X",
    "x": "X",
    "threads": "Threads",
}


def update_slack_message_ref(url: str, channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
    """Save the Slack channel + message ts for this story so we can reply or match reactions later."""
    with db_client.context():
        story = DiSocialStory.query().filter(DiSocialStory.story_url == url).get()
        if story:
            story.slack_channel_id = channel_id
            story.slack_message_ts = message_ts
            if story.slack_message_timestamp is None:
                story.slack_message_timestamp = datetime.now()
            story.put()
            return story.to_dict()
    return None


def get_story_by_slack_message(channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
    """Look up a story by the Slack message (channel + ts). Used when we get a reaction."""
    if not channel_id or not message_ts:
        return None
    with db_client.context():
        story = (
            DiSocialStory.query()
            .filter(
                DiSocialStory.slack_channel_id == channel_id,
                DiSocialStory.slack_message_ts == message_ts,
            )
            .get()
        )
        return story.to_dict() if story else None


def build_blocks_from_story(
    *,
    story_url: str,
    story_title: str,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    image_url: Optional[str] = None,
    include_needs_visual_button: bool = False,
    story_url_for_button: Optional[str] = None,
    social_channel_id: Optional[str] = None,
    social_message_ts: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Build Block Kit blocks for one story message. Returns (blocks, fallback text for notifications)."""
    lines = [f"*<{story_url}|{story_title}>*"]
    if writer_name:
        lines.append(f"Writer: {writer_name}")
    if photographer_name:
        lines.append(f"Photographer: {photographer_name}")

    blocks: List[Dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]

    if image_url:
        blocks.append({
            "type": "image",
            "image_url": image_url,
            "alt_text": story_title[:100],
        })
    elif include_needs_visual_button and story_url_for_button is not None:
        value = json.dumps({
            "story_url": story_url_for_button,
            "social_channel_id": social_channel_id or "",
            "social_message_ts": social_message_ts or "",
        })
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Needs Visual", "emoji": True},
                "action_id": "social_needs_visual",
                "value": value,
            }],
        })

    fallback = f"{story_title} — {story_url}"
    return blocks, fallback


def post_story_to_social_channel(
    *,
    story_url: str,
    story_title: str,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Post a new story to the social channel. We send a short parent message, then a thread
    reply with the full details (and image if we have one, otherwise a "Needs Visual" button).
    Also stores channel/ts on the story so reactions and follow-up replies work.
    """
    if not SOCIAL_MEDIA_POSTS_CHANNEL_ID:
        return {"ok": False, "error": "SOCIAL_MEDIA_POSTS_CHANNEL_ID not set"}

    short_text = f"New story: {story_title}"
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=SOCIAL_MEDIA_POSTS_CHANNEL_ID,
            text=short_text,
        )
        channel_id = res["channel"]
        message_ts = res["ts"]
    except Exception as e:
        print(f"[socials_slackbot] chat_postMessage failed: {e}")
        return {"ok": False, "error": str(e)}

    include_button = not bool(image_url)
    thread_blocks, fallback = build_blocks_from_story(
        story_url=story_url,
        story_title=story_title,
        writer_name=writer_name,
        photographer_name=photographer_name,
        image_url=image_url,
        include_needs_visual_button=include_button,
        story_url_for_button=story_url if include_button else None,
        social_channel_id=channel_id if include_button else None,
        social_message_ts=message_ts if include_button else None,
    )
    try:
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            thread_ts=message_ts,
            text=fallback,
            blocks=thread_blocks,
        )
    except Exception as e:
        print(f"[socials_slackbot] thread reply failed: {e}")

    update_slack_message_ref(story_url, channel_id, message_ts)
    return {"ok": True, "channel": channel_id, "ts": message_ts}


def _reply_in_thread(
    channel_id: str,
    thread_ts: str,
    text: str,
    blocks: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Reply in a thread. Optional blocks (e.g. for an image)."""
    try:
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
        return True
    except Exception as e:
        print(f"[socials_slackbot] reply failed: {e}")
        return False


# --- Needs Visual button: send to Photo Editors channel ---

@app.action("social_needs_visual")
def _handle_needs_visual(ack, body, logger):
    ack()
    logger.info(body)
    try:
        channel_id = (body.get("channel") or {}).get("id") or (body.get("container") or {}).get("channel_id")
        message_ts = (body.get("message") or {}).get("ts") or (body.get("container") or {}).get("message_ts")
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
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Visual added", "emoji": True},
                    "action_id": "social_visual_added",
                    "value": json.dumps({
                        "story_url": story_url,
                        "social_channel_id": channel_id,
                        "social_message_ts": message_ts,
                    }),
                }],
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

        private_metadata = json.dumps({
            "story_url": story_url,
            "social_channel_id": social_channel_id,
            "social_message_ts": social_message_ts,
        })
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
                            "placeholder": {"type": "plain_text", "text": "https://example.com/image.jpg"},
                        },
                        "label": {"type": "plain_text", "text": "Image URL (new photo/media for the story)"},
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"[social_visual_added] {e}")


@app.view(VISUAL_ADDED_MODAL_CALLBACK)
def _handle_visual_added_modal_submit(ack, body, logger, view):
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
                {"type": "section", "text": {"type": "mrkdwn", "text": "Visual added by photo team:"}},
                {"type": "image", "image_url": image_url, "alt_text": "Story visual"},
            ]
            _reply_in_thread(
                social_channel_id,
                social_message_ts,
                "Visual added by photo team.",
                blocks=blocks,
            )
        else:
            _reply_in_thread(
                social_channel_id,
                social_message_ts,
                "Visual added by photo team. (No image URL provided.)",
            )
    except Exception as e:
        logger.error(f"[social_visual_added_modal] {e}")


# --- Reaction added: if it's a platform emoji on our message, update DB and reply ---

@app.event("reaction_added")
def _on_reaction_added(event, logger):
    """When someone reacts with e.g. :instagram:, mark that platform as posted and reply in thread."""
    try:
        item = event.get("item") or {}
        if item.get("type") != "message":
            return
        channel_id = item.get("channel")
        message_ts = item.get("ts")
        reaction = (event.get("reaction") or "").strip().lower()
        if not channel_id or not message_ts or not reaction:
            return

        story = get_story_by_slack_message(channel_id, message_ts)
        if not story:
            return

        platform = REACTION_TO_PLATFORM.get(reaction)
        if not platform:
            return

        story_url = story.get("story_url")
        if not story_url:
            return

        update_social(story_url, platform)
        now = datetime.now(ZoneInfo("America/Chicago"))
        time_str = ap_datetime(now)
        _reply_in_thread(
            channel_id,
            message_ts,
            f"This was posted to {platform} at {time_str}.",
        )
    except Exception as e:
        logger.error(f"[socials_slackbot] reaction_added: {e}")


def notify_new_story_from_rss(
    story_url: str,
    story_title: str,
    writer_name: Optional[str] = None,
    photographer_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Called when a new (non-sponsored) story is picked up from RSS. Just forwards to post_story_to_social_channel."""
    return post_story_to_social_channel(
        story_url=story_url,
        story_title=story_title,
        writer_name=writer_name,
        photographer_name=photographer_name,
        image_url=image_url,
    )
