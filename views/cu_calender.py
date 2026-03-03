from flask import Blueprint, request, jsonify
from flask_login import login_required
from flask_cors import cross_origin

from db.cu_calender import (
    get_future_public_events,
    center_val,
    add_event,
    remove_event,
    get_pending_events,
    accept_event
)


from util.security import restrict_to, csrf
from datetime import datetime

calendar_routes = Blueprint("calendar_routes", __name__, url_prefix="/cu-calendar")
admin_calendar_routes = Blueprint("admin_calendar_routes", __name__, url_prefix="/admin/cu-calendar")


#public routes 
@calendar_routes.route("/events", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_public_events():
    return jsonify(get_future_public_events()), 200

@calendar_routes.route("/center", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_map_center():
    center = center_val()
    return jsonify({"lat": center[0], "long": center[1]}), 200


#admin routes 

@admin_calendar_routes.route("/pending", methods=["GET"])
@login_required
def list_pending_events():
    return jsonify(get_pending_events()), 200

@admin_calendar_routes.route("/<uid>/accept", methods=["POST"])
@login_required
def accept_pending_event(uid):
    if not uid:
        return jsonify({"error": "Invalid Event ID format."}), 400
    success = accept_event(uid)

    if not success:
        return jsonify({"error": "Event not found or already accepted."}), 404
    
    return jsonify({"message": "Event accepted!"}), 200

