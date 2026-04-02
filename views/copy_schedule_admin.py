import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

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
from util.copy_schedule import shift_label, day_label
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


def _to_json_safe(obj):
    """Recursively convert date/datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(item) for item in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _shift_label_str(shift: dict) -> str:
    """Return a human-readable shift label like 'Monday 4/7 6pm-8pm' from a shift dict."""
    d = shift.get("date")
    h = shift.get("start_hour")
    if d and h is not None:
        return f"{day_label(d)} {shift_label(h)}"
    return "your shift"


def _notify_editors_added(shift: dict):
    """DM any editors who were just assigned to a shift."""
    label = _shift_label_str(shift)
    for email in filter(None, [shift.get("editor_id"), shift.get("editor_id_2")]):
        dm_user_by_email(
            email,
            f"📅 *You've Been Scheduled for a Shift*\n"
            f"The copy chief has added you to a shift on {label}.\n"
            f"👉 Check the shift dashboard for details.",
        )


def _notify_editors_removed(shift: dict):
    """DM any editors who were just removed from a shift."""
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
    shifts = [_to_json_safe(s) for s in get_all_shifts()]
    shift_requests = [_to_json_safe(r) for r in get_all_shift_requests()]
    return render_template(
        "copy_schedule_admin.html",
        editors=editors,
        shifts=shifts,
        shift_requests=shift_requests,
    )


@copy_scheduler_routes.route("/admin/editor", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_editor():
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form.get("phone") or None
    category = request.form.get("category") or None
    editor = add_copy_editor(name=name, email=email, phone=phone, category=category)
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
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form.get("phone") or None
    category = request.form.get("category") or None
    editor = update_copy_editor(
        uid, name=name, email=email, phone=phone, category=category
    )
    return jsonify(editor)


@copy_scheduler_routes.route("/admin/shift", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_shift():
    date = datetime.date.fromisoformat(request.form["date"])
    start_hour = int(request.form["start_hour"])
    editor_id = request.form.get("editor_id") or None
    editor_name = request.form.get("editor_name") or None
    editor_id_2 = request.form.get("editor_id_2") or None
    editor_name_2 = request.form.get("editor_name_2") or None
    shift = add_shift(
        date=date,
        start_hour=start_hour,
        editor_id=editor_id,
        editor_name=editor_name,
        editor_id_2=editor_id_2,
        editor_name_2=editor_name_2,
    )
    if "error" not in shift:
        _notify_editors_added(shift)
    return jsonify(_to_json_safe(shift)), 201


@copy_scheduler_routes.route("/admin/shift/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_shift_route(uid):
    deleted = delete_shift(uid)
    if deleted:
        _notify_editors_removed(deleted)
    return jsonify({"ok": True})


@copy_scheduler_routes.route("/admin/shift/<uid>/update", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def update_shift_route(uid):
    date = datetime.date.fromisoformat(request.form["date"])
    start_hour = int(request.form["start_hour"])
    editor_id = request.form.get("editor_id") or None
    editor_name = request.form.get("editor_name") or None
    editor_id_2 = request.form.get("editor_id_2") or None
    editor_name_2 = request.form.get("editor_name_2") or None
    old_shift = get_shift_by_uid(uid)
    shift = update_shift(
        uid,
        date=date,
        start_hour=start_hour,
        editor_id=editor_id,
        editor_name=editor_name,
        editor_id_2=editor_id_2,
        editor_name_2=editor_name_2,
    )
    if shift and old_shift:
        old_editors = {
            e for e in [old_shift.get("editor_id"), old_shift.get("editor_id_2")] if e
        }
        new_editors = {
            e for e in [shift.get("editor_id"), shift.get("editor_id_2")] if e
        }
        label = _shift_label_str(shift)
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
    return jsonify(_to_json_safe(shift))


@copy_scheduler_routes.route("/admin/shifts", methods=["GET"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def get_shifts():
    return jsonify([_to_json_safe(s) for s in get_all_shifts()])


@copy_scheduler_routes.route("/admin/request/<int:uid>/approve", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def approve_request(uid):
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
def deny_request(uid):
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
