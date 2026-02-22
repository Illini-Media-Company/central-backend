from flask import Blueprint, render_template, request, redirect, url_for
from db.copy_admin_dashboard import (
    get_all_copy_editors,
    add_copy_editor,
    delete_copy_editor,
    update_copy_editor,
)

copy_admin_dashboard_routes = Blueprint(
    "copy_admin_dashboard_routes", __name__, url_prefix="/copy-admin-dashboard"
)


@copy_admin_dashboard_routes.route("/admin", methods=["GET"])
def admin():
    editors = get_all_copy_editors()
    return render_template("copy_admin.html", editors=editors)


@copy_admin_dashboard_routes.route("/admin/editor", methods=["POST"])
def create_editor():
    name = request.form["name"]
    email = request.form["email"]
    add_copy_editor(name=name, email=email)
    return redirect(url_for("copy_admin_dashboard_routes.admin"))


@copy_admin_dashboard_routes.route("/admin/editor/<int:uid>/delete", methods=["POST"])
def delete_editor(uid):
    delete_copy_editor(uid)
    return redirect(url_for("copy_admin_dashboard_routes.admin"))


@copy_admin_dashboard_routes.route("/admin/editor/<int:uid>/update", methods=["POST"])
def update_editor(uid):
    name = request.form["name"]
    email = request.form["email"]
    update_copy_editor(uid, name=name, email=email)
    return redirect(url_for("copy_admin_dashboard_routes.admin"))
