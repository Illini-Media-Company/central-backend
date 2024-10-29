from flask import Blueprint, render_template, request
from flask_login import login_required

from db.map_point import get_all_points, add_point, remove_point, get_recent_points
from util.security import restrict_to


map_points_routes = Blueprint(
    "map_points_routes", __name__, url_prefix="/map-points"
)


@map_points_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    points = get_recent_points(10)
    return render_template('map_point.html', recent_points = points)


@map_points_routes.route("/", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def list_map_points():
    return get_all_points()


@map_points_routes.route("/", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def create_map_point():
    latitude = float(request.form["lat"])
    longitude = float(request.form["long"])
    url = request.form["url"]

    return add_point(latitude, longitude, url)


@map_points_routes.route("/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def delete_map_point(uid):
    if uid.isdigit() and remove_point(int(uid)):
        return "Map Point deleted.", 200
    else:
        return "Map Point not found.", 404
