import re

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from db.story import (
    Story,
    create_story,
    get_all_stories,
    get_recent_stories,
    delete_all_stories
)



breaking_routes = Blueprint("breaking_routes", __name__, url_prefix="/breaking")


@breaking_routes.route("/dashboard")
@login_required
def dashboard():
    return render_template("breaking.html")



