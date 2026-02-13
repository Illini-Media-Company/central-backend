from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request
from flask_cors import cross_origin
from flask_login import current_user, login_required
from util.illordle_generate_word import random_word

from db.illordle_word import (
    add_word,
    get_word,
    get_all_words,
    get_words_in_date_range,
    delete_all_words,
)
from util.security import restrict_to
from util.stories import get_title_from_url

from util.google_analytics import send_ga4_event
from constants import IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID


illordle_routes = Blueprint("illordle_routes", __name__, url_prefix="/illordle")


@illordle_routes.route("/dashboard")
@login_required
def dashboard():
    today = datetime.now(tz=ZoneInfo("America/Chicago")).date()
    next_two_weeks = [today + timedelta(days=i) for i in range(15)]
    words = []
    for date in next_two_weeks:
        word = get_word(date)
        if word != None:
            words.append(word)
        else:
            words.append({"date": date, "word": ""})

    return render_template("illordle.html", words=words)


@illordle_routes.route("", methods=["GET"])
@login_required
def list_words():
    words = get_all_words()
    return words


@illordle_routes.route("/word/today", methods=["GET"])
@cross_origin()
def get_todays_word():
    # Log in Google Analytics
    utm_source = request.args.get("utm_source", "none")
    utm_medium = request.args.get("utm_medium", "none")
    send_ga4_event(
        "illordle_word_fetch",
        IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID,
        {"utm_source": utm_source, "utm_medium": utm_medium},
    )

    today = datetime.now(tz=ZoneInfo("America/Chicago")).date()
    word = get_word(today)
    if word != None:
        return word
    else:
        word = add_word(random_word(), today, "", "", "")
        return word


@illordle_routes.route("/word/<mm>/<dd>/<yyyy>", methods=["GET"])
@login_required
def retrieve_word(mm, dd, yyyy):
    try:
        year = int(yyyy)
        month = int(mm)
        day = int(dd)
        date = datetime(year, month, day).date()
        word = get_word(date)
        if word is not None:
            return word
        else:
            return "No word set for date.", 404
    except ValueError:
        return "Invalid date format. Please use MM/DD/YYYY format.", 400


@illordle_routes.route("/word/<mm>/<dd>/<yyyy>", methods=["POST"])
@login_required
@restrict_to(["editors", "di-section-editors"])
def create_word(mm, dd, yyyy):
    word = request.form["word"].lower()
    story_url = request.form["url"].partition("?")[0]

    try:
        year = int(yyyy)
        month = int(mm)
        day = int(dd)
        date = datetime(year, month, day).date()
    except ValueError:
        return "ERROR: Invalid date format. Please use MM/DD/YYYY format.", 400
    # if date < datetime.now(tz=ZoneInfo("America/Chicago")).date():
    #     return "ERROR: Date cannot be in the past.", 400
    if len(word) < 5 or len(word) > 6:
        return "ERROR: Word must be 5 or 6 letters long.", 400
    if not word.isalpha():
        return "ERROR: Word must contain only letters.", 400

    if story_url != "":
        story_title = get_title_from_url(story_url)
        if story_title is None:
            return "ERROR: Story cannot be found.", 400
    else:
        story_title = ""

    old_words = get_words_in_date_range(date - timedelta(days=180), None)
    if (
        sum(
            (old_word["word"] == word and old_word["date"] != date)
            for old_word in old_words
        )
        > 0
    ):
        return "ERROR: Word cannot be used in the last 180 days.", 400

    return add_word(
        word=word,
        date=date,
        author=current_user.name,
        story_url=story_url,
        story_title=story_title,
    )


@illordle_routes.route("/delete-all", methods=["POST"])
@login_required
@restrict_to(["editors"])
def delete_all():
    delete_all_words()
    return "All words deleted."
