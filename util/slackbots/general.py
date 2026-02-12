"""
Includes general use Slackbot functions.

Created on Feb. 4, 2026 by Jacob Slabosz
Last modified Feb. 11, 2026
"""

import logging
from typing import Any, Dict, List, Optional
from constants import SLACK_BOT_TOKEN
from util.slackbots._slackbot import app


logger = logging.getLogger(__name__)


# Local cache for user IDs
_user_id_cache = {}


def can_bot_access_channel(channel_id: str) -> bool:
    """
    Checks if a channel exists and if the acting bot is in it.

    Arguments:
        `channel_id` (`str`): The ID of the channel

    Returns:
        `bool`: `True` if the channel exists and is accessible, `False` otherwise
    """
    logger.debug(f"Checking bot access for channel {channel_id}")

    try:
        res = app.client.conversations_info(channel=channel_id)

        if not res.get("ok"):
            logger.warning(f"Slack API returned ok=False for channel {channel_id}.")
            return False

        is_member = res["channel"].get("is_member", False)

        if is_member:
            logger.debug(f"Bot has access to channel {channel_id}.")
        else:
            logger.debug(f"Bot is NOT a member of channel {channel_id}.")

        return is_member
    except Exception as e:
        error_msg = str(e)

        if "channel_not_found" in error_msg:
            logger.error(
                f"Channel ID {channel_id} not found. Verify channel's ID and existence."
            )
        elif "missing_scope" in error_msg:
            logger.critical(
                f"Permissions Error: Bot lacks 'channels:read' or 'groups:read' scope."
            )
        elif "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")
        else:
            logger.exception(
                f"Unexpected error querying Slack channel {channel_id}: {error_msg}"
            )

        return False


def dm_user_by_email(
    email: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Sends a Slack direct message from the bot account to a given user specified
    by their email address in Slack (IMC email). Always use dm_channel_by_id instead
    if the user's Slack ID is available to decrease total Slack API calls.

    Arguments:
        `email` (`str`): The email address of the user to send a message to
        `text` (`str`): The text of the message
        `blocks` (`Optional[List[Dict[str, Any]]]`): The message formatted as
            Slack blocks

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    logger.debug(f"Attempting to send DM to email {email}.")

    user_id = _lookup_user_id_by_email(email)
    if not user_id:
        logger.warning(f"Aborting DM to {email}: Slack User ID could not be resolved.")
        return {"ok": False, "error": f"user_not_found:{email}"}

    logger.debug(f"Resolved {email} to {user_id}. Passing to dm_channel_by_id.")

    result = dm_channel_by_id(channel_id=user_id, text=text, blocks=blocks)
    if result.get("ok"):
        logger.info(f"DM successfully sent to {email} (ID: {user_id}).")
    else:
        logger.error(
            f"Failed to DM {email} (ID: {user_id}). Error: {result.get('error')}"
        )

    return result


def dm_channel_by_id(
    channel_id: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Sends a Slack direct message from the bot account to a given user or to a given
    Slack channel.

    Arguments:
        `channel_id` (`str`): The Slack ID of the user or the channel to send the message to
        `text` (`str`): The text of the message
        `blocks` (`Optional[List[Dict[str, Any]]]`): The message formatted as
            Slack blocks

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    logger.debug(f"Attempting chat_postMessage to {channel_id}.")

    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            text=text,
            blocks=blocks or None,
        )

        if res.get("ok"):
            logger.info(f"Message sent successfully to {channel_id} (ts: {res['ts']}).")
            return {"ok": True, "channel": res["channel"], "ts": res["ts"]}

        error_reason = res.get("error", "unknown_error")
        logger.error(f"Slack API returned error for {channel_id}: {error_reason}")
        return {"ok": False, "error": error_reason}
    except Exception as e:
        error_msg = str(e)

        if "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")
        elif "channel_not_found" in error_msg:
            logger.error(
                f"Target channel {channel_id} not found. Bot may not be in channel or ID is invalid."
            )
        elif "is_archived" in error_msg:
            logger.warning(
                f"Target channel {channel_id} is archived. Message not sent."
            )
        else:
            logger.exception(
                f"Unexpected crash in chat_postMessage to {channel_id}: {error_msg}"
            )

        return {"ok": False, "error": error_msg}


def reply_to_slack_message(
    channel_id: str,
    thread_ts: str,
    text: str,
    blocks: Optional[List[Dict[str, Any]]] = None,
    reply_broadcast: bool = False,
) -> Dict[str, Any]:
    """
    Replies to an existing Slack message or thread.

    Arguments:
        `channel_id` (`str`): The Slack ID of the channel containing the message
        `thread_ts` (`str`): The timestamp (`ts`) of the parent message to reply to
        `text` (`str`): The text of the reply
        `blocks` (`Optional[List[Dict[str, Any]]]`): The reply formatted as Slack blocks
        `reply_broadcast` (`bool`): If `True`, the reply will also be posted to the main channel

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the new message sent at
    """
    logger.debug(f"Attempting threaded reply in {channel_id} to parent {thread_ts}.")

    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks or None,
            reply_broadcast=reply_broadcast,
        )

        if res.get("ok"):
            logger.info(
                f"Threaded reply sent to {channel_id} (Parent: {thread_ts}, Reply: {res['ts']}, Broadcast: {reply_broadcast})."
            )
            return {"ok": True, "channel": res["channel"], "ts": res["ts"]}

        error_reason = res.get("error", "unknown_error")
        logger.error(f"Slack API rejected thread reply in {channel_id}: {error_reason}")
        return {"ok": False, "error": error_reason}
    except Exception as e:
        error_msg = str(e)

        if "thread_not_found" in error_msg:
            logger.error(
                f"Failed to reply: Parent thread {thread_ts} no longer exists in {channel_id}."
            )
        elif "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")
        elif "is_archived" in error_msg:
            logger.warning(f"Cannot reply: Channel {channel_id} is archived.")
        else:
            logger.exception(
                f"Unexpected crash while replying to thread {thread_ts} in {channel_id}: {error_msg}"
            )

        return {"ok": False, "error": error_msg}


def add_user_to_channel(user_id: str, channel_id: str) -> tuple[bool, str | None]:
    """
    Adds a Slack user to a specified channel. The bot user must be in the channel.

    Arguments:
        `user_id` (`str`): The user's Slack ID
        `channel_id` (`str`): The ID of the channel to add the user to
    Returns:
        tuple (`bool`, `str | None`): Whether the operation was successful and an error message if not
    """
    logger.debug(f"Adding user {user_id} to channel {channel_id}.")

    access = can_bot_access_channel(channel_id=channel_id)
    if access == False:
        logger.debug(f"Bot cannot access channel {channel_id}")
        return False, f"Bot cannot access channel {channel_id}"

    try:
        res = app.client.conversations_invite(channel=channel_id, users=[user_id])
        logger.info(f"Successfully added user {user_id} to channel {channel_id}.")
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "already_in_channel" in error_msg:
            logger.info(f"User {user_id} already in channel {channel_id}. Continuing.")
            return True, None  # Treat as success if they are already there
        elif "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")

        logger.error(f"Error adding user {user_id} to {channel_id}: {e}")
        return False, error_msg


def remove_user_from_channel(user_id: str, channel_id: str) -> tuple[bool, str | None]:
    """
    Removes a Slack user from a specified channel. The bot user must be in the channel.

    Arguments:
        `user_id` (`str`): The user's Slack ID
        `channel_id` (`str`): The ID of the channel to remove the user from
    Returns:
        tuple (`bool`, `str | None`): Whether the operation was successful and an error message if not
    """
    logger.debug(f"Removing user {user_id} from channel {channel_id}.")

    access = can_bot_access_channel(channel_id=channel_id)
    if access == False:
        logger.debug(f"Bot cannot access channel {channel_id}")
        return False, f"Bot cannot access channel {channel_id}"

    try:
        res = app.client.conversations_kick(channel=channel_id, user=user_id)
        logger.info(f"Successfully removed user {user_id} from channel {channel_id}.")
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "not_in_channel" in error_msg:
            logger.info(f"User {user_id} not in channel {channel_id}. Continuing.")
            return True, None  # Treat as success if they are already not in channel
        elif "restricted_action" in error_msg:
            logger.warning(
                f"Skipped removal: User {user_id} is likely an Admin or the channel {channel_id} is restricted. Bots cannot kick admins."
            )
            return True, None  # Treat this as success
        elif "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")
        else:
            logger.exception(f"Error removing user {user_id} from {channel_id}: {e}")

        return False, error_msg


# HELPERS


def _lookup_user_id_by_email(email: str) -> Optional[str]:
    """
    Get a user's Slack ID from their associated account email. First tries a local cache,
    then resorts to Slack API.

    Arguments:
        `email` (`str`): The IMC email of the user
    Returns:
        `str`: The user's Slack ID, else `None`
    """
    logger.debug(f"Looking for Slack ID for user {email}")

    if email in _user_id_cache:
        user_id = _user_id_cache[email]
        logger.info(f"Mapped {email} to {user_id} via cache.")
        return user_id

    try:
        logger.debug(f"Querying Slack API for email {email}.")
        user_id = app.client.users_lookupByEmail(email=email)["user"]["id"]

        _user_id_cache[email] = user_id
        logger.info(f"Successfully mapped {email} to Slack ID {user_id}")
        return user_id
    except Exception as e:
        error_msg = str(e)

        if "users_not_found" in error_msg:
            logger.warning(f"Lookup failed: No Slack account found for {email}")
        elif "ratelimited" in error_msg:
            logger.critical(f"SLACK RATE LIMIT HIT: {error_msg}")
        else:
            logger.exception(
                f"Unexpected Slack API error during lookup for {email}: {error_msg}"
            )

        return None
