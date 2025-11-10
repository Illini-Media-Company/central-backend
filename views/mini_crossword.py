from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request, jsonify

# from flask_cors import cross_origin
from flask_login import login_required

# from flask_login import current_user, login_required
# from util.illordle_generate_word import random_word

from db.mini_crossword_object import get_crossword, get_all_crosswords
from db.story import get_recent_stories
from util.security import restrict_to
from util.stories import get_title_from_url
from util.mini_crossword.validator import validate_crossword
from datetime import date as _date

from db.mini_crossword_object import add_crossword
from flask_login import current_user


mini_routes = Blueprint("mini_routes", __name__, url_prefix="/mini")


@mini_routes.route("", methods=["GET"])
@login_required
def all_days():
    """
    Return data; all saved crosswods
    """
    return get_all_crosswords()


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


@mini_routes.route("/validate", methods=["POST"])
@login_required
def validate():
    """
    Validate a crossword grid posted from the admin UI.
    Expected JSON body:
      {
        "date": "YYYY-MM-DD" | omitted (defaults to today),
        "grid": [[str,...] x5],  # '#' for black cells, 'A'-'Z' for letters
        "origin": "manual"|"auto" (optional, defaults to "manual"),
        "article_link": str (optional, defaults to ""),
        "created_by": str (optional, defaults to "")
      }
    """

    payload = request.get_json(silent=True) or {}

    grid = payload.get("grid")
    if not isinstance(grid, list):
        return (
            jsonify({"ok": False, "error": "grid is required and must be a 5x5 list"}),
            400,
        )

    # Defaults for meta
    cw_date_str = payload.get("date") or _date.today().isoformat()

    # Convert date string to date object if needed
    if isinstance(cw_date_str, str):
        try:
            cw_date_obj = _date.fromisoformat(cw_date_str)
        except ValueError:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Invalid date format. Use YYYY-MM-DD format.",
                    }
                ),
                400,
            )
    else:
        cw_date_obj = cw_date_str

    origin = payload.get("origin") or "manual"
    article_link = payload.get("article_link") or ""
    created_by = (
        getattr(current_user, "email", None)
        or getattr(current_user, "name", None)
        or ""
    )

    # Build a lightweight object with attributes expected by validator
    class _Crossword:
        pass

    cw = _Crossword()
    cw.id = None
    cw.date = cw_date_obj
    cw.grid = grid
    cw.clues = payload.get("clues") or {}
    cw.answers = payload.get("answers") or []
    cw.origin = origin
    cw.article_link = article_link
    cw.created_by = created_by

    try:
        summary = validate_crossword(cw)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    # Only after successful validation, check if crossword with this date already exists
    existing = get_crossword(cw_date_obj)
    if existing:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"A crossword already exists for {cw_date_obj}. Please change the date.",
                }
            ),
            400,
        )

    return jsonify({"ok": True, "summary": summary})


@mini_routes.route("/save", methods=["POST"])
@login_required
def save_crossword():
    payload = request.get_json(silent=True) or {}

    cw_date_str = payload.get("date")
    grid = payload.get("grid")
    if not cw_date_str or not grid:
        return jsonify({"ok": False, "error": "date and grid are required"}), 400

    try:
        cw_date = _date.fromisoformat(cw_date_str)
    except:
        return jsonify({"ok": False, "error": "Invalid date format"}), 400

    cw_id = int(cw_date.strftime("%Y%m%d"))

    crossword = add_crossword(
        id=cw_id,
        date=cw_date,
        grid=grid,
        clues=payload.get("clues", {}),
        answers=payload.get("answers", []),
        origin=payload.get("origin", "manual"),
        article_link=payload.get("article_link", ""),
        created_by=(
            getattr(current_user, "email", None)
            or getattr(current_user, "name", None)
            or ""
        ),
    )

    return jsonify({"ok": True, "crossword": crossword})
