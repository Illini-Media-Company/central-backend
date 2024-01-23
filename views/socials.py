import re

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from db.story import (
    get_all_stories,
    get_recent_stories,
    add_story,
    delete_all_stories,
    check_limit,
)
from util.security import restrict_to
from util.stories import get_title_from_url, post_to_reddit


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
    url = request.form["url"].partition("?")[0]
    title, err = validate_story(url)
    if err:
        return err, 400

    add_story(
        title=title, url=url, posted_to="Illinois app", posted_by=current_user.name
    )
    return "Illinois App push notification sent.", 200


@socials_routes.route("/reddit", methods=["POST"])
@login_required
@restrict_to(["editors", "social"])
def create_reddit_post():
    url = request.form["url"].partition("?")[0]
    title, err = validate_story(url)
    if err:
        return err, 400

    try:
        reddit_url = post_to_reddit(title, url)
    except Exception as e:
        return str(e), 500

    add_story(
        title=title, url=reddit_url, posted_to="Reddit", posted_by=current_user.name
    )
    return "Posted to Reddit.", 200


@socials_routes.route("/delete-all", methods=["POST"])
@login_required
@restrict_to(["editors"])
def delete_all():
    delete_all_stories()
    return "All stories deleted.", 200


def validate_story(url):
    if len(url) < 1:
        return None, "ERROR: Empty URL."
    if not is_valid_url(url):
        return None, "ERROR: Invalid URL."
    title = get_title_from_url(url)
    if title is None:
        return None, "ERROR: Story cannot be found."
    return title, None


def is_valid_url(url):
    url_pattern = re.compile(r"^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$", re.IGNORECASE)
    return bool(re.match(url_pattern, url))
