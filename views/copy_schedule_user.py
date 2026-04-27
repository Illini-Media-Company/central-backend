from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from util.security import restrict_to
from util.copy_schedule import (
    get_week_bounds,
    get_week_schedule,
    get_shifts_for_week,
    get_droppable_shifts_for_week,
    get_editor_shifts_for_week,
    build_pending_map,
    build_incoming_map,
    build_swap_requested_set,
    get_required_shifts,
    get_available_hours,
    get_slot_class_for_user,
    get_slot_type_for_user,
    format_today,
    day_label,
    shift_label,
    request_drop,
    request_swap,
    add_slot,
    pickup_shift,
    cancel_request,
    approve_request,
    deny_request,
)
from db import client as dbclient
from constants import ALL_SCHEDULER_GROUPS
from datetime import date, timedelta

from views.copy_schedule_admin import copy_scheduler_routes


def _build_week_context(reference_date: date = None):
    sunday, saturday = get_week_bounds(reference_date)
    editor_id = current_user.email

    # Role-appropriate slot class and slot_type string
    slot_class = get_slot_class_for_user(current_user)
    slot_type = get_slot_type_for_user(current_user)

    # Break-week-aware schedule
    week_schedule = get_week_schedule(reference_date)
    is_break = week_schedule["is_break_week"]
    duration = week_schedule["duration"]

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

    available_hours = get_available_hours(current_user, reference_date)
    shift_hours = [
        {"start": h, "label": shift_label(h, duration)} for h in available_hours
    ]

    with dbclient.context():
        shifts_map_raw = get_shifts_for_week(reference_date, slot_class=slot_class)

        shifts_map = {
            k: v.to_dict() if v is not None else None for k, v in shifts_map_raw.items()
        }

        shift_editor_names = {
            key: slot.editor_name
            for key, slot in shifts_map_raw.items()
            if slot and slot.editor_name
        }

        droppable_set = get_droppable_shifts_for_week(
            reference_date, slot_class=slot_class
        )
        swap_req_set = build_swap_requested_set(reference_date, slot_type=slot_type)
        my_shifts_raw = get_editor_shifts_for_week(
            editor_id, reference_date, slot_class=slot_class
        )

        my_shifts = [
            {
                "date": s.date,
                "date_str": s.date.isoformat(),
                "start_hour": s.start_hour,
                "day_label": day_label(s.date),
                "hour_label": shift_label(s.start_hour, duration),
                "up_for_drop": s.up_for_drop,
            }
            for s in my_shifts_raw
        ]

        pending_map = build_pending_map(editor_id, reference_date, slot_type=slot_type)
        required = get_required_shifts(current_user, reference_date)
        incoming_requests = build_incoming_map(
            editor_id, reference_date, slot_type=slot_type
        )

    return {
        "editor": {
            "id": editor_id,
            "name": current_user.name,
            "required_shifts_per_week": required,
        },
        "today_label": format_today(),
        "week_days": week_days,
        "shift_hours": shift_hours,
        "is_break_week": is_break,
        "shifts_map": shifts_map,
        "shift_editor_names": shift_editor_names,
        "droppable_set": droppable_set,
        "swap_requested_set": swap_req_set,
        "my_shifts": my_shifts,
        "pending_map": pending_map,
        "incoming_requests": incoming_requests,
    }


@copy_scheduler_routes.route("/me", methods=["GET"])
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
    return render_template("copy_schedule.html", **ctx)


@copy_scheduler_routes.route("/me/api/accept-swap", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_accept_swap():
    data = request.get_json()
    with dbclient.context():
        result = approve_request(data["request_id"])
    if result["success"]:
        return jsonify({"status": "accepted"})
    return jsonify({"status": "error", "message": result["reason"]}), 400


@copy_scheduler_routes.route("/me/api/decline-swap", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_decline_swap():
    data = request.get_json()
    with dbclient.context():
        result = deny_request(data["request_id"])
    if result["success"]:
        return jsonify({"status": "declined"})
    return jsonify({"status": "error", "message": result["reason"]}), 400


@copy_scheduler_routes.route("/me/api/drop", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_drop_shift():
    data = request.get_json()
    with dbclient.context():
        result = request_drop(
            current_user, date.fromisoformat(data["date"]), int(data["hour"])
        )
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    return jsonify({"status": "pending", "request_id": result["request_id"]})


@copy_scheduler_routes.route("/me/api/swap", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_swap_shift():
    data = request.get_json()
    with dbclient.context():
        result = request_swap(
            current_user,
            date.fromisoformat(data["source_date"]),
            int(data["source_hour"]),
            date.fromisoformat(data["target_date"]),
            int(data["target_hour"]),
            data["swap_mode"],
        )
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    return jsonify({"status": "pending", "request_id": result["request_id"]})


@copy_scheduler_routes.route("/me/api/add-slot", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_add_slot():
    data = request.get_json()
    with dbclient.context():
        result = add_slot(
            current_user, date.fromisoformat(data["date"]), int(data["hour"])
        )
    if result["success"]:
        return jsonify({"status": "added"})
    return jsonify({"status": "error", "message": result["reason"]}), 400


@copy_scheduler_routes.route("/me/api/pickup", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_pickup_shift():
    data = request.get_json()
    with dbclient.context():
        result = pickup_shift(
            current_user, date.fromisoformat(data["date"]), int(data["hour"])
        )
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    return jsonify({"status": "picked_up"})


@copy_scheduler_routes.route("/me/api/cancel-request", methods=["POST"])
@login_required
@restrict_to(ALL_SCHEDULER_GROUPS)
def api_cancel_request():
    data = request.get_json()
    with dbclient.context():
        result = cancel_request(data["request_id"])
    if result["success"]:
        return jsonify({"status": "cancelled"})
    return jsonify({"status": "error", "message": result["reason"]}), 400
