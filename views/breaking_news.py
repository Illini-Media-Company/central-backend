from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from util.security import restrict_to
import requests

from db.story import Story, add_story, get_recent_stories

from util.stories import get_title_from_url

from flask_login import login_required
from db.story import add_story, get_recent_stories
from db.social_post import SocialPlatform
from util.social_posts import post_to_reddit, post_to_twitter
from util.stories import get_published_url, get_title_from_url
from util.slackbot import app
from constants import SLACK_BOT_TOKEN

DI_COPYING_ID = "C06LYTJ5N6S"

COPYING_MESSAGE = [
    {"type": "divider"},
    {
        "type":"header",
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
            "text": ":white_check_mark:*BREAKING NEWS HAS BEEN PUBLISHED*:white_check_mark:",
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
            "text": ":rotating_light:*BREAKING NEWS IS READY FOR EDITING*:rotating_light:",
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



breaking_routes = Blueprint("breaking_routes", __name__, url_prefix="/breaking")

@breaking_routes.route("/dashboard")
@login_required
def dashboard():
    stories = get_recent_stories(10)

    return render_template('breaking.html', stories=stories)


@breaking_routes.route('/submit', methods=['POST'])
def submit_story():
    url = get_published_url(request.form["url"].partition("?")[0])
    title = get_title_from_url(url)

    post_to_reddit = request.form.get('post_to_reddit') == '1'
    post_to_twitter = request.form.get('post_to_twitter') == '1'
    created_by = current_user.name
    slack_message_id = ''

    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to fetch webpage"
    
    if not post_to_twitter and not post_to_reddit:
        result = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            username="IMC Breaking News Bot",
            channel=DI_COPYING_ID,
            blocks=COPYING_MESSAGE,
            text="BREAKING NEWS ALERT"
        )
        slack_message_id = result["ts"]
    
    new_story = add_story(
        title=title,
        url=url,
        post_to_reddit=post_to_reddit,
        post_to_twitter=post_to_twitter,
        slack_message_id=slack_message_id,
        created_by=created_by
    )
    return "success", 200

#Publish to social media
''' def is_valid_url(url):
    url_pattern = re.compile(r"^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$", re.IGNORECASE)
    return bool(re.match(url_pattern, url))

def validate_story(url):
    if len(url) < 1:
        return None, ("ERROR: Empty URL.", 400)
    if not is_valid_url(url):
        return None, ("ERROR: Invalid URL.", 400)
    title = get_title_from_url(url)
    if title is None:
        return None, ("ERROR: Story cannot be found.", 400)
    return title, None

print('start')
print(validate_story('https://dailyillini.com/wp-admin/post.php?post=338488&action=edit'))
print(validate_story('https://dailyillini.com/life_and_culture-stories/2024/04/22/marching-illini-sousaphones-take-on-illinois-5k/'))
print('end')

'''


'''@breaking_routes.route('/publish_reddit', methods= ['POST'])
@login_required
def create_reddit_post():
    url = get_published_url(request.form["url"].partition("?")[0])
    title = get_title_from_url(url)
    url, err = post_to_reddit(title, url)
    if err:
        return err
    else:
         return jsonify({"title": title, "message": "Published to Reddit."}), 200
    

print('start')
print(get_title_from_url(get_published_url('https://dailyillini.com/wp-admin/post.php?post=338488&action=edit')))
print('end')
@breaking_routes.route("/publish_twitter", methods=["POST"])
@login_required

def create_tweet():
    url = get_published_url(request.form["url"].partition("?")[0])
    title = get_title_from_url(url)
    url, err = post_to_twitter(title, url)
    if err:
        return err
    else:
         return jsonify({"title": title, "message": "Published to Twitter."}), 200
    
'''



    

# Start of the Slack Button Code
@app.action("breaking_button")
def breaking_button(ack, logger, body):
    ack()
    logger.info(body)
    ts = body["message"]["ts"]
    url = story_url_from_ts(10, ts)
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