from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from flask_cors import cross_origin
from db.food_truck import (
    add_truck_loctime_repeat,
    remove_truck_loctime_repeat,
    register_food_truck,
    deregister_food_truck,
    modify_food_truck,
    get_all_registered_trucks,
    get_registration_by_id,
    add_truck_loctime,
    remove_truck_loctime,
    modify_truck_loctime,
    get_all_loctimes_for_truck,
    get_loctime_by_id,
    get_all_trucks_with_loctimes,
    check_existing_loctime,
    check_existing_loctime_notruck,
    get_all_cuisines,
)
from util.security import restrict_to, csrf
from datetime import datetime
from db import client
import logging
from constants import GOOGLE_MAP_API, FOOD_TRUCK_MAPS_ID

from util.google_analytics import send_ga4_event
from constants import IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID


logger = logging.getLogger(__name__)


food_truck_routes = Blueprint("food_truck_routes", __name__, url_prefix="/food-truck")


# Admin page, renders food_truck_admin.html
# Gets all registered food trucks
@food_truck_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def admin():
    with client.context():
        trucks = get_all_registered_trucks()
    return render_template("food_truck_admin.html", registered=trucks)


# Dashboard page, renders food_truck_dash.html
@food_truck_routes.route("/dashboard", methods=["GET"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    with client.context():
        email = request.args.get("login_email")
        uid = request.args.get("login_uid")
        source = request.args.get("login_source")
        google_maps_api_key = GOOGLE_MAP_API
        food_truck_map_id = FOOD_TRUCK_MAPS_ID

        # This does not execute on the first load (since email and uid are undefined)
        # When the page reloads when the user clicks the "Find" button, this executes
        if email and uid:
            uid = int(uid)
            truck = next(
                (
                    truck
                    for truck in get_all_registered_trucks()
                    if truck["email"] == email and truck["uid"] == uid
                ),
                None,
            )
            loc_times = get_all_loctimes_for_truck(uid)
        else:
            truck = []
            loc_times = []

        if source:
            source_str = source
        else:
            source_str = None

    logger.debug("Done.")
    return render_template(
        "food_truck_dash.html",
        truck=truck,
        loc_times=loc_times,
        login_email=email,
        login_source=source_str,
        login_uid=uid,
        google_maps_api_key=google_maps_api_key,
        food_truck_map_id=food_truck_map_id,
    )


################################################################


# Register a new food truck
@food_truck_routes.route("/register", methods=["POST"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def register_truck():
    with client.context():
        name = request.form["name"]
        cuisine = request.form["cuisine"]
        emoji = request.form["emoji"]
        url = request.form["url"]
        email = request.form["email"]

        register_food_truck(
            name=name, cuisine=cuisine, emoji=emoji, url=url, email=email
        )

    return "Food truck registered", 200


# Deregister a food truck (Given the truck's UID)
@food_truck_routes.route("/deregister/<uid>", methods=["POST"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def deregister_truck(uid):
    with client.context():
        if uid.isdigit() and deregister_food_truck(int(uid)):
            return "Food truck deregistered.", 200
        else:
            logger.error("Failed.")
            return "Food truck not found.", 404


# Modify a food truck's registration (Given the truck's UID)
@food_truck_routes.route("/register/<uid>", methods=["POST"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def modify_truck(uid):
    with client.context():
        name = request.form["name"]
        cuisine = request.form["cuisine"]
        emoji = request.form["emoji"]
        url = request.form["url"]
        email = request.form["email"]

        modify_food_truck(
            uid=int(uid), name=name, cuisine=cuisine, emoji=emoji, url=url, email=email
        )

    return "Food truck modified", 200


# Get a food truck's registration (Given the truck's UID)
@food_truck_routes.route("/registration/<uid>", methods=["GET"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def get_registration(uid):
    with client.context():
        if uid.isdigit():
            return get_registration_by_id(int(uid))
        else:
            return "Invalid UID", 400


################################################################


# Add a new locTime for a truck (ACCESSED WITHOUT LOGIN)
# Will add a repeating time if "repeat" is checked
@food_truck_routes.route("/loctime", methods=["POST"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def add_loctime():
    """
    API endpoint to add a loctime for a food truck

    Returns:
        (str, int): A tuple containing a message and a HTTP status code

    """
    with client.context():
        truck_uid = float(request.form["uid"])
        latitude = float(request.form["lat"])
        longitude = float(request.form["lon"])
        nearest_address = request.form["nearest_address"]
        location_desc = request.form["location_desc"]
        start_time = datetime.strptime(request.form["start_time"], "%Y-%m-%dT%H:%M")
        end_time = datetime.strptime(request.form["end_time"], "%Y-%m-%dT%H:%M")
        reported_by = request.form["reported_by"]
        repeat = request.form.get("repeat") is not None
        repeat_end_raw = request.form.get("repeat_end", "").strip()

        if check_existing_loctime(truck_uid, start_time, end_time):
            return "Invalid: An existing time overlaps with the requested time.", 422

        if not repeat:
            add_truck_loctime(
                truck_uid=truck_uid,
                lat=latitude,
                lon=longitude,
                nearest_address=nearest_address,
                location_desc=location_desc,
                start_time=start_time,
                end_time=end_time,
                reported_by=reported_by,
            )

            return "locTime created", 200
        else:
            end_date = datetime.strptime(repeat_end_raw, "%Y-%m-%d").date()

            add_truck_loctime_repeat(
                truck_uid=truck_uid,
                lat=latitude,
                lon=longitude,
                nearest_address=nearest_address,
                location_desc=location_desc,
                start_time=start_time,
                end_time=end_time,
                reported_by=reported_by,
                end_date=end_date,
            )

            return "repeating locTime created", 200


# Remove a locTime for a truck (given the locTime's UID) (ACCESSED WITHOUT LOGIN)
@food_truck_routes.route("/loctime-remove/<uid>", methods=["POST"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def remove_loctime(uid):
    with client.context():
        if uid.isdigit() and remove_truck_loctime(int(uid)):
            return "locTime removed.", 200
        else:
            return "locTime not found.", 404


# Remove all locTime's with a specific recurrence_id for a truck
@food_truck_routes.route("/loctime-remove-series/<uid>", methods=["POST"])
def remove_loctime_series(uid):
    """
    API endpoint to delete a group of repeating loctimes for a food truck

    Args:
        uid: Unique ID of a food truck

    Returns:
        (str, int): A tuple containing a message and a HTTP status code

    """
    with client.context():
        loctime = get_loctime_by_id(int(uid))

        if loctime == None:
            return "locTime not found!!!", 404

        recurrence_id = loctime.get("recurrence_id")

        if not recurrence_id:
            # guard against user trying to delete non-recurring locTime
            remove_truck_loctime(uid)
            return "Deleted 1 non-recurring locTime.", 200

        deleted = remove_truck_loctime_repeat(recurrence_id)
        return f"Deleted {deleted} recurring locTime(s).", 200


# Modify a locTime for a truck (given the locTime's UID) (ACCESSED WITHOUT LOGIN)
@food_truck_routes.route("/loctime/<uid>", methods=["POST"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def modify_loctime(uid):
    with client.context():
        lat = float(request.form["lat"])
        lon = float(request.form["lon"])
        nearest_address = request.form["nearest_address"]
        location_desc = request.form["location_desc"]
        start_time = datetime.strptime(request.form["start_time"], "%Y-%m-%dT%H:%M")
        end_time = datetime.strptime(request.form["end_time"], "%Y-%m-%dT%H:%M")
        reported_by = request.form["reported_by"]

        if check_existing_loctime_notruck(uid, start_time, end_time):
            return "Invalid: An existing time overlaps with the requested time.", 422

        modify_truck_loctime(
            uid=uid,
            lat=lat,
            lon=lon,
            nearest_address=nearest_address,
            location_desc=location_desc,
            start_time=start_time,
            end_time=end_time,
            reported_by=reported_by,
        )

    return "locTime modified", 200


# Get a locTime (given the locTime's UID) (ACCESSED WITHOUT LOGIN)
@food_truck_routes.route("/loctime/<uid>", methods=["GET"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def get_loctime(uid):
    with client.context():
        if uid.isdigit():
            return get_loctime_by_id(int(uid))
        else:
            return "Invalid UID", 400


################################################################


# Get all of the food trucks as a JSON
@food_truck_routes.route("/json", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_food_trucks_json():
    # Log in Google Analytics
    utm_source = request.args.get("utm_source", "none")
    utm_medium = request.args.get("utm_medium", "none")
    send_ga4_event(
        "foodtruck_json_fetch",
        IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID,
        {"utm_source": utm_source, "utm_medium": utm_medium},
    )

    with client.context():
        trucks_with_loctimes = get_all_trucks_with_loctimes()

        for truck in trucks_with_loctimes:
            truck.pop("email", None)
            truck.pop("uid", None)

            for loc in truck.get("loc_times", []):
                loc.pop("uid", None)

    return jsonify(trucks_with_loctimes)


# Get all of the registered cuisines as a JSON
@food_truck_routes.route("/cuisines", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_cuisines_json():
    with client.context():
        cuisines = get_all_cuisines()
    return jsonify(cuisines)


# # List all of the food trucks
# @food_truck_routes.route("/", methods=["GET"])
# @login_required
# @restrict_to(["student-managers", "editors", "imc-staff-webdev"])
# def list_food_trucks():
#     return get_all_food_trucks()


################################################################
