from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request

# from flask_cors import cross_origin
from flask_login import login_required

# from flask_login import current_user, login_required
# from util.illordle_generate_word import random_word

# from db.mini_crossword import (
#     # necessary functions to pull
# )
from db.story import get_recent_stories
from util.security import restrict_to
from util.stories import get_title_from_url


mini_routes = Blueprint("mini_routes", __name__, url_prefix="/mini")


@mini_routes.route("", methods=["GET"])
@login_required
def all_days():
    """
    Return data; all saved crosswods
    """
    return ""


@mini_routes.route("/today", methods=["GET"])
@login_required
def today():
    """
    Return today's crossword data
    """
    return ""


@mini_routes.route("/word/<mm>/<dd>/<yyyy>", methods=["GET"])
@login_required
def retrieve_word(mm, dd, yyyy):
    """
    Return a specific day's crossword data
    """
    return ""


@mini_routes.route("/dashboard")
@login_required
def dashboard():
    return render_template("mini_crossword.html")
