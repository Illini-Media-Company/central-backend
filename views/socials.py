import re

from flask import Blueprint, render_template, request
from flask_login import login_required

from db.social_post import (
    SocialPlatform,
    get_all_posts,
    get_recent_posts,
    delete_all_posts,
)
from util.security import restrict_to
from util.social_posts import (
    send_illinois_app_notification,
    post_to_reddit,
    post_to_twitter,
)
from util.stories import get_title_from_url


socials_routes = Blueprint("socials_routes", __name__, url_prefix="/socials")


@socials_routes.route("/dashboard")
@login_required
def dashboard():
    posts = get_recent_posts(10)
    platforms = list(SocialPlatform)
    return render_template("socials.html", posts=posts, platforms=platforms)


@socials_routes.route("", methods=["GET"])
@login_required
def list_posts():
    return get_all_posts()


@socials_routes.route("/illinois-app", methods=["POST"])
@login_required
@restrict_to(["editors"])
def create_push_notification():
    url = request.form["url"].partition("?")[0]
    title, err = validate_story(url)
    if err:
        return err

    url, err = send_illinois_app_notification(title, url)
    if err:
        return err
    else:
        return "Illinois app push notification sent.", 200


@socials_routes.route("/reddit", methods=["POST"])
@login_required
@restrict_to(["editors", "di-staff-social", "webdev"])
def create_reddit_post():
    url = request.form["url"].partition("?")[0]
    title, err = validate_story(url)
    if err:
        return err

    url, err = post_to_reddit(title, url)
    if err:
        print(err)
        return err
    else:
        return "Posted to Reddit.", 200


@socials_routes.route("/twitter", methods=["POST"])
@login_required
@restrict_to(["editors", "di-staff-social"])
def create_tweet():
    url = request.form["url"].partition("?")[0]
    title, err = validate_story(url)
    if err:
        return err

    url, err = post_to_twitter(title, url)
    if err:
        return err
    else:
        return "Posted to Twitter.", 200


@socials_routes.route("/delete-all", methods=["POST"])
@login_required
@restrict_to(["editors"])
def delete_all():
    delete_all_posts()
    return "All social posts deleted.", 200


def validate_story(url):
    if len(url) < 1:
        return None, ("ERROR: Empty URL.", 400)
    if not is_valid_url(url):
        return None, ("ERROR: Invalid URL.", 400)
    title = get_title_from_url(url)
    if title is None:
        return None, ("ERROR: Story cannot be found.", 400)
    return title, None


def is_valid_url(url):
    url_pattern = re.compile(r"^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$", re.IGNORECASE)
    return bool(re.match(url_pattern, url))
