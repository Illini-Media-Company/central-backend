"""
This file defines the helper functions and error codes for the Employee Management System.
Also defines functions responsible for sending onboarding and offboarding emails.

Created by Jacob Slabosz on Feb. 3, 2026
Last modified Feb. 16, 2026
"""

import base64
import logging
from flask import render_template
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from util.security import get_admin_creds
from util.slackbots.general import (
    dm_channel_by_id,
    reply_to_slack_message,
    add_user_to_channel,
    remove_user_from_channel,
)

logger = logging.getLogger(__name__)

# ERROR CODES ##################################################################
EUSERDNE = -1  # User does not exist
EEMPDNE = -2  # EmployeeCard does not exist
EPOSDNE = -3  # PositionCard does not exist
ERELDNE = -4  # EmployeePositionRelation does not exist

EMISSING = -5  # Required field is missing
EEXCEPT = -6  # Unknown exception occurred during operation
EEXISTS = -7  # EmployeeCard or EmployeePositionRelation already exists
ESUPREP = -8  # Error setting supervisor(s) or direct report(s)
EGROUP = -9  # Google Groups update failed
EGROUPDNE = -10  # Google Group email does not exist or is invalid
ESLACKDNE = -11  # Slack channel ID does not exist or is not accessible
ESLACK = -12  # Slack channels update failed

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

ONBOARDING_STARTED_TEXT = "Onboarding started for {name}"
ONBOARDING_CARD_CREATED_TEXT = "EmployeeCard created."
ONBOARDING_CARD_CREATED_BLOCKS = [
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": ":white_check_mark: Employee Card created"},
    }
]
ONBOARDING_EMAIL_SENT_TEXT = "Onboarding email sent."
ONBOARDING_EMAIL_SENT_BLOCKS = [
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": ":white_check_mark: Onboarding email sent"},
    }
]
ONBOARDING_INFO_RECEIVED_TEXT = "Employee completed onboarding form."
ONBOARDING_INFO_RECEIVED_BLOCKS = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":white_check_mark: Employee completed onboarding form.",
        },
    }
]
ONBOARDING_GOOGLE_CREATED_TEXT = "Google account created."
ONBOARDING_GOOGLE_CREATED_BLOCKS = [
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": ":white_check_mark: Google account created"},
    }
]
ONBOARDING_GOOGLE_FAILED_TEXT = "Google account creation failed."
ONBOARDING_GOOGLE_FAILED_BLOCKS = [
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": ":x: Google account creation failed"},
    },
    {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Please manually create the user's Google account and update their card in EMS with their IMC email.",
            }
        ],
    },
]
ONBOARDING_COMPLETE_TEXT = "Onboarding for {name} complete"

ONBOARDING_EMAIL_TEXT_BODY = """Hi {first_name},

    Welcome to the Illini Media Company team! Please fill out your onboarding form using the link below::

    {onboarding_url}

    Note: This form is best viewed on desktop.

    After completing the form, please keep an eye out for future communications from us, which 
    will be via Slack. If you have any issues accessing the form or have any questions regarding 
    the process, reach out to helpdesk@illinimedia.com.

    Illini Media Company"""


def send_onboarding_email(to_email: str, first_name: str, onboarding_url: str) -> dict:
    """
    Sends the onboarding email via Gmail API using admin/service-account credentials.
    Validates required inputs, builds both plain-text and HTML email bodies, and sends
    from the configured sender (onboarding@illinimedia.com). Returns {"ok": True, "message_id": ...}
    on success, or {"ok": False, "error": ...} if the Gmail API call fails.
    """
    if not to_email:
        raise ValueError("to_email is required")
    if not onboarding_url:
        raise ValueError("onboarding_url is required")

    creds = get_admin_creds(GMAIL_SEND_SCOPE)

    # Impersonate email address
    sender_email = "onboarding@illinimedia.com"
    if isinstance(creds, service_account.Credentials):
        creds = creds.with_scopes([GMAIL_SEND_SCOPE]).with_subject(sender_email)

    service = build("gmail", "v1", credentials=creds)

    subject = "[Action Required] Complete Your Illini Media Onboarding"
    text_body = ONBOARDING_EMAIL_TEXT_BODY.format(
        first_name=first_name, onboarding_url=onboarding_url
    )

    html_body = render_template(
        "employee_management/ems_onboarding_email.html",
        first_name=first_name,
        onboarding_url=onboarding_url,
    )

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "message_id": sent.get("id")}
    except HttpError as e:
        return {"ok": False, "error": str(e)}


def get_ems_brand_image_url(brand: str) -> str:
    """
    Returns the image URL for a given brand.

    Args:
        brand (str): The brand name.

    Returns:
        str: The image URL for the brand.
    """
    brand_images = {
        "Chambana Eats": "/static/brandmarks/background/96x96/CE_SquareIcon.png",
        "The Daily Illini": "/static/brandmarks/background/96x96/DI_SquareIcon.png",
        "Illini Content Studio": "/static/brandmarks/background/96x96/ICS_SquareIcon.png",
        "Illio": "/static/brandmarks/background/96x96/Illio_SquareIcon.png",
        "IMC": "/static/brandmarks/background/96x96/IMC_SquareIcon.png",
        "WPGU": "/static/brandmarks/background/96x96/WPGU_SquareIcon.png",
    }
    return brand_images.get(brand, "/static/defaults/position_profile.png")


#################################################################################
# SLACK FUNCTIONS


def slack_dm_onboarding_started(channel_id: str, employee_name: str) -> dict:
    """
    Sends the initial onboarding Slack message to the specified channel.

    Arguments:
        `channel_id` (`str`): The Slack `channel_id` to send the message to
        `employee_name` (`str`): The name of the employee being onboarded

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    text = ONBOARDING_STARTED_TEXT.format(name=employee_name)
    blocks = get_onboarding_started_blocks(employee_name)
    res = dm_channel_by_id(channel_id=channel_id, text=text, blocks=blocks)
    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    original_ts = res["ts"]

    # Send first follow up
    text = ONBOARDING_CARD_CREATED_TEXT
    blocks = ONBOARDING_CARD_CREATED_BLOCKS
    res = reply_to_slack_message(
        channel_id=channel_id, thread_ts=original_ts, text=text, blocks=blocks
    )
    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    # Send second follow up
    text = ONBOARDING_EMAIL_SENT_TEXT
    blocks = ONBOARDING_EMAIL_SENT_BLOCKS
    res = reply_to_slack_message(
        channel_id=channel_id, thread_ts=original_ts, text=text, blocks=blocks
    )
    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    return {"ok": True, "channel": res["channel"], "ts": res["ts"]}


def slack_dm_info_received(channel_id: str, thread_ts: str) -> dict:
    """
    Sends a message as a reply to the original notifying that the employee has completed the form.

    Arguments:
        `channel_id` (`str`): The Slack `channel_id` of the original message
        `thread_ts` (`str`): The timestamp (`ts`) of the parent message to reply to

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    text = ONBOARDING_INFO_RECEIVED_TEXT
    blocks = ONBOARDING_INFO_RECEIVED_BLOCKS
    res = reply_to_slack_message(
        channel_id=channel_id, thread_ts=thread_ts, text=text, blocks=blocks
    )

    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    return {"ok": True, "channel": res["channel"], "ts": res["ts"]}


def slack_dm_google_created(channel_id: str, thread_ts: str) -> dict:
    """
    Sends a message as a reply to the original notifying that the Google account was created.

    Arguments:
        `channel_id` (`str`): The Slack `channel_id` of the original message
        `thread_ts` (`str`): The timestamp (`ts`) of the parent message to reply to

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    text = ONBOARDING_GOOGLE_CREATED_TEXT
    blocks = ONBOARDING_GOOGLE_CREATED_BLOCKS
    res = reply_to_slack_message(
        channel_id=channel_id, thread_ts=thread_ts, text=text, blocks=blocks
    )

    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    return {"ok": True, "channel": res["channel"], "ts": res["ts"]}


def slack_dm_google_failed(channel_id: str, thread_ts: str, error: str) -> dict:
    """
    Sends a message as a reply to the original notifying that the Google account creation failed.

    Arguments:
        `channel_id` (`str`): The Slack `channel_id` of the original message
        `thread_ts` (`str`): The timestamp (`ts`) of the parent message to reply to
        `error` (`str`): The error message to include in the Slack message

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    text = ONBOARDING_GOOGLE_FAILED_TEXT
    blocks = get_google_failed_blocks(error=error)
    res = reply_to_slack_message(
        channel_id=channel_id,
        thread_ts=thread_ts,
        text=text,
        blocks=blocks,
        reply_broadcast=True,
    )

    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    return {"ok": True, "channel": res["channel"], "ts": res["ts"]}


def slack_dm_onboarding_complete(
    channel_id: str,
    thread_ts: str,
    employee_name: str,
    ems_url: str,
    slack_id: str | None = None,
) -> dict:
    """
    Sends a message as a broadcasted reply to the original notifying that employee's
        onboarding is complete.

    Arguments:
        `channel_id` (`str`): The Slack `channel_id` of the original message
        `thread_ts` (`str`): The timestamp (`ts`) of the parent message to reply to
        `employee_name` (`str`): The name of the employee being onboarded
        `slack_id` (`str`): The Slack ID of the employee being onboarded
        `ems_url` (`str`): The URL to view/edit the employee in EMS

    Returns:
        `dict`:
            * `ok` (`bool`): `True` if the message sent successfully, `False` otherwise
            * `error` (`str`): (If `ok` = `False`) The error that occurred
            * `channel` (`str`): (If `ok` = `True`) The channel the message sent to
            * `ts` (`str`): (If `ok` = `True`) The timestamp the message sent at
    """
    text = ONBOARDING_COMPLETE_TEXT.format(name=employee_name)
    blocks = get_onboarding_complete_blocks(slack_id=slack_id, url=ems_url)
    res = reply_to_slack_message(
        channel_id=channel_id,
        thread_ts=thread_ts,
        text=text,
        blocks=blocks,
        reply_broadcast=True,
    )

    # Validate
    if not isinstance(res, dict):
        return {"ok": False, "error": "Unknown fatal error."}
    if not res.get("ok"):
        return {"ok": False, "error": f"{res['error']}"}

    return {"ok": True, "channel": res["channel"], "ts": res["ts"]}


def get_onboarding_started_blocks(name: str) -> dict:
    """
    Creates the blocks used for the initial onboarding message.

    Arguments:
        `name` (`str`): The name of the employee being onboarded

    Returns:
        `dict`: The Slack message as blocks
    """
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Onboarding began for *{name}*"},
        }
    ]


def get_onboarding_complete_blocks(
    url: str,
    slack_id: str | None = None,
) -> dict:
    """
    Creates the blocks used for the initial onboarding message. If `slack_id`
    if `None`, will return blocks for an overridden onboarding without Slack access.

    Arguments:
        `slack_id` (`str`): The Slack ID employee being onboarded
        `url` (`str`): The URL to view/edit the employee in EMS

    Returns:
        `dict`: The Slack message as blocks
    """
    if slack_id is None:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: Onboarding manually overridden (Complete).",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Use <{url}|this link> to assign the employee to a position which \
                        will automatically add them to the correct Slack channels and Google Groups. \
                        Note that the employee's Slack and Google accounts have not been verified.",
                },
            },
        ]
    else:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: Onboarding complete for <@{slack_id}>.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Use <{url}|this link> to assign the employee to a position which will automatically add them to the correct Slack channels and Google Groups.",
                },
            },
        ]


def get_google_failed_blocks(error: str) -> dict:
    """
    Creates the blocks used for the initial onboarding message.

    Arguments:
        `error` (`str`): The error message to include in the Slack message

    Returns:
        `dict`: The Slack message as blocks
    """
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":x: Google account creation failed"},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{error}```"}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Please manually create the user's Google account and update their card in EMS with their IMC email.",
                }
            ],
        },
    ]


def update_slack_channels(
    user_id: str, old_channels: list[str], new_channels: list[str]
) -> tuple[bool, str | None]:
    """
    Updates a user's Slack channel memberships based on the channels the user was previously in
        and the channels they should now be in. Ignores all channels that are not included in either list.

    Arguments:
        `user_id` (`str`): The Slack ID of the user to update
        `old_channels` (`list[str]`): List of IDs for the channels the user is/was in
        `new_channels` (`list[str]`): List of IDs for the channels the user should be in
    Returns:
        tuple (`bool`, `str | None`): Whether the operation was successful and an error message if not
    """
    remove_from_channels = list(set(old_channels) - set(new_channels))
    add_to_channels = list(set(new_channels) - set(old_channels))

    # Logging
    logger.debug(f"Removing {user_id} from channels: {remove_from_channels}")
    logger.debug(f"Adding {user_id} to channels: {add_to_channels}")

    try:
        if remove_from_channels:
            for channel in remove_from_channels:
                # Remove user from channel
                success, error = remove_user_from_channel(
                    user_id=user_id, channel_id=channel
                )
                if not success:
                    logger.error(f"Error removing user from channel {channel}: {error}")
                    return False, error
        if add_to_channels:
            for channel in add_to_channels:
                # Add user to channel
                success, error = add_user_to_channel(
                    user_id=user_id, channel_id=channel
                )
                if not success:
                    logger.error(f"Error adding user to channel {channel}: {error}")
                    return False, error
    except Exception as e:
        logger.exception(f"Unexpected crash while updating Slack channels: {e}")
        return False, str(e)

    return True, None


#################################################################################
