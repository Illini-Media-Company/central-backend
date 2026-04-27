from flask import Blueprint, render_template

followup_tracker_routes = Blueprint(
    "followup_tracker_routes", __name__, url_prefix="/followup-tracker"
)


@followup_tracker_routes.route("/", methods=["GET"])
def dashboard():
    return render_template("followup_tracker.html")
