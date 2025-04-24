from flask import Blueprint, request
from flask_login import current_user, login_required
from util.copy_editing import add_copy_editor, remove_copy_editor
from db.json_store import json_store_get
from util.security import restrict_to, csrf
copy_schedule_routes = Blueprint(
    "copy_schedule_routes", __name__, url_prefix="/copy_schedule"
)


@copy_schedule_routes.route("/register", methods=["POST"])
@login_required
def register():
    day_of_week = request.form["day_of_week"]
    shift_num = request.form["shift_num"]
    add_copy_editor(current_user.email, day_of_week, shift_num)
    return "Done register", 200

@copy_schedule_routes.route("/copy-edit-scheduler", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def print_jobs():
    print(type(json_store_get("COPY_EDITING_JOBS")))
    return json_store_get("COPY_EDITING_JOBS") if json_store_get("COPY_EDITING_JOBS") else "None", 200


@copy_schedule_routes.route("/unregister", methods=["POST"])
@login_required
def unregister():
    day_of_week = request.form["day_of_week"]
    shift_num = request.form["shift_num"]
    remove_copy_editor(current_user.email, day_of_week, shift_num)
    return "Done unregister", 200
