from threading import Thread

from flask import request
from slack_bolt import App
import logging
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler

from constants import (
    ENV,
    SLACK_BOT_TOKEN,
    SLACK_APP_TOKEN,
    SLACK_SIGNING_SECRET,
)
from util.security import csrf
from db.user import add_user, get_user_entity
from util.ask_oauth import get_valid_access_token
from util.discovery_engine import (
    answer_query,
    extract_answer_and_citations,
    extract_search_results,
    search_query,
)

from constants import (
    IMC_GENERAL_ID,
    IMC_GENERAL_TEST_ID,
    DI_ANNOUNCEMENTS_ID,
    ILLIO_ANNOUNCEMENTS_ID,
    WPGU_ANNOUNCEMENTS_ID,
    ICS_GENERAL_ID,
    IMC_ADVERTISING_ID,
    IMC_MARKETING_ID,
    IMC_FRONTDESK_ID,
    ILLIO_DESIGN_ID,
    ILLIO_PHOTO_ID,
    ILLIO_WRITER_ID,
    WPGU_ENGINEERING_ID,
    WPGU_ILLINI_DRIVE_ID,
    WPGU_MARKETING_ID,
    WPGU_MUSIC_ID,
    WPGU_NEWS_ID,
    WPGU_ON_AIR_ID,
    WPGU_PRODUCTION_ID,
    WPGU_SPORTS_ID,
)

ILLIO_MESSAGE = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Choose your section(s) within Illio Yearbook:*",
        },
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":computer: Designer",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "illio_design_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":camera_with_flash: Photographer",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "illio_photo_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":pencil: Writer",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "illio_writer_button",
            },
        ],
    },
]

ILLIO_MESSAGE_TEXT = "Choose your section(s) within Illio Yearbook"

WPGU_MESSAGE = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Choose your section(s) within WPGU 107.1 FM:*",
        },
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":gear: Engineering",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_engineering_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":basketball: Illini Drive",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_illini_drive_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":desktop_computer: Marketing",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_marketing_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":musical_note: Music",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_music_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":newspaper: News",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_news_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":studio_microphone: On-Air",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_on_air_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":level_slider: Production",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_production_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":football: Sports",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_sports_button",
            },
        ],
    },
]

WPGU_MESSAGE_TEXT = "Choose your section(s) within WPGU 107.1 FM"

IMC_MESSAGE = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Choose your department within IMC Business:*",
        },
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":newspaper: Advertising",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "imc_advertising_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":desktop_computer: Marketing",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "imc_marketing_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":pushpin: Front Desk",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "imc_frontdesk_button",
            },
        ],
    },
]

IMC_MESSAGE_TEXT = "Choose your section within IMC Business"

IMC_WELCOME_MESSAGE = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":imc: Welcome to Illini Media Company! :imc:",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "This Slack workspace serves as the communication hub for all things related to Illini Media Company. Here, you’ll be able to communicate with all your peers, both within your department and in other departments.",
        },
    },
    {"type": "divider"},
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ':bell:\nMake sure you have downloaded Slack on both your phone and laptop and have all notifications turned on. You’ll have to click "You" in the bottom right corner, then "Notifications," then change the top option to "All new messages."',
        },
    },
    {"type": "divider"},
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ':adult:\nStart by customizing your profile! All users should have their full name in their Slack profile, along with a profile photo (it doesn’t have to be you). You should also add your title. You should format your title as follows:\n\n"[Department] — [Title]"\n\nFor example, a staff photographer for IMC would input "IMC — Staff Photographer"\n\nFor those with positions in multiple departments, format it as follows:\n\n"IMC — Staff Photographer | DI — Reporter"\n\nPlease use an em dash, not a hyphen!',
        },
    },
    {"type": "divider"},
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":Calendar:\nMake sure you’ve connected Google Calendar to Slack! This allows all of your meetings to seamlessly integrate with Slack. In your list of channels, you should see the Google Calendar app at the bottom. Click that and make sure you log in!",
        },
    },
    {"type": "divider"},
    {
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": "To begin, use the buttons below to choose your IMC department. If you are in multiple, you can click multiple buttons.",
            "emoji": True,
        },
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":dailyillini: The Daily Illini :dailyillini:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "daily_illini_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":illio: Illio Yearbook :illio:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "illio_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":wpgu: WPGU 107.1 FM :wpgu:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "wpgu_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":ics: Illini Content Studio :ics:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "ics_button",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":imc: IMC Business :imc:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "imc_business_button",
            },
        ],
    },
]

IMC_WELCOME_MESSAGE_TEXT = "Welcome to Illini Media Company!"

logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


@app.event("app_mention")
def handle_mention(event, say):
    say("👋 Hey!")


@app.event("member_joined_channel")
def member_joined_channel(event):
    user_id = event["user"]
    channel_id = event["channel"]
    print("\nUser " + user_id + " joined channel " + channel_id)
    print(channel_id + " Here")
    if channel_id in [IMC_GENERAL_ID, IMC_GENERAL_TEST_ID]:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=directMessage,
            blocks=IMC_WELCOME_MESSAGE,
            text=IMC_WELCOME_MESSAGE_TEXT,
        )
        print("   Message sent.\n")
    elif channel_id == ILLIO_ANNOUNCEMENTS_ID:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=directMessage,
            blocks=ILLIO_MESSAGE,
            text=ILLIO_MESSAGE_TEXT,
        )
        print("   Message sent.\n")
    elif channel_id == WPGU_ANNOUNCEMENTS_ID:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=directMessage,
            blocks=WPGU_MESSAGE,
            text=WPGU_MESSAGE_TEXT,
        )
        print("   Message sent.\n")
    else:
        print("  Not a channel of interest. No messages sent.")


def buttonWrapper(buttonName, buttonHashtag, channel, userName, userId):
    print("User " + userName + " clicked " + buttonName + " Button")

    try:
        app.client.conversations_invite(
            token=SLACK_BOT_TOKEN,
            channel=channel,
            users=userId,
            force=True,
        )
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=userId,
            text=f"<@{userId}>, you have been added to <#{channel}>.",
        )
        print("  User " + userName + " has been added to " + buttonHashtag + "\n")
    except Exception as e:
        print(e)
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=userId,
            text=f"<@{userId}>, you are already in <#{channel}>.",
        )


# Executed if a user clicks the "The Daily Illini" button
@app.action("daily_illini_button")
def daily_illini_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "Daily Illini", "#di_announcements", DI_ANNOUNCEMENTS_ID, userName, userId
    )


# Executed if a user clicks the "WPGU 107.1 FM" button
@app.action("wpgu_button")
def wpgu_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "WPGU", "#wpgu_announcements", WPGU_ANNOUNCEMENTS_ID, userName, userId
    )


# Executed if a user clicks the "Illio Yearbook" button
@app.action("illio_button")
def illioButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "Illio", "#illio_announcements", ILLIO_ANNOUNCEMENTS_ID, userName, userId
    )


# Executed if a user clicks the "Illini Content Studio" button
@app.action("ics_button")
def ics_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "Illini Content Studio", "#ics_general", ICS_GENERAL_ID, userName, userId
    )


# Executed if a user clicks the "IMC Business" button
@app.action("imc_business_button")
def imc_business_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    print("User " + userName + " clicked IMC Business button")

    # direct message the user
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        channel=userId,
        blocks=IMC_MESSAGE,
        text=IMC_MESSAGE_TEXT,
    )

    print("    Section choose message sent.\n")


# IMC Business buttons


# Executed if a user clicks the IMC Advertising button
@app.action("imc_advertising_button")
def imc_advertising_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "IMC Advertising", "#imc_advertising", IMC_ADVERTISING_ID, userName, userId
    )


# Executed if a user clicks the IMC Marketing button
@app.action("imc_marketing_button")
def imc_marketing_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("IMC Marketing", "#imc_marketing", IMC_MARKETING_ID, userName, userId)


# executed if a user clicks the IMC Front Desk button
@app.action("imc_frontdesk_button")
def imc_frontdesk_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "IMC Front Desk", "#imc_frontdesk", IMC_FRONTDESK_ID, userName, userId
    )


# Illio buttons


# Executed if a user clicks the Illio Design button
@app.action("illio_design_button")
def illio_design_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Design", "#illio_design", ILLIO_DESIGN_ID, userName, userId)


# Executed if a user clicks the Illio Photo button
@app.action("illio_photo_button")
def illio_photo_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Photo", "#illio_photo", ILLIO_PHOTO_ID, userName, userId)


# Executed if a user clicks the Illio Writer button
@app.action("illio_writer_button")
def illio_writer_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Writer", "#illio_writer", ILLIO_WRITER_ID, userName, userId)


# WPGU buttons


# Executed if a user clicks the WPGU Engineering button
@app.action("wpgu_engineering_button")
def wpgu_engineering_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "WPGU Engineering", "#wpgu_engineering", WPGU_ENGINEERING_ID, userName, userId
    )


# Executed if a user clicks the WPGU IlliniDriveButton
@app.action("wpgu_illini_drive_button")
def wpgu_illini_drive_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "WPGU Illini Drive",
        "#wpgu_illini-drive",
        WPGU_ILLINI_DRIVE_ID,
        userName,
        userId,
    )


# Executed if a user clicks the WPGU Marketing button
@app.action("wpgu_marketing_button")
def wpgu_marketing_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "WPGU Marketing", "#wpgu_marketing", WPGU_MARKETING_ID, userName, userId
    )


# Executed if a user clicks on the WPGU Music button
@app.action("wpgu_music_button")
def wpgu_music_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Music", "#wpgu_music", WPGU_MUSIC_ID, userName, userId)


# executed if a user clicks the WPGU News Button
@app.action("wpgu_news_button")
def wpgu_news_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU News", "#wpgu_news", WPGU_NEWS_ID, userName, userId)


# Executed if a user clicks the WPGU On-Air button
@app.action("wpgu_on_air_button")
def wpgu_on_air_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU On-Air", "#wpgu_on-air", WPGU_ON_AIR_ID, userName, userId)


# Executed if a user clicks the WPGU Production button
@app.action("wpgu_production_button")
def wpgu_production_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper(
        "WPGU Production", "#wpgu_production", WPGU_PRODUCTION_ID, userName, userId
    )


# Executed if a user clicks the WPGU Sports button
@app.action("wpgu_sports_button")
def wpgu_sports_button(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Sports", "#wpgu_sports", WPGU_SPORTS_ID, userName, userId)


def start_slack(flask_app):
    logging.info(f"Initializing Slack app in {ENV} mode.")

    if ENV == "prod":
        handler = SlackRequestHandler(app)

        @flask_app.route("/slack/events", methods=["POST"])
        @csrf.exempt
        def slack_events():
            return handler.handle(request)

        logger.info("Slack events listener registered at /slack/events")

    elif SLACK_APP_TOKEN is not None:
        try:
            handler = SocketModeHandler(app, SLACK_APP_TOKEN)
            handler.connect()

            logger.info("Slack app connected via Socket Mode (Development only).")
        except Exception as e:
            logger.exception(f"Failed to initialize Slack Socket mode: {str(e)}")

    else:
        logger.warning(
            "Slack initialization skipped: No App Token found and ENV is not 'prod'."
        )
