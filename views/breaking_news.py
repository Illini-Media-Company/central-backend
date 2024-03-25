import re
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user, login_required
import requests

from db.story import Story, add_story, get_recent_stories

from util.stories import get_title_from_url


breaking_routes = Blueprint("breaking_routes", __name__, url_prefix="/breaking")




@breaking_routes.route("/dashboard")
@login_required
def dashboard():
    stories = get_recent_stories(10)

    return render_template('breaking.html', stories=stories)

@breaking_routes.route('/submit', methods=['POST'])
def submit_story():
    url = request.form['url']
    title = get_title_from_url(url)
    post_to_reddit = request.form.get('post_to_reddit') == '1'
    post_to_twitter = request.form.get('post_to_twitter') == '1'
    slack_message_id = ' '
    created_by = current_user.name

    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to fetch webpage"
    
    new_story = add_story(
        title=title,
        url=url,
        post_to_reddit=post_to_reddit,
        post_to_twitter=post_to_twitter,
        slack_message_id=slack_message_id,
        created_by=created_by
    )

    return "Submitted to database", 200