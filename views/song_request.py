from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from util.security import restrict_to

from db.song_request import (
    create_song_request,
    get_all_song_requests,
    get_song_request_by_id,
    update_request_status,
    delete_all_song_requests,
    delete_song_request,
)
from util.song_request import (
    send_song_request_submission_email,
    send_song_request_update_email,
)
from db.song_request import update_slack_ts
from util.slackbots.general import (
    dm_channel_by_id,
    dm_user_by_email,
)
from util.slackbots.song_request import (
    delete_song_request_message,
    post_song_request_to_slack,
    update_song_request_message,
)

song_request_routes = Blueprint(
    "song_request_routes", __name__, url_prefix="/wpgu-song-requests"
)


# Form Routes
@song_request_routes.route("/form", methods=["GET", "POST"])
def form():
    is_logged_in = current_user.is_authenticated

    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        song_name = (data.get("song_name") or "").strip()
        artist_name = (data.get("artist_name") or "").strip()
        is_imc_employee = bool(data.get("is_employee")) and is_logged_in

        submitter_name = None
        submitter_email = (data.get("email") or "").strip() or None
        submitter_slack_id = None

        if not song_name or not artist_name:
            return jsonify({"error": "Song title and artist are required."}), 400

        # Only authenticated users can submit as IMC employees.
        if is_imc_employee:
            submitter_name = current_user.name
            submitter_email = current_user.email
            submitter_slack_id = getattr(current_user, "slack_id", None)

        # Create the database record
        new_request = create_song_request(
            song_name=song_name,
            artist_name=artist_name,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            is_imc_employee=is_imc_employee,
            submitter_slack_id=submitter_slack_id,
        )

        slack_res = post_song_request_to_slack(
            song_name=song_name,
            artist_name=artist_name,
            submitter_slack_id=submitter_slack_id,
            submitter_email=submitter_email,
            request_id=new_request.key.id() if new_request.key else None,
        )
        if slack_res.get("ok") and new_request.key:
            update_slack_ts(new_request.key.id(), slack_res["ts"])

        if not is_imc_employee and submitter_email:
            send_song_request_submission_email(
                to_email=submitter_email,
                song_name=song_name,
                artist_name=artist_name,
            )

        if is_imc_employee:
            if submitter_slack_id:
                dm_channel_by_id(
                    channel_id=submitter_slack_id,
                    text=f'✅ Your song request "*{song_name}*" by "*{artist_name}*" has been submitted!',
                )
            elif submitter_email:
                dm_user_by_email(
                    email=submitter_email,
                    text=f'✅ Your song request "*{song_name}*" by "*{artist_name}*" has been submitted!',
                )

        return (
            jsonify(
                {
                    "message": "Song request submitted successfully!",
                    "uid": new_request.key.id() if new_request.key else None,
                }
            ),
            200,
        )

    # Handle GET request
    return render_template(
        "wpgu-song-req/wpgu_song_req_form.html", is_logged_in=is_logged_in
    )


# Dashboard Routes
# Dashboard Routes
@song_request_routes.route("/dashboard", methods=["GET"])
@song_request_routes.route("/dashboard/<filter_type>", methods=["GET"])
@login_required
@restrict_to(["wpgu-music", "imc-staff-webdev"])
def dashboard(filter_type="all"):
    """
    Dashboard to view and manage song requests. Matches IMC styling.
    """
    all_requests = get_all_song_requests()

    # Apply filtering based on the URL parameter
    if filter_type.lower() == "pending":
        requests = [r for r in all_requests if r.status == "pending"]
        selection = "Pending Requests"
    elif filter_type.lower() == "in-progress":
        requests = [r for r in all_requests if r.status == "in_progress"]
        selection = "In-Progress Requests"
    elif filter_type.lower() == "accepted":
        requests = [r for r in all_requests if r.status == "accepted"]
        selection = "Accepted Requests"
    elif filter_type.lower() == "declined":
        requests = [r for r in all_requests if r.status == "declined"]
        selection = "Declined Requests"
    else:
        requests = all_requests
        selection = "All Requests"

    return render_template(
        "wpgu-song-req/wpgu_song_req_dashboard.html",
        requests=requests,
        selection=selection,
    )


@song_request_routes.route("/get-requests", methods=["GET"])
@login_required
def get_requests():
    """Returns all song requests in JSON format."""
    requests = get_all_song_requests()

    results = []
    for req in requests:
        req_dict = req.to_dict()
        if req_dict.get("timestamp"):
            req_dict["timestamp"] = req_dict["timestamp"].isoformat() + "Z"

        req_dict["uid"] = req.key.id() if req.key else None
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

    if updated.slack_ts:
        update_song_request_message(
            updated=updated,
            message_ts=updated.slack_ts,
            status="in_progress",
            reviewer_name=reviewer_name,
            request_id=uid,
        )

    return (
        jsonify(
            {
                "message": f"Request claimed by {reviewer_name}!",
                "request": updated.to_dict(),
            }
        ),
        200,
    )


@song_request_routes.route("/clear-all", methods=["POST", "DELETE"])
@login_required
@restrict_to(["imc-staff-webdev"])
def api_clear_all():
    """Wipes all song requests from the database for storage cleanup."""
    deleted_count = delete_all_song_requests()

    return (
        jsonify({"message": f"Successfully deleted {deleted_count} song requests."}),
        200,
    )


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
            status="accepted",
        )

    if updated.slack_ts:
        update_song_request_message(
            updated=updated,
            message_ts=updated.slack_ts,
            status="accepted",
            reviewer_name=reviewer_name,
        )
    if updated.is_imc_employee:
        if updated.submitter_slack_id:
            dm_channel_by_id(
                channel_id=updated.submitter_slack_id,
                text=f'✅ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" has been approved!',
            )
        elif updated.submitter_email:
            dm_user_by_email(
                email=updated.submitter_email,
                text=f'✅ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" has been approved!',
            )

    return jsonify({"message": "Song approved!", "request": updated.to_dict()}), 200


@song_request_routes.route("/api/<uid>/deny", methods=["POST"])
@login_required
@restrict_to(["wpgu-music", "imc-staff-webdev"])
def api_deny(uid):
    """Marks a song request as declined and saves the reasoning."""
    data = request.get_json() or {}
    rejection_reason = data.get("rejection_reason")
    reviewer_name = current_user.name

    updated = update_request_status(
        uid, "declined", reviewer_name=reviewer_name, rejection_reason=rejection_reason
    )
    if not updated:
        return jsonify({"error": "Request not found."}), 404

    if not updated.is_imc_employee and updated.submitter_email:
        send_song_request_update_email(
            to_email=updated.submitter_email,
            song_name=updated.song_name,
            artist_name=updated.artist_name,
            status="declined",
            rejection_reason=rejection_reason,
        )

    reason_text = f"\n*Reason:* {rejection_reason}" if rejection_reason else ""
    if updated.slack_ts:
        update_song_request_message(
            updated=updated,
            message_ts=updated.slack_ts,
            status="declined",
            reviewer_name=reviewer_name,
            rejection_reason=rejection_reason,
        )
    if updated.is_imc_employee:
        if updated.submitter_slack_id:
            dm_channel_by_id(
                channel_id=updated.submitter_slack_id,
                text=f'❌ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" was not approved.{reason_text}',
            )
        elif updated.submitter_email:
            dm_user_by_email(
                email=updated.submitter_email,
                text=f'❌ Your song request "*{updated.song_name}*" by "*{updated.artist_name}*" was not approved.{reason_text}',
            )

    return jsonify({"message": "Song denied.", "request": updated.to_dict()}), 200


@song_request_routes.route("/api/<uid>/remove", methods=["POST"])
@login_required
@restrict_to(["wpgu-music", "imc-staff-webdev"])
def api_remove_single(uid):
    """Deletes a single song request and removes its Slack channel message."""
    song_request = get_song_request_by_id(uid)
    if not song_request:
        return jsonify({"error": "Request not found."}), 404

    if song_request.slack_ts:
        slack_delete = delete_song_request_message(message_ts=song_request.slack_ts)
        slack_error = str(slack_delete.get("error") or "")
        if not slack_delete.get("ok") and "message_not_found" not in slack_error:
            return (
                jsonify({"error": "Failed to delete the Slack message."}),
                502,
            )

    success = delete_song_request(uid)

    if not success:
        return jsonify({"error": "Request not found."}), 404

    return jsonify({"message": "Deleted successfully"}), 200
