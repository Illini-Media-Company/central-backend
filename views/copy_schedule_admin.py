import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from db.copy_schedule import ShiftSlot, SeniorShiftSlot
from db.kv_store import kv_store_get, kv_store_set
from util.copy_schedule_admin import (
    get_all_copy_editors,
    add_copy_editor,
    delete_copy_editor,
    update_copy_editor,
    get_all_shifts,
    add_shift,
    delete_shift,
    update_shift,
    get_shift_by_uid,
    get_all_shift_requests,
    approve_shift_request,
    deny_shift_request,
    upsert_editors_from_groups,
)
from util.copy_schedule import (
    shift_label,
    day_label,
    get_all_break_weeks,
    toggle_break_week,
)
from util.slackbots.general import dm_user_by_email
from util.google_admin import get_group_members
from util.security import restrict_to
from constants import (
    COPY_ADMIN_ACCESS_GROUPS,
    COPY_EDITOR_GROUPS,
    SENIOR_COPY_EDITOR_GROUPS,
)

copy_scheduler_routes = Blueprint(
    "copy_scheduler_routes", __name__, url_prefix="/copy-schedule"
)

# KV key for the copy bot feature flag
COPY_BOT_FLAG_KEY = "COPY_BOT_USE_SHIFT_SCHEDULE"


def _to_json_safe(obj):
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(item) for item in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _shift_label_str(shift: dict) -> str:
    d = shift.get("date")
    h = shift.get("start_hour")
    if d and h is not None:
        return f"{day_label(d)} {shift_label(h)}"
    return "your shift"


def _notify_editors_added(shift: dict):
    label = _shift_label_str(shift)
    for email in filter(None, [shift.get("editor_id"), shift.get("editor_id_2")]):
        dm_user_by_email(
            email,
            f"📅 *You've Been Scheduled for a Shift*\n"
            f"The copy chief has added you to a shift on {label}.\n"
            f"👉 Check the shift dashboard for details.",
        )


def _notify_editors_removed(shift: dict):
    label = _shift_label_str(shift)
    for email in filter(None, [shift.get("editor_id"), shift.get("editor_id_2")]):
        dm_user_by_email(
            email,
            f"🗑️ *A Shift Was Removed*\n"
            f"The copy chief has removed your shift on {label}.\n"
            f"👉 Check the shift dashboard for your updated schedule.",
        )


@copy_scheduler_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def admin():
    editors = get_all_copy_editors()
    shifts = [_to_json_safe(s) for s in get_all_shifts(slot_class=ShiftSlot)]
    senior_shifts = [
        _to_json_safe(s) for s in get_all_shifts(slot_class=SeniorShiftSlot)
    ]
    shift_requests = [_to_json_safe(r) for r in get_all_shift_requests()]
    break_weeks = get_all_break_weeks()
    copy_bot_active = str(kv_store_get(COPY_BOT_FLAG_KEY)) == "1"
    return render_template(
        "copy_schedule_admin.html",
        editors=editors,
        shifts=shifts,
        senior_shifts=senior_shifts,
        shift_requests=shift_requests,
        break_weeks=break_weeks,
        copy_bot_active=copy_bot_active,
    )


@copy_scheduler_routes.route("/admin/editor", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_editor():
    editor = add_copy_editor(
        name=request.form["name"],
        email=request.form["email"],
        phone=request.form.get("phone") or None,
        category=request.form.get("category") or None,
    )
    return jsonify(editor), 201


@copy_scheduler_routes.route("/admin/editor/<int:uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_editor(uid):
    delete_copy_editor(uid)
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/editor/<int:uid>/update", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def update_editor(uid):
    editor = update_copy_editor(
        uid,
        name=request.form["name"],
        email=request.form["email"],
        phone=request.form.get("phone") or None,
        category=request.form.get("category") or None,
    )
    return jsonify(editor)


@copy_scheduler_routes.route("/admin/shift", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_shift():
    shift = add_shift(
        date=datetime.date.fromisoformat(request.form["date"]),
        start_hour=int(request.form["start_hour"]),
        editor_id=request.form.get("editor_id") or None,
        editor_name=request.form.get("editor_name") or None,
        editor_id_2=request.form.get("editor_id_2") or None,
        editor_name_2=request.form.get("editor_name_2") or None,
        slot_class=ShiftSlot,
    )
    if "error" not in shift:
        _notify_editors_added(shift)
    return jsonify(_to_json_safe(shift)), 201


@copy_scheduler_routes.route("/admin/shift/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_shift_route(uid):
    deleted = delete_shift(uid, slot_class=ShiftSlot)
    if deleted:
        _notify_editors_removed(deleted)
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/shift/<uid>/update", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def update_shift_route(uid):
    old_shift = get_shift_by_uid(uid, slot_class=ShiftSlot)
    shift = update_shift(
        uid,
        date=datetime.date.fromisoformat(request.form["date"]),
        start_hour=int(request.form["start_hour"]),
        editor_id=request.form.get("editor_id") or None,
        editor_name=request.form.get("editor_name") or None,
        editor_id_2=request.form.get("editor_id_2") or None,
        editor_name_2=request.form.get("editor_name_2") or None,
        slot_class=ShiftSlot,
    )
    _diff_notify(old_shift, shift)
    return jsonify(_to_json_safe(shift))


@copy_scheduler_routes.route("/admin/senior-shift", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_senior_shift():
    shift = add_shift(
        date=datetime.date.fromisoformat(request.form["date"]),
        start_hour=int(request.form["start_hour"]),
        editor_id=request.form.get("editor_id") or None,
        editor_name=request.form.get("editor_name") or None,
        editor_id_2=request.form.get("editor_id_2") or None,
        editor_name_2=request.form.get("editor_name_2") or None,
        slot_class=SeniorShiftSlot,
    )
    if "error" not in shift:
        _notify_editors_added(shift)
    return jsonify(_to_json_safe(shift)), 201


@copy_scheduler_routes.route("/admin/senior-shift/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_senior_shift_route(uid):
    deleted = delete_shift(uid, slot_class=SeniorShiftSlot)
    if deleted:
        _notify_editors_removed(deleted)
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/senior-shift/<uid>/update", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def update_senior_shift_route(uid):
    old_shift = get_shift_by_uid(uid, slot_class=SeniorShiftSlot)
    shift = update_shift(
        uid,
        date=datetime.date.fromisoformat(request.form["date"]),
        start_hour=int(request.form["start_hour"]),
        editor_id=request.form.get("editor_id") or None,
        editor_name=request.form.get("editor_name") or None,
        editor_id_2=request.form.get("editor_id_2") or None,
        editor_name_2=request.form.get("editor_name_2") or None,
        slot_class=SeniorShiftSlot,
    )
    _diff_notify(old_shift, shift)
    return jsonify(_to_json_safe(shift))


@copy_scheduler_routes.route("/admin/shifts", methods=["GET"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def get_shifts():
    return jsonify([_to_json_safe(s) for s in get_all_shifts(slot_class=ShiftSlot)])


@copy_scheduler_routes.route("/admin/senior-shifts", methods=["GET"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def get_senior_shifts():
    return jsonify(
        [_to_json_safe(s) for s in get_all_shifts(slot_class=SeniorShiftSlot)]
    )


@copy_scheduler_routes.route("/admin/request/<int:uid>/approve", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def approve_request_route(uid):
    result = approve_shift_request(uid)
    if "error" not in result:
        requester_email = result.get("requester_id")
        if requester_email:
            dm_user_by_email(
                requester_email,
                f"✅ *Your Request Was Approved*\n"
                f"Your {result.get('request_type', '').replace('_', ' ')} request has been approved by the copy chief.\n"
                f"👉 Check the shift dashboard to see your updated schedule.",
            )
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/request/<int:uid>/deny", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def deny_request_route(uid):
    result = deny_shift_request(uid)
    if "error" not in result:
        requester_email = result.get("requester_id")
        if requester_email:
            dm_user_by_email(
                requester_email,
                f"❌ *Your Request Was Denied*\n"
                f"Your {result.get('request_type', '').replace('_', ' ')} request has been denied by the copy chief.\n"
                f"Please check the shift dashboard or reach out with questions.",
            )
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/break-week/toggle", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def toggle_break_week_route():
    data = request.get_json()
    week_start_iso = data.get("week_start")
    if not week_start_iso:
        return jsonify({"error": "week_start is required"}), 400
    try:
        week_start = datetime.date.fromisoformat(week_start_iso)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400
    if week_start.weekday() != 6:
        return jsonify({"error": "week_start must be a Sunday"}), 400
    result = toggle_break_week(week_start_iso, admin_email=current_user.email)
    return jsonify(result)


@copy_scheduler_routes.route("/admin/flag/copy-bot/toggle", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def toggle_copy_bot_flag():
    """
    Toggle COPY_BOT_USE_SHIFT_SCHEDULE between "0" (calendar) and "1" (shift schedule).
    Returns: {"active": bool}
    """
    current = str(kv_store_get(COPY_BOT_FLAG_KEY))
    new_val = "0" if current == "1" else "1"
    kv_store_set(COPY_BOT_FLAG_KEY, new_val)
    return jsonify({"active": new_val == "1"})


@copy_scheduler_routes.route("/admin/sync-from-groups", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def sync_from_groups():
    group_map = {}
    for group in COPY_EDITOR_GROUPS:
        members = get_group_members(f"{group}@illinimedia.com")
        group_map.setdefault("Copy Editor", []).extend(members)
    for group in SENIOR_COPY_EDITOR_GROUPS:
        members = get_group_members(f"{group}@illinimedia.com")
        group_map.setdefault("Senior Copy Editor", []).extend(members)
    result = upsert_editors_from_groups(group_map)
    return jsonify(result)


def _diff_notify(old_shift: dict | None, new_shift: dict | None):
    """DM editors who were added or removed from a shift."""
    if not new_shift or not old_shift:
        return
    label = _shift_label_str(new_shift)
    old_editors = {
        e for e in [old_shift.get("editor_id"), old_shift.get("editor_id_2")] if e
    }
    new_editors = {
        e for e in [new_shift.get("editor_id"), new_shift.get("editor_id_2")] if e
    }
    for email in new_editors - old_editors:
        dm_user_by_email(
            email,
            f"📅 *You've Been Scheduled for a Shift*\n"
            f"The copy chief has added you to a shift on {label}.\n"
            f"👉 Check the shift dashboard for details.",
        )
    for email in old_editors - new_editors:
        dm_user_by_email(
            email,
            f"🗑️ *You've Been Removed from a Shift*\n"
            f"The copy chief has removed you from the shift on {label}.\n"
            f"👉 Check the shift dashboard for your updated schedule.",
        )
