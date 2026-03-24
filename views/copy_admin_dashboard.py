import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from util.copy_scheduler_admin import (
    get_all_copy_editors,
    add_copy_editor,
    delete_copy_editor,
    update_copy_editor,
    get_all_shifts,
    add_shift,
    delete_shift,
    update_shift,
    get_all_shift_requests,
    approve_shift_request,
    deny_shift_request,
)
from util.security import restrict_to
from constants import COPY_ADMIN_ACCESS_GROUPS

copy_admin_dashboard_routes = Blueprint(
    "copy_admin_dashboard_routes", __name__, url_prefix="/copy-admin-dashboard"
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


@copy_admin_dashboard_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def admin():
    editors = get_all_copy_editors()
    shifts = [_to_json_safe(s) for s in get_all_shifts()]
    shift_requests = [_to_json_safe(r) for r in get_all_shift_requests()]
    return render_template(
        "copy_admin.html", editors=editors, shifts=shifts, shift_requests=shift_requests
    )


@copy_admin_dashboard_routes.route("/admin/editor", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def create_editor():
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form.get("phone") or None
    category = request.form.get("category") or None
    editor = add_copy_editor(name=name, email=email, phone=phone, category=category)
    return jsonify(editor), 201


@copy_admin_dashboard_routes.route("/admin/editor/<int:uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_editor(uid):
    delete_copy_editor(uid)
    return jsonify({"ok": True})


@copy_admin_dashboard_routes.route("/admin/editor/<int:uid>/update", methods=["POST"])
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


@copy_admin_dashboard_routes.route("/admin/shift", methods=["POST"])
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
    return jsonify(_to_json_safe(shift)), 201


@copy_admin_dashboard_routes.route("/admin/shift/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def delete_shift_route(uid):
    delete_shift(uid)
    return jsonify({"ok": True})


@copy_admin_dashboard_routes.route("/admin/shift/<uid>/update", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def update_shift_route(uid):
    date = datetime.date.fromisoformat(request.form["date"])
    start_hour = int(request.form["start_hour"])
    editor_id = request.form.get("editor_id") or None
    editor_name = request.form.get("editor_name") or None
    editor_id_2 = request.form.get("editor_id_2") or None
    editor_name_2 = request.form.get("editor_name_2") or None
    shift = update_shift(
        uid,
        date=date,
        start_hour=start_hour,
        editor_id=editor_id,
        editor_name=editor_name,
        editor_id_2=editor_id_2,
        editor_name_2=editor_name_2,
    )
    return jsonify(_to_json_safe(shift))


@copy_admin_dashboard_routes.route("/admin/request/<int:uid>/approve", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def approve_request(uid):
    approve_shift_request(uid)
    return jsonify({"ok": True})


@copy_admin_dashboard_routes.route("/admin/request/<int:uid>/deny", methods=["POST"])
@login_required
@restrict_to(COPY_ADMIN_ACCESS_GROUPS)
def deny_request(uid):
    deny_shift_request(uid)
    return jsonify({"ok": True})
