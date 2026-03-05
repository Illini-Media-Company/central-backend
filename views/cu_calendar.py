from flask import Blueprint, request, jsonify
from flask_login import login_required
from flask_cors import cross_origin

from db.cu_calender import (
    get_future_public_events,
    center_val,
    add_event,
    remove_event,
    get_pending_events,
    accept_event,
    delete_expired_events,
    get_event_by_id)

from util.cu_calendar import geocode_address, gcal_to_events



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


#get individual events from form 
@calendar_routes.route("/submit", methods=["POST"])
@cross_origin()
@csrf.exempt
def submit_calendar_item():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("address"):
        return jsonify({"error": "Missing required fields (title and address)."}), 400
    
    new_event = add_event(
        title=data.get("title"),
        lat=None, 
        long=None, 
        url=data.get("url"),
        start_date=data.get("start_date"), 
        end_date=data.get("end_date"),
        image=data.get("image"),
        address=data.get("address"),
        event_type=data.get("event_type"),
        description=data.get("description"),
        company_name=data.get("company_name"),
        is_accepted=False
    )
    return jsonify({"message": "Event submitted for IMC approval!", "uid": new_event['uid']}), 201
    

#admin routes 
#regular events
@admin_calendar_routes.route("/pending", methods=["GET"])
@login_required
def list_pending_events():
    return jsonify(get_pending_events()), 200



@admin_calendar_routes.route("/source/add", methods=["POST"])
@login_required
def add_and_process_source():
    data = request.get_json()
    gcal_url = data.get("gcal_url")
    company = data.get("company_name") 

    if not gcal_url:
        return jsonify({"error": "Missing gcal_url"}), 400
    
    parsed_events = gcal_to_events(gcal_url)

    if parsed_events is None:
        return jsonify({"error": "Failed to parse Google Calendar URL."}), 400
    
    for event in parsed_events:
        coords = geocode_address(event.get("address"))
        
        if coords:
            lat, lng = coords
            # 3. Save directly as an accepted event
            add_event(
                title=event.get("title"),
                lat=lat,
                long=lng,
                url=gcal_url,
                start_date=event.get("start_date"),
                end_date=event.get("end_date"),
                image=None, 
                address=event.get("address"),
                event_type="Imported", 
                description=event.get("description"),
                company_name=company,
                is_accepted=True # Direct to map
            )
    return jsonify({"message": f"Successfully imported events!"}), 200



@admin_calendar_routes.route("/<uid>/accept", methods=["POST"])
@login_required
def accept_pending_event(uid):
    if not uid:
        return jsonify({"error": "Invalid Event ID format."}), 400
    

    event = get_event_by_id(uid)
    if not event:
        return jsonify({"error": "Event not found."}), 404
    
    address = event.get("address")

    coords = geocode_address(address)
    if not coords:
        return jsonify({"error": "Failed to geocode address."}), 400
    
    lat, lng = coords


    success = accept_event(uid, lat, lng)
    if not success:
        return jsonify({"error": "Event not found or already accepted."}), 404
    
    return jsonify({"message": "Event accepted!"}), 200

