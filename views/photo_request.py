from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from util.security import restrict_to

from db.photo_request import (
    add_photo_request,
    get_all_photo_requests,
    update_photo_request,
    claim_photo_request,
    complete_photo_request,
    delete_photo_request,
)

photo_request_routes = Blueprint(
    "photo_request_routes", __name__, url_prefix="/photo-requests"
)


# dashboard — render all requests
@photo_request_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    requests = get_all_photo_requests()
    return render_template("photo_request_dashboard.html", requests=requests)


# /api/submit — create new request
@photo_request_routes.route("/api/submit", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def api_submit():
    data = request.get_json() or {}
    required = ["submitterEmail", "submitterName", "destination", "department", "memo"]
    for field in required:
        if field not in data or data[field] == "" or data[field] is None:
            return jsonify({"error": "missing required fields"}), 400

    try:
        created = add_photo_request(
            submitterEmail=data.get("submitterEmail"),
            submitterName=data.get("submitterName"),
            destination=data.get("destination"),
            department=data.get("department"),
            memo=data.get("memo"),
            specificDetails=data.get("specificDetails"),
            referenceURL=data.get("referenceURL"),
            dueDate=data.get("dueDate"),
            specificEvent=data.get("specificEvent"),
            eventDateTime=data.get("eventDateTime"),
            eventLocation=data.get("eventLocation"),
            pressPass=data.get("pressPass"),
            pressPassRequester=data.get("pressPassRequester"),
        )
        return jsonify({"message": "created", "request": created}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# /api/<uid>/claim — claim request
@photo_request_routes.route("/api/<uid>/claim", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def api_claim(uid):
    data = request.get_json() or {}
    name = data.get("photogName")
    email = data.get("photogEmail")
    if not name or not email:
        return jsonify({"error": "photogName and photogEmail required"}), 400

    updated = claim_photo_request(uid, photogName=name, photogEmail=email)
    if not updated:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "claimed", "request": updated}), 200


# /api/<uid>/complete — complete with Drive URL
@photo_request_routes.route("/api/<uid>/complete", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def api_complete(uid):
    data = request.get_json() or {}
    driveURL = data.get("driveURL")
    if not driveURL:
        return jsonify({"error": "driveURL required"}), 400

    updated = complete_photo_request(uid, driveURL=driveURL)
    if not updated:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "completed", "request": updated}), 200


# /api/<uid>/remove — delete
@photo_request_routes.route("/api/<uid>/remove", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def api_remove(uid):
    ok = delete_photo_request(uid)
    if not ok:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "deleted"}), 200


# /api/<uid>/modify — update
@photo_request_routes.route("/api/<uid>/modify", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def api_modify(uid):
    data = request.get_json() or {}
    updated = update_photo_request(uid, **data)
    if not updated:
        return jsonify({"error": "not found or no changes"}), 400
    return jsonify({"message": "updated", "request": updated}), 200
