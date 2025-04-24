from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from flask_cors import cross_origin
from db.map_point import (
    get_all_points,
    remove_point,
    get_next_points,
    center_val,
)
from util.security import restrict_to, csrf
from util.map_point import add
from datetime import datetime
from util.map_point import scheduler
from db.json_store import json_store_get

map_points_routes = Blueprint("map_points_routes", __name__, url_prefix="/map-points")


@map_points_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    points = get_next_points(10)
    return render_template("map_point.html", recent_points=points)


@map_points_routes.route("/", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def list_map_points():
    return get_all_points()


@map_points_routes.route("/json", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_map_points_json():
    return jsonify(get_all_points())


@map_points_routes.route("/", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def create_map_point():
    latitude = float(request.form["lat"])
    longitude = float(request.form["long"])
    url = request.form["url"]
    title = request.form["title"]
    image = request.form["image"]
    address = request.form["address"]
    start_date = datetime.strptime(request.form["start-date"], "%Y-%m-%dT%H:%M")
    end_date = datetime.strptime(request.form["end-date"], "%Y-%m-%dT%H:%M")

    add(
        title=title,
        lat=latitude,
        long=longitude,
        url=url,
        start_date=start_date,
        end_date=end_date,
        image=image,
        address=address,
    )

    return "Map point created", 200


@map_points_routes.route("/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def delete_map_point(uid):
    if uid.isdigit() and remove_point(int(uid)):
        return "Map Point deleted.", 200
    else:
        return "Map Point not found.", 404


@map_points_routes.route("/center", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_center():
    center = center_val()
    return jsonify({"lat_center": center[0], "long_center": center[1]})


@map_points_routes.route("/scheduler", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def print_jobs():
    print(type(json_store_get("MAP_JOBS")))
    return json_store_get("MAP_JOBS") if json_store_get("MAP_JOBS") else "None", 200

@map_points_routes.route("/copy-edit-scheduler", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def print_jobs():
    print(type(json_store_get("COPY_EDITING_JOBS")))
    return json_store_get("COPY_EDITING_JOBS") if json_store_get("COPY_EDITING_JOBS") else "None", 200

@map_points_routes.route("/check-jobs", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def jobs():
    scheduler.print_jobs()
    json = []
    job_list = scheduler.get_jobs()
    for job in job_list:
        json.append({"id": job.id, "runtime": job.next_run_time})
    return jsonify(json), 200




@map_points_routes.route("/clear-scheduler", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def clear():
    scheduler.remove_all_jobs()
    return "cleared MAP_POINTS scheduler", 200
