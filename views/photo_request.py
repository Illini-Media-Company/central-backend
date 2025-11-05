from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from util.security import restrict_to
from zoneinfo import ZoneInfo
from datetime import datetime

from util.photo_request import (
    build_blocks_from_request,
    dm_user_by_email,
    post_photo_blocks,
    _label_for_request,
    send_claimer_confirmation,
)


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


# /dashboard — render photo requests based on selection (defaults to all requests)


@photo_request_routes.route("/dashboard/<selection>", methods=["GET"])
@photo_request_routes.route(
    "/dashboard", defaults={"selection": "all"}, methods=["GET"]
)
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard(selection=None):
    print(f'Fetching "{selection}" photo requests for dashboard...')

    # Fetch the appropriate requests based on selection
    # Format the selection name to display on the dashboard
    match selection:
        case "completed":
            requests = get_completed_photo_requests()
            selection_name = "Completed Requests"
        case "in-progress":
            requests = get_inprogress_photo_requests()
            selection_name = "In-Progress Requests"
        case "claimed":
            requests = get_claimed_photo_requests()
            selection_name = "Claimed Requests"
        case "unclaimed":
            requests = get_unclaimed_photo_requests()
            selection_name = "Unclaimed Requests"
        case "claimed-email":
            email = request.args.get("email")
            requests = get_claimed_photo_requests_for_user(email)
            selection_name = f"Requests Claimed by {email}"
        case "completed-email":
            email = request.args.get("email")
            requests = get_completed_photo_requests_for_user(email)
            selection_name = f"Requests Completed by {email}"
        case "submitted-email":
            email = request.args.get("email")
            requests = get_submitted_photo_requests_for_user(email)
            selection_name = f"Requests Submitted by {email}"
        case "all":
            requests = get_all_photo_requests()
            selection_name = "All Requests"
        case _:
            return "Invalid request selection", 404

    print("Fetched.")
    return render_template(
        "photo-req/photo_req_sheet.html", requests=requests, selection=selection_name
    )


# /form — form to submit a request
@photo_request_routes.route("/form", methods=["GET"])
@login_required
def form():
    return render_template("photo-req/photo_req_form.html")


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

    print("All required fields present, submitting photo request...")

    kwargs = {
        "submitterEmail": data.get("submitterEmail"),
        "submitterName": data.get("submitterName"),
        "destination": data.get("destination"),
        "department": data.get("department"),
        "memo": data.get("memo"),
        "specificDetails": data.get("specificDetails"),
        "referenceURL": data.get("referenceURL"),
        "dueDate": datetime.strptime(data.get("dueDate"), "%Y-%m-%d").date(),
        "moreInfo": data.get("moreInfo"),
        "isCourtesy": data.get("isCourtesy"),
        "specificEvent": data.get("specificEvent"),
        "eventLocation": data.get("eventLocation"),
        "pressPass": data.get("pressPass"),
        "pressPassRequester": data.get("pressPassRequester"),
    }

    # Only want eventDateTime if it was actually set otherwise it will error
    if data.get("eventDateTime"):
        kwargs["eventDateTime"] = datetime.strptime(
            data.get("eventDateTime"), "%Y-%m-%dT%H:%M"
        )

    try:
        created = add_photo_request(**kwargs)

        # Build the Slack blocks from the saved record
        blocks = build_blocks_from_request(created)

        # DM the requester a copy (always)
        try:
            dm_user_by_email(
                email=created["submitterEmail"],
                text="We got your request. Here’s a copy of your submission.",
                blocks=blocks,
            )
        except Exception as e:
            print(f"[photo_submit] DM failed: {e}")

        # Post to photo channel unless it's a courtesy request
        if not created.get("isCourtesy"):
            try:
                res = post_photo_blocks(
                    blocks=blocks,
                    request_id=str(created["uid"]),
                )
                # If posting succeeded, store channel + ts so we can update later
                if isinstance(res, dict) and res.get("ok"):
                    try:
                        update_photo_request(
                            uid=int(created["uid"]),
                            slackChannel=res.get("channel"),
                            slackTs=res.get("ts"),
                        )
                        # also mirror status explicitly, though add_photo_request defaulted to submitted
                        update_photo_request(
                            uid=int(created["uid"]), status="submitted"
                        )
                    except Exception as _e:
                        print(f"[photo_submit] storing slack ids failed: {_e}")

            except Exception as e:
                print(f"[photo_submit] Channel post failed: {e}")

        return jsonify({"message": "submitted", "request": created}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# /api/<uid>/claim — claim request
@photo_request_routes.route("/api/<uid>/claim", methods=["POST"])
@login_required
@restrict_to(["imc-staff-photo", "imc-staff-webdev"])
def api_claim(uid):
    print(f"Claiming photo request {uid}...")
    data = request.get_json() or {}
    name = data.get("photogName")
    email = data.get("photogEmail")
    if not name or not email:
        print("Missing photogName or photogEmail.")
        return jsonify({"error": "photogName and photogEmail required"}), 400

    # DB: mark as claimed
    updated = claim_photo_request(uid=int(uid), photogName=name, photogEmail=email)
    if not updated:
        return jsonify({"error": "not found"}), 400

    label = _label_for_request(req or {})
    send_claimer_confirmation(
        request_id=request_id, label=label, user_id=user_id, email=claimer_email
    )

    # Update the original channel message to reflect 'claimed'
    try:
        from util.photo_request import update_message_blocks, build_blocks_from_request

        ch = updated.get("slackChannel")
        ts = updated.get("slackTs")
        if ch and ts:
            new_blocks = build_blocks_from_request(updated)

            # remove any action buttons in the original post
            new_blocks = [b for b in new_blocks if b.get("type") != "actions"]

            # append claimed-by context to match Slack-claim flow
            claimer_name = name or email
            claimer_display = f"*Claimed by* {claimer_name}"
            claimer_block = {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"✅ {claimer_display}"},
                    {"type": "mrkdwn", "text": f"*Request ID:* `{uid}`"},
                ],
            }

            # avoid duplicating context footer if it already exists
            if not any(
                "Claimed" in (el.get("text") or "")
                for b in new_blocks
                if b.get("type") == "context"
                for el in b.get("elements", [])
            ):
                new_blocks.append(claimer_block)

            update_message_blocks(ch, ts, new_blocks, text="Photo request (claimed)")

    except Exception as e:
        print(f"[api_claim] Slack update failed: {e}")

    # notify the requester
    try:
        from util.photo_request import dm_user_by_email as _dm

        submitter = updated.get("submitterEmail")
        if submitter:
            label = _label_for_request(req or {})
            _dm(
                email=submitter,
                text=f"📸 Your photo request #{label} has been *claimed* by {name}.",
            )
    except Exception as e:
        print(f"[api_claim] DM to requester failed: {e}")

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

    # Update the Slack channel post to reflect "completed" and show Drive link
    try:
        from util.photo_request import update_message_blocks, build_blocks_from_request

        ch = updated.get("slackChannel")
        ts = updated.get("slackTs")
        if ch and ts:
            new_blocks = build_blocks_from_request(updated)
            new_blocks = [b for b in new_blocks if b.get("type") != "actions"]
            update_message_blocks(ch, ts, new_blocks, text="Photo request (completed)")
    except Exception as e:
        print(f"[api_complete] Slack update failed: {e}")

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


# # /api/fetch/completed — get all completed requests
# @photo_request_routes.route("/api/fetch/completed", methods=["GET"])
# @login_required
# def api_fetch_completed():
#     requests = get_completed_photo_requests()
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# # /api/fetch/in-progress — get all in-progess requests
# @photo_request_routes.route("/api/fetch/in-progress", methods=["GET"])
# @login_required
# def api_fetch_inprogress():
#     requests = get_inprogress_photo_requests()
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# # /api/fetch/claimed — get all claimed requests
# @photo_request_routes.route("/api/fetch/claimed", methods=["GET"])
# @login_required
# def api_fetch_claimed():
#     requests = get_claimed_photo_requests()
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# # /api/fetch/unclaimed — get all unclaimed requests
# @photo_request_routes.route("/api/fetch/unclaimed", methods=["GET"])
# @login_required
# def api_fetch_unclaimed():
#     requests = get_unclaimed_photo_requests()
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# # /api/fetch/claimed/<email> — get all requests claimed by a user with specified email
# @photo_request_routes.route("/api/fetch/claimed/<email>", methods=["GET"])
# @login_required
# def api_fetch_claimed_email(email):
#     requests = get_claimed_photo_requests_for_user(email)
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# # /api/fetch/completed/<email> — get all requests completed by a user with specified email
# @photo_request_routes.route("/api/fetch/completed/<email>", methods=["GET"])
# @login_required
# def api_fetch_completed_email(email):
#     requests = get_completed_photo_requests_for_user(email)
#     if not requests:
#         return "Requests not found.", 400
#     return requests, 200


# /api/fetch/submitted/<email> — get all requests submitted by a user with specified email
@photo_request_routes.route("/api/fetch/submitted/<email>", methods=["GET"])
@login_required
def api_fetch_submitted_email(email):
    print(f"Fetching submitted photo requests for {email}...")
    requests = get_submitted_photo_requests_for_user(email)

    return render_template(
        "photo-req/photo_req_sheet.html",
        requests=requests,
        selection="Your Requests",
        hide_extras=True,
    )
