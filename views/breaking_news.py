import re

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from db.story import (
    Story,
    add_story,
    get_all_stories,
    get_recent_stories,
    delete_all_stories
)



breaking_routes = Blueprint("breaking_routes", __name__, url_prefix="/breaking")



@breaking_routes.route('/submit_story', methods=['POST'])
def submit_story():
    title = request.form[Story.title]
    content = request.form[Story.url]
    db.add_story(title, content)
    return 'Story added successfully'

@breaking_routes.route("/dashboard")
@login_required
def dashboard():
    stories = get_recent_stories(10)
    return render_template("breaking.html", stories=stories)

