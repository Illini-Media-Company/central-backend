from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from util.security import restrict_to

from db.song_request import (
    create_song_request,
    get_all_song_requests,
    update_request_status,
    delete_all_song_requests
)
from util.song_request import send_song_request_update_email
song_request_routes = Blueprint(
    "song_request_routes", __name__, url_prefix="/wpgu-song-requests"
)

# Form Routes
@song_request_routes.route("/form", methods=["GET", "POST"])
def form():
    is_logged_in = current_user.is_authenticated

    if request.method == "POST":
        data = request.get_json()
        
        song_name = data.get("song_name")
        artist_name = data.get("artist_name")
        is_employee = data.get("is_employee", False)
        
        submitter_name = None
        submitter_email = data.get("email")
        submitter_slack_id = None
        
        # If they claim to be an employee and are authenticated, use session data
        if is_employee and is_logged_in:
            submitter_name = current_user.name
            submitter_email = current_user.email
            submitter_slack_id = getattr(current_user, 'slack_id', None) 
            
        # Create the database record
        new_request = create_song_request(
            song_name=song_name,
            artist_name=artist_name,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            is_imc_employee=is_employee,
            submitter_slack_id=submitter_slack_id
        )
        
        # TODO: Trigger Slack message to #wpgu_song-requests here
        # TODO: Trigger Slack confirmation DM to employee here
        
        return jsonify({
            "message": "Song request submitted successfully!", 
            "uid": new_request.key.id() if new_request.key else None
        }), 200

    # Handle GET request
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
    return render_template("wpgu-song-req/wpgu_song_req_dashboard.html") 

@song_request_routes.route("/get-requests", methods=["GET"])
@login_required
def get_requests():
    """Returns all song requests in JSON format."""
    requests = get_all_song_requests()
    
    results = []
    for req in requests:
        req_dict = req.to_dict()
        if req_dict.get('timestamp'):
            req_dict['timestamp'] = req_dict['timestamp'].isoformat() + 'Z'
        
        req_dict['uid'] = req.key.id() if req.key else None
        results.append(req_dict)
        
    return jsonify(results), 200

@song_request_routes.route("/api/<uid>/claim", methods=["POST"])
@login_required
def api_claim(uid):
    """Allows a user to claim a song request for review."""
    reviewer_name = current_user.name
    
    updated = update_request_status(uid, "in_progress", reviewer_name=reviewer_name)
    if not updated:
        return jsonify({"error": "Request not found."}), 404
    
    # TODO: Update original Slack message to remove Approve/Deny buttons 
    # and say "Currently being reviewed by [Name]"

    return jsonify({"message": f"Request claimed by {reviewer_name}!", "request": updated.to_dict()}), 200

@song_request_routes.route("/clear-all", methods=["POST", "DELETE"])
@login_required
@restrict_to(["imc-staff-webdev"]) 
def api_clear_all():
    """Wipes all song requests from the database for storage cleanup."""
    deleted_count = delete_all_song_requests()
    
    return jsonify({
        "message": f"Successfully deleted {deleted_count} song requests."
    }), 200


@song_request_routes.route("/api/<uid>/approve", methods=["POST"])
@login_required
def api_approve(uid):
    """Marks a song request as accepted."""
    reviewer_name = current_user.name
    
    updated = update_request_status(uid, "accepted", reviewer_name=reviewer_name)
    if not updated:
        return jsonify({"error": "Request not found."}), 404
    
    if not updated.is_imc_employee and updated.submitter_email:
        send_song_request_update_email(
            to_email=updated.submitter_email,
            song_name=updated.song_name,
            artist_name=updated.artist_name,
            status="accepted"
        )

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
    
    if not updated.is_imc_employee and updated.submitter_email:
        send_song_request_update_email(
            to_email=updated.submitter_email,
            song_name=updated.song_name,
            artist_name=updated.artist_name,
            status="declined",
            rejection_reason=rejection_reason
    )

    # TODO: Update original Slack message and DM user update
    return jsonify({"message": "Song denied.", "request": updated.to_dict()}), 200