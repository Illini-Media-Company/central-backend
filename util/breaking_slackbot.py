from flask import Blueprint, redirect, request, url_for
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from util.slackbot import app
from flask_login import login_required
from db.story import add_story, get_recent_stories
from util.stories import get_published_url, get_title_from_url

from constants import ENV, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET
from util.security import csrf

DI_COPYING_ID = "C06LYTJ5N6S"

COPYING_MESSAGE = [
    {"type": "divider"},
    {
        "type":"header",
        "text": {
            "type": "plain_text",
            "text": ":rotating_light:*BREAKING NEWS HAS BEEN POSTED*:rotating_light:",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Check if the story is published",
        }
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Check if Published",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "breaking_button",
            },
        ],
    },
    {"type": "divider"},
]
POSTED_SUCCESFULLY = [
    {"type": "divider"},
    {
        "type":"header",
        "text": {
            "type": "plain_text",
            "text": ":rotating_light:*BREAKING NEWS HAS BEEN POSTED*:rotating_light:",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":white_check_mark: Story has been published :white_check_mark:",
        }
    },
    {"type": "divider"},
]
NOT_POSTED = [
    {"type": "divider"},
    {
        "type":"header",
        "text": {
            "type": "plain_text",
            "text": ":rotating_light:*BREAKING NEWS HAS BEEN POSTED*:rotating_light:",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Check if the story is published",
        }
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":x: Story has not been published :x:",
                    "emoji": True,
                },
                "value": "click_me_123",
                "action_id": "breaking_button",
            },
        ],
    },
    {"type": "divider"},
]

breaking_news_routes = Blueprint(
    "breaking_news_routes", __name__, url_prefix="/breaking" 
)

@breaking_news_routes.route("/post", methods=["POST"])
@login_required
def post_message():
    story_url = request.form["story_url"]
    story_title = get_title_from_url(story_url)
    result = app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="IMC Notification Bot",
        channel=DI_COPYING_ID,
        blocks=COPYING_MESSAGE,
        text="BREAKING NEWS ALERT"
    )

    add_story(story_title, story_url, False, False, result["ts"], "User")
    return "success", 200

@app.action("breaking_button")
def breaking_button(ack, logger, body):
    ack()
    logger.info(body)
    ts = body["message"]["ts"]

    url = story_url_from_ts(20, ts)
    if (url == None):
        print("story is no longer recent")
    elif (get_published_url(url) == None):
        app.client.chat_update(
            token=SLACK_BOT_TOKEN, 
            channel=DI_COPYING_ID,
            ts=ts,
            blocks=NOT_POSTED,
            text="STORY HAS NOT BEEN POSTED",
        )
    elif (get_published_url(url) != None):
        app.client.chat_update(
            token=SLACK_BOT_TOKEN, 
            channel=DI_COPYING_ID,
            ts=ts,
            blocks=POSTED_SUCCESFULLY,
            text="STORY HAS BEEN POSTED",
        )


def story_url_from_ts(count, ts):
    stories = get_recent_stories(count)
    for i in stories:
        if (i["slack_message_id"] == ts):
            return i["url"]
    return None