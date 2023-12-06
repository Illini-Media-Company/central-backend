import sys
from flask import Blueprint, render_template, request
from flask_login import login_required

from db.illordle_word import add_word, get_word, get_all_words


illordle_routes = Blueprint("illordle_routes", __name__, url_prefix="/illordle")


@illordle_routes.route("/dashboard")
@login_required
def dashboard():
    return render_template("illordle.html")


@illordle_routes.route("/word", methods=["POST"])
@login_required
def create_word():
    word = request.form["word"]
    date = request.form["date"]

    valid_word, message = validate_word(word)
    if not valid_word:
        return message

    ret = add_word(word=word, date=date)
    return f"Created word: {ret}", 200


@illordle_routes.route("/word", methods=["GET"])
@login_required
def list_words():
    if "date" in request.args:
        date = request.args.get("date")
        return get_word(date=date)

    return get_all_words()


"""
Helper/Utils
"""


def validate_word(word):
    if len(word) < 2 or len(word) > 7:
        return (
            False,
            "word must be greater than 2 characters and less than 7 characters.",
        )
