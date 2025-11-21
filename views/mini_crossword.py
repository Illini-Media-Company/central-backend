from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request, jsonify
from flask_cors import cross_origin
from flask_login import login_required

from db.mini_crossword_object import get_crossword, get_all_crosswords
from db.story import get_recent_stories
from util.security import restrict_to
from util.stories import get_title_from_url
from util.helpers.ap_datetime import ap_daydate
from util.mini_crossword_validator import validate_crossword
from datetime import date as _date

from db.mini_crossword_object import add_crossword
from flask_login import current_user


mini_routes = Blueprint("mini_routes", __name__, url_prefix="/mini")


@mini_routes.route("", methods=["GET"])
@login_required
def all_days():
    """
    Return data; all saved crosswords
    """
    return get_all_crosswords()


@mini_routes.route("/today", methods=["GET"])
@cross_origin()
def today():
    """
    Return today's crossword data
    """
    today = datetime.today()
    days_since_monday = today.weekday()

    most_recent_monday = today - timedelta(days=days_since_monday)

    most_recent_monday.date()
    crossword = get_crossword(most_recent_monday.date())
    if crossword:
        return crossword
    return {"NO_CROSSWORD_ERROR": "No crossword scheduled for this date."}


@mini_routes.route("/dashboard")
@login_required
@restrict_to(["di-section-editors", "imc-staff-webdev"])
def dashboard():
    return render_template("mini_crossword.html")


@mini_routes.route("/api/validate", methods=["POST"])
@login_required
def validate():
    """
    Validate a crossword grid posted from the admin UI.
    Expected JSON body:
      {
        "date": "YYYY-MM-DD" | omitted (defaults to today),
        "grid": [[str,...] x5],  # '#' for black cells, 'A'-'Z' for letters (no empty cells)
        "origin": "manual"|"auto" (optional, defaults to "manual"),
        "article_link": str (optional, defaults to "")
      }
    """

    payload = request.get_json(silent=True) or {}

    # Fetch the grid
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

    # Check if crossword with this date already exists BEFORE validation
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

    origin = payload.get("origin") or "manual"
    article_link = payload.get("article_link") or ""
    created_by = (
        getattr(current_user, "name", None)
        or getattr(current_user, "email", None)
        or ""
    )

    # Build a lightweight object with attributes expected by validator
    class _Crossword:
        pass

    cw = _Crossword()
    cw.id = None
    cw.date = cw_date_obj
    cw.grid = grid
    cw.clues = {}  # Always empty - clues not set yet
    # cw.answers = []  # Always empty - answers not set yet
    cw.origin = origin
    cw.article_link = article_link
    cw.created_by = created_by

    try:
        summary = validate_crossword(cw)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({"ok": True, "summary": summary}), 200


@mini_routes.route("/api/submit", methods=["POST"])
@login_required
@restrict_to(["di-section-editors", "imc-staff-webdev"])
def save_crossword():
    """ """

    payload = request.get_json(silent=True) or {}

    # Get the date and the grid
    cw_date_str = payload.get("date")
    grid = payload.get("grid")
    data = payload.get("data")
    if not cw_date_str or not grid or not data:
        return jsonify({"ok": False, "error": "Date, grid and data are required."}), 400

    try:
        cw_date = _date.fromisoformat(cw_date_str)
        ap_date = ap_daydate(cw_date)
    except:
        return jsonify({"ok": False, "error": "Invalid date format."}), 400

    # Make the ID the date
    cw_id = int(cw_date.strftime("%Y%m%d"))

    # Get the article link and get the corresponding title (if present)
    link = payload.get("article_link", "")
    if link:
        title = get_title_from_url(link)
    else:
        title = ""

    crossword = add_crossword(
        id=cw_id,
        date=cw_date,
        datestr=ap_date,
        grid=grid,
        data=data,
        origin=payload.get("origin", "manual"),
        article_link=link,
        article_title=title,
        created_by=(
            getattr(current_user, "name", None)
            or getattr(current_user, "email", None)
            or ""
        ),
    )

    return jsonify({"ok": True, "crossword": crossword}), 200
