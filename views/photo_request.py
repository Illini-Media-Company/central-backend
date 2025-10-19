from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from util.security import restrict_to
from datetime import datetime

from db.photo_request import (
    add_photo_request,
    get_all_photo_requests,
    update_photo_request,
    claim_photo_request,
    complete_photo_request,
    delete_photo_request,
    get_photo_request_by_uid,
    get_completed_photo_requests,
    get_inprogress_photo_requests,
    get_claimed_photo_requests,
    get_unclaimed_photo_requests,
    get_claimed_photo_requests_for_user,
    get_completed_photo_requests_for_user,
    get_submitted_photo_requests_for_user,
)

photo_request_routes = Blueprint(
    "photo_request_routes", __name__, url_prefix="/photo-requests"
)


# /dashboard — render all requests
@photo_request_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    requests = get_all_photo_requests()
    return render_template("/photo-req/photo_req_dashboard.html", requests=requests)


# /form — form to submit a request
@photo_request_routes.route("/form", methods=["GET"])
@login_required
def form():
    return render_template("/photo-req/photo_req_form.html")


# /api/submit — create new request
@photo_request_routes.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    data = request.get_json() or {}
    required = [
        "submitterEmail",
        "submitterName",
        "destination",
        "memo",
        "specificDetails",
        "dueDate",
        "isCourtesy",
    ]
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
            dueDate=datetime(data.get("dueDate")),
            moreInfo=data.get("moreInfo"),
            isCourtesy=True if data.get("isCourtesy") == "true" else False,
            specificEvent=True if data.get("specificEvent") == "true" else False,
            eventDateTime=datetime(data.get("eventDateTime")),
            eventLocation=data.get("eventLocation"),
            pressPass=True if data.get("pressPass") == "true" else False,
            pressPassRequester=data.get("pressPassRequester"),
        )
        return jsonify({"message": "submitted", "request": created}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# /api/<uid>/claim — claim request
@photo_request_routes.route("/api/<uid>/claim", methods=["POST"])
@login_required
@restrict_to(["imc-staff-photo" "imc-staff-webdev"])
def api_claim(uid):
    data = request.get_json() or {}
    name = data.get("photogName")
    email = data.get("photogEmail")
    if not name or not email:
        return jsonify({"error": "photogName and photogEmail required"}), 400

    updated = claim_photo_request(uid=int(uid), photogName=name, photogEmail=email)
    if not updated:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "claimed", "request": updated}), 200


# /api/<uid>/complete — complete with Drive URL
@photo_request_routes.route("/api/<uid>/complete", methods=["POST"])
@login_required
@restrict_to(["imc-staff-photo", "imc-staff-webdev"])
def api_complete(uid):
    data = request.get_json() or {}
    driveURL = data.get("driveURL")
    if not driveURL:
        return jsonify({"error": "driveURL required"}), 400

    updated = complete_photo_request(uid=int(uid), driveURL=driveURL)
    if not updated:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "completed", "request": updated}), 200


# /api/<uid>/remove — delete a request
@photo_request_routes.route("/api/<uid>/remove", methods=["POST"])
@login_required
@restrict_to(["photo", "imc-staff-webdev"])
def api_remove(uid):
    ok = delete_photo_request(int(uid))
    if not ok:
        return jsonify({"error": "not found"}), 400
    return jsonify({"message": "deleted"}), 200


# /api/<uid>/modify — update an existing request
@photo_request_routes.route("/api/<uid>/modify", methods=["POST"])
@login_required
@restrict_to(["photo", "imc-staff-webdev"])
def api_modify(uid):
    data = request.get_json() or {}
    updated = update_photo_request(uid=int(uid), **data)
    if not updated:
        return jsonify({"error": "not found or no changes"}), 400
    return jsonify({"message": "updated", "request": updated}), 200


# —————————————————————————————————————————————————————————————————————— #


# /api/<uid>/get — get a specific request
@photo_request_routes.route("/api/<uid>/get", methods=["GET"])
@login_required
@restrict_to(["imc-staff-photo", "imc-staff-webdev"])
def api_get(uid):
    req = get_photo_request_by_uid(int(uid))
    if not req:
        return "Request not found.", 400
    return req, 200


# /api/fetch/all — get all requests
@photo_request_routes.route("/api/fetch/all", methods=["GET"])
@login_required
def api_fetch_all():
    requests = get_all_photo_requests()
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/completed — get all completed requests
@photo_request_routes.route("/api/fetch/completed", methods=["GET"])
@login_required
def api_fetch_completed():
    requests = get_completed_photo_requests()
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/in-progress — get all in-progess requests
@photo_request_routes.route("/api/fetch/in-progress", methods=["GET"])
@login_required
def api_fetch_inprogress():
    requests = get_inprogress_photo_requests()
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/claimed — get all claimed requests
@photo_request_routes.route("/api/fetch/claimed", methods=["GET"])
@login_required
def api_fetch_claimed():
    requests = get_claimed_photo_requests()
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/unclaimed — get all unclaimed requests
@photo_request_routes.route("/api/fetch/unclaimed", methods=["GET"])
@login_required
def api_fetch_unclaimed():
    requests = get_unclaimed_photo_requests()
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/claimed/<email> — get all requests claimed by a user with specified email
@photo_request_routes.route("/api/fetch/claimed/<email>", methods=["GET"])
@login_required
def api_fetch_claimed_email(email):
    requests = get_claimed_photo_requests_for_user(email)
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/completed/<email> — get all requests completed by a user with specified email
@photo_request_routes.route("/api/fetch/completed/<email>", methods=["GET"])
@login_required
def api_fetch_completed_email(email):
    requests = get_completed_photo_requests_for_user(email)
    if not requests:
        return "Requests not found.", 400
    return requests, 200


# /api/fetch/submitted/<email> — get all requests submitted by a user with specified email
@photo_request_routes.route("/api/fetch/submitted/<email>", methods=["GET"])
@login_required
def api_fetch_submitted_email(email):
    requests = get_submitted_photo_requests_for_user(email)
    if not requests:
        return "Requests not found.", 400
    return requests, 200
