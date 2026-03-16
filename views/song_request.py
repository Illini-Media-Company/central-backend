from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from util.security import restrict_to

from db.song_request import (
    create_song_request,
    get_all_song_requests,
    update_request_status,
    update_slack_ts
)


song_request_routes = Blueprint(
    "song_request_routes", __name__, url_prefix="/wpgu-song-requests"
)

@song_request_routes.route("/form", methods=["GET"])
def form():
    is_logged_in = current_user.is_authenticated
    return render_template(
        "wpgu-song-req/wpgu_song_req_form.html", 
        is_logged_in=is_logged_in
    )

# Dashboard Routes 
@song_request_routes.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """
    Simple dashboard to verify backend data.
    Access at: /wpgu-song-requests/dashboard
    """
    requests = get_all_song_requests()
    return render_template("wpgu-song-req/wpgu_song_req_dashboard.html", requests=requests)   


@song_request_routes.route("/api/<uid>/approve", methods=["POST"])
@login_required
@restrict_to(["wpgu-music", "imc-staff-webdev"])
def api_approve(uid):
    """Marks a song request as accepted."""
    reviewer_name = current_user.name
    
    updated = update_request_status(uid, "accepted", reviewer_name=reviewer_name)
    if not updated:
        return jsonify({"error": "Request not found."}), 404
        
    # TODO: Update original Slack message and DM user update
    return jsonify({"message": "Song approved!", "request": updated.to_dict()}), 200


@song_request_routes.route("/api/<uid>/deny", methods=["POST"])
@login_required
@restrict_to(["wpgu-music", "imc-staff-webdev"])
def api_deny(uid):
    """Marks a song request as declined and saves the reasoning."""
    data = request.get_json() or {}
    rejection_reason = data.get("rejection_reason")
    reviewer_name = current_user.name
    
    updated = update_request_status(uid, "declined", reviewer_name=reviewer_name, rejection_reason=rejection_reason)
    if not updated:
        return jsonify({"error": "Request not found."}), 404
        
    # TODO: Update original Slack message and DM user update
    return jsonify({"message": "Song denied.", "request": updated.to_dict()}), 200

