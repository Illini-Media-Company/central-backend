import re

from flask import Blueprint, render_template, request
from flask_login import login_required
import praw

from db.story import (
    get_all_stories,
    get_recent_stories,
    add_story,
    delete_all_stories,
    check_limit,
)
from util.constants import (
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    SUBREDDIT,
)
from util.security import restrict_to


socials_routes = Blueprint("socials_routes", __name__, url_prefix="/socials")


@socials_routes.route("/dashboard")
@login_required
def dashboard():
    stories = get_recent_stories(10)
    return render_template("socials.html", stories=stories)


@socials_routes.route("", methods=["GET"])
@login_required
def list_stories():
    return get_all_stories()


@socials_routes.route("/illinois-app", methods=["POST"])
@login_required
@restrict_to(["editors"])
def create_push_notification():
    if check_limit():
        return "ERROR: 3 push notifications have been sent in the past 7 days.", 403
    title = request.form["title"]
    url = request.form["url"]
    err = validate_story(title, url)
    if err:
        return err, 400

    add_story(title=title, url=url, posted_to="Illinois app")
    return "Illinois App push notification sent.", 200


@socials_routes.route("/reddit", methods=["POST"])
@login_required
@restrict_to(["editors", "social"])
def create_reddit_post():
    title = request.form["title"]
    url = request.form["url"]
    err = validate_story(title, url)
    if err:
        return err, 400

    try:
        reddit_url = post_to_reddit(title, url)
    except Exception as e:
        return str(e), 500

    add_story(title=title, url=reddit_url, posted_to="Reddit")
    return "Posted to Reddit.", 200


@socials_routes.route("/delete-all", methods=["POST"])
@login_required
@restrict_to(["editors"])
def delete_all():
    delete_all_stories()
    return "All stories deleted.", 200


def post_to_reddit(title, url):
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=f"story submission by u/{REDDIT_USERNAME}",
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
    )
    subreddit = reddit.subreddit(SUBREDDIT)
    submission = subreddit.submit(title, url=url)
    return "https://www.reddit.com" + submission.permalink


def validate_story(title, url):
    if len(title) < 1:
        return "ERROR: Empty title."
    if len(url) < 1:
        return "ERROR: Empty URL."
    if not is_valid_url(url):
        return "ERROR: Invalid URL."
    return None


def is_valid_url(url):
    url_pattern = re.compile(r"^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$", re.IGNORECASE)
    return bool(re.match(url_pattern, url))
