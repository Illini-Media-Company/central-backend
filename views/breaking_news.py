from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from util.security import restrict_to
from util.slackbots.copy_editing import notify_copy_editor

from db.story import Story, add_story, get_recent_stories

from flask_login import login_required
from db.story import add_story, get_recent_stories
from db.social_post import SocialPlatform
from util.stories import get_published_url
from util.slackbots._slackbot import app
from constants import SLACK_BOT_TOKEN
from util.security import csrf

DI_COPYING_ID = "C50E93LJG"
POSTED_SUCCESSFULLY = [
    {"type": "divider"},
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":white_check_mark:*BREAKING NEWS HAS BEEN PUBLISHED*:white_check_mark:",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":white_check_mark: Story has been published :white_check_mark:",
        },
    },
    {"type": "divider"},
]

breaking_routes = Blueprint("breaking_routes", __name__, url_prefix="/breaking")


@breaking_routes.route("/dashboard")
@login_required
def dashboard():
    stories = get_recent_stories(10)
    return render_template("breaking.html", stories=stories)


@breaking_routes.route("/submit", methods=["POST"])
@csrf.exempt
def submit_story():
    url = request.form["url"] + "&action=edit"
    title = url

    post_to_reddit = True if request.form["post_to_reddit"] == "true" else False
    post_to_twitter = True if request.form["post_to_twitter"] == "true" else False
    created_by = current_user.name
    slack_message_id = ""
    result = app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        channel=DI_COPYING_ID,
        blocks=[
            {"type": "divider"},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":rotating_light:*BREAKING NEWS IS READY FOR EDITING*:rotating_light:",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "<!channel> Check if the story is published: \n" + url,
                },
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
        ],
        text="BREAKING NEWS ALERT",
    )
    slack_message_id = result["ts"]

    notify_copy_editor(url, True)

    new_story = add_story(
        title=title,
        url=url,
        post_to_reddit=post_to_reddit,
        post_to_twitter=post_to_twitter,
        slack_message_id=slack_message_id,
        created_by=created_by,
    )

    return "success", 200


# Start of the Slack Button Code
@app.action("breaking_button")
def breaking_button(ack, logger, body):
    ack()
    logger.info(body)
    ts = body["message"]["ts"]
    url = story_url_from_ts(10, ts)
    if url == None:
        print("story is no longer recent")
    elif get_published_url(url) == None:
        app.client.chat_update(
            token=SLACK_BOT_TOKEN,
            channel=DI_COPYING_ID,
            ts=ts,
            blocks=[
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":rotating_light:*BREAKING NEWS IS READY FOR EDITING*:rotating_light:",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "<!channel> Check if the story is published: \n" + url,
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": ":x: Not Published :x:",
                                "emoji": True,
                            },
                            "value": "click_me_123",
                            "action_id": "breaking_button",
                        },
                    ],
                },
                {"type": "divider"},
            ],
            text="STORY HAS NOT BEEN POSTED",
        )
    elif get_published_url(url) != None:
        app.client.chat_update(
            token=SLACK_BOT_TOKEN,
            channel=DI_COPYING_ID,
            ts=ts,
            blocks=POSTED_SUCCESSFULLY,
            text="STORY HAS BEEN POSTED",
        )


def story_url_from_ts(count, ts):
    stories = get_recent_stories(count)
    for i in stories:
        if i["slack_message_id"] == ts:
            return i["url"]
    return None
