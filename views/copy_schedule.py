from flask import Blueprint, request
from flask_login import current_user, login_required
from util.copy_editing import add_copy_editor, remove_copy_editor

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


@copy_schedule_routes.route("/unregister", methods=["POST"])
@login_required
def unregister():
    day_of_week = request.form["day_of_week"]
    shift_num = request.form["shift_num"]
    remove_copy_editor(current_user.email, day_of_week, shift_num)
    return "Done unregister", 200
