from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from util.security import restrict_to
from util.shift_utils import (
    get_week_bounds,
    get_shifts_for_week,
    get_droppable_shifts_for_week,
    get_editor_shifts_for_week,
    build_pending_map,
    build_swap_requested_set,
    get_required_shifts,
    format_today,
    day_label,
    shift_label,
    request_drop,
    request_swap,
    add_slot,
    pickup_shift,
    cancel_request,
    SHIFT_START_HOURS,
)
from db import client as dbclient
from constants import ALL_SCHEDULER_GROUPS
from datetime import date, datetime, timedelta


shift_scheduler_routes = Blueprint(
    "shift_scheduler_routes", __name__, url_prefix="/shift-scheduler"
)


# ---------------------------------------------------------------------------
# Helper: build template context for a given week
# ---------------------------------------------------------------------------


def _build_week_context(reference_date: date = None):
    sunday, saturday = get_week_bounds(reference_date)
    editor_id = current_user.email

    week_days = []
    current = sunday
    while current <= saturday:
        week_days.append(
            {
                "date_str": current.isoformat(),
                "label": day_label(current),
            }
        )
        current += timedelta(days=1)

    shift_hours = [{"start": h, "label": shift_label(h)} for h in SHIFT_START_HOURS]

    with dbclient.context():
        shifts_map = get_shifts_for_week(reference_date)

        shift_editor_names = {}
        for key, slot in shifts_map.items():
            if slot and slot.editor_name:
                shift_editor_names[key] = slot.editor_name

        droppable_set = get_droppable_shifts_for_week(reference_date)
        swap_requested_set = build_swap_requested_set(reference_date)

        my_shifts_raw = get_editor_shifts_for_week(editor_id, reference_date)
        my_shifts = []
        for s in my_shifts_raw:
            my_shifts.append(
                {
                    "date": s.date,
                    "date_str": s.date.isoformat(),
                    "start_hour": s.start_hour,
                    "day_label": day_label(s.date),
                    "hour_label": shift_label(s.start_hour),
                    "up_for_drop": s.up_for_drop,
                }
            )

        pending_map = build_pending_map(editor_id, reference_date)
        required = get_required_shifts(current_user, reference_date)

    return {
        "editor": {
            "id": editor_id,
            "name": current_user.name,
            "required_shifts_per_week": required,
        },
        "today_label": format_today(),
        "week_days": week_days,
        "shift_hours": shift_hours,
        "shifts_map": shifts_map,
        "shift_editor_names": shift_editor_names,
        "droppable_set": droppable_set,
        "swap_requested_set": swap_requested_set,
        "my_shifts": my_shifts,
        "pending_map": pending_map,
    }


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------


@shift_scheduler_routes.route("", methods=["GET"])
@shift_scheduler_routes.route("/", methods=["GET"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def scheduler():
    week_param = request.args.get("week")
    if week_param:
        try:
            reference_date = date.fromisoformat(week_param)
        except ValueError:
            reference_date = date.today()
    else:
        reference_date = date.today()

    ctx = _build_week_context(reference_date)
    return render_template("scheduler.html", **ctx)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@shift_scheduler_routes.route("/api/drop", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_drop_shift():
    data = request.get_json()
    shift_date = date.fromisoformat(data["date"])
    shift_hour = int(data["hour"])

    with dbclient.context():
        result = request_drop(current_user, shift_date, shift_hour)

    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400

    return jsonify({"status": "pending", "request_id": result["request_id"]})


@shift_scheduler_routes.route("/api/swap", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_swap_shift():
    data = request.get_json()
    source_date = date.fromisoformat(data["source_date"])
    source_hour = int(data["source_hour"])
    target_date = date.fromisoformat(data["target_date"])
    target_hour = int(data["target_hour"])
    swap_mode = data["swap_mode"]  # "direct" | "add_into" | "swap_drop"

    with dbclient.context():
        result = request_swap(
            current_user,
            source_date,
            source_hour,
            target_date,
            target_hour,
            swap_mode,
        )

    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400

    return jsonify({"status": "pending", "request_id": result["request_id"]})


@shift_scheduler_routes.route("/api/add-slot", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_add_slot():
    data = request.get_json()
    shift_date = date.fromisoformat(data["date"])
    shift_hour = int(data["hour"])

    with dbclient.context():
        result = add_slot(current_user, shift_date, shift_hour)

    if result["success"]:
        return jsonify({"status": "added"})
    else:
        return jsonify({"status": "error", "message": result["reason"]}), 400


@shift_scheduler_routes.route("/api/pickup", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_pickup_shift():
    data = request.get_json()
    shift_date = date.fromisoformat(data["date"])
    shift_hour = int(data["hour"])

    with dbclient.context():
        result = pickup_shift(current_user, shift_date, shift_hour)

    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400

    return jsonify({"status": "picked_up"})


@shift_scheduler_routes.route("/api/cancel-request", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_cancel_request():
    data = request.get_json()

    with dbclient.context():
        result = cancel_request(data["request_id"])

    if result["success"]:
        return jsonify({"status": "cancelled"})
    else:
        return jsonify({"status": "error", "message": result["reason"]}), 400
