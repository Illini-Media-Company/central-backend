from flask import Blueprint, render_template, request, abort
from flask_login import login_required
from datetime import datetime, timedelta
from db.illordle_word import add_word, get_word, get_all_words, delete_all_words

illordle_routes = Blueprint("illordle_routes", __name__, url_prefix="/illordle")


@illordle_routes.route("/dashboard")
@login_required
def dashboard():
    today = datetime.now().date()
    print("Today: " + str(datetime.now()))
    next_two_weeks = [today + timedelta(days=i) for i in range(15)]
    words = []
    for date in next_two_weeks:
        word = get_word(date)
        if word != "No word available for that date.":
            words.append(word)
        else:
            words.append({"date": date, "word": ""})

    return render_template("illordle.html", words=words)


@illordle_routes.route("/word", methods=["POST"])
@login_required
def create_word():
    word = request.form["word"]
    date_str = request.form["date"]
    try:
        date = datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:  # HTML depends on these error messages. Check before modify.
        return "ERROR: Invalid date format. Please use MM/DD/YYYY format."
    if date < datetime.now().date():
        return "ERROR: Date cannot be in the past."
    if len(word) < 5 or len(word) > 8:
        return "ERROR: Word must be between 5 and 8 characters long."

    ret = add_word(word=word, date=date)
    return ret, 200


@illordle_routes.route("/word", methods=["GET"])
@login_required
def list_word():
    date_str = request.args.get("date")
    print(date_str)
    if date_str:
        try:
            date = datetime.strptime(date_str, "%m/%d/%Y").date()
            word = get_word(date)
            return word
        except ValueError:
            return "Invalid date format. Please use MM/DD/YYYY format.", 400
    else:
        return "No date was provided to search.", 200


@illordle_routes.route("/all_words", methods=["GET"])
@login_required
def list_words():
    words = get_all_words()
    if words:
        return words
    else:
        return "No words in database.", 404


@illordle_routes.route("/delete_all_words", methods=["POST"])
@login_required
def delete_words():
    delete_all_words()
    return "All words deleted."
