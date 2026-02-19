from flask import Blueprint, render_template

copy_admin_dashboard_routes = Blueprint(
    "copy_admin_dashboard_routes", __name__, url_prefix="/copy-admin-dashboard"
)


@copy_admin_dashboard_routes.route("/admin", methods=["GET"])
def admin():
    return render_template("copy_admin.html")
