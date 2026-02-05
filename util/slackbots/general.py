"""
Includes general use Slackbot functions.

Created on Feb. 4, 2026 by Jacob Slabosz
Last modified Feb. 4, 2026
"""

from constants import SLACK_BOT_TOKEN
from util.slackbots._slackbot import app


def can_bot_access_channel(channel_id: str) -> bool:
    """
    Checks if a channel exists and if the acting bot is in it.

    Arguments:
        `channel_id` (`str`): The ID of the channel

    Returns:
        `bool`: `True` if the channel exists and is accessible, `False` otherwise
    """
    try:
        print(channel_id)
        res = app.client.conversations_info(channel=channel_id)

        if res.get("ok"):
            # Check if the bot is in the channel
            return res["channel"].get("is_member", False)
    except Exception as e:
        print(f"Error checking Slack channel {channel_id}: {e}")

        return False
