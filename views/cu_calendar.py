"""CU Calendar Flask routes: public API, submissions, admin dashboard.

Last modified by Cal Anderson on March 24, 2026
"""

import logging
from datetime import datetime, time, timezone

from flask import Blueprint, jsonify, request, render_template
from flask_cors import cross_origin
from flask_login import login_required
from constants import CU_CALENDAR_ID, DEFAULT_PUBLIC_EVENT_CATEGORY, GOOGLE_MAP_API
from zoneinfo import ZoneInfo

from db.cu_calender import (
    accept_event,
    add_calendar_source,
    add_event,
    center_val,
    get_event_by_id,
    get_future_public_events,
    get_pending_events,
    highlight_event as db_highlight_event,
    remove_event as db_remove_event,
    event_exists,
    get_all_calendar_sources,
    get_public_event_categories,
    normalize_public_event_category,
)
from util.cu_calendar import geocode_address, gcal_to_events, upload_images_to_gcs
from util.security import csrf

from util.slackbots.general import dm_channel_by_id

calendar_routes = Blueprint("calendar_routes", __name__, url_prefix="/cu-calendar")
admin_calendar_routes = Blueprint(
    "admin_calendar_routes", __name__, url_prefix="/admin/cu-calendar"
)
public_calendar_api_routes = Blueprint(
    "public_calendar_api_routes", __name__, url_prefix="/api/events"
)


def _safe_public_event_category(event_type):
    """
    Normalize event_type for API output; fall back to DEFAULT_PUBLIC_EVENT_CATEGORY if invalid.
    """
    try:
        return normalize_public_event_category(event_type)
    except ValueError:
        return DEFAULT_PUBLIC_EVENT_CATEGORY


def _serialize_datetime(value):
    """Format a datetime for JSON (ISO); pass through non-datetimes."""

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat()
        return value.isoformat() + "Z"
    return value


def _serialize_public_event(event):
    """JSON shape for /api/events (no submitter fields)."""

    return {
        "uid": event.get("uid"),
        "title": event.get("title"),
        "description": event.get("description"),
        "event_type": _safe_public_event_category(event.get("event_type")),
        "highlight": bool(event.get("highlight", False)),
        "start_date": _serialize_datetime(event.get("start_date")),
        "end_date": _serialize_datetime(event.get("end_date")),
        "address": event.get("address"),
        "lat": event.get("lat"),
        "long": event.get("long"),
        "url": event.get("url"),
        "images": [image for image in (event.get("images") or []) if image],
    }


def _serialize_legacy_public_event(event):
    """JSON shape for legacy /cu-calendar endpoints."""

    serialized = dict(event)
    serialized["event_type"] = _safe_public_event_category(event.get("event_type"))
    serialized["start_date"] = _serialize_datetime(event.get("start_date"))
    serialized["end_date"] = _serialize_datetime(event.get("end_date"))
    serialized["created_at"] = _serialize_datetime(event.get("created_at"))
    serialized["images"] = [image for image in (event.get("images") or []) if image]
    serialized.pop("submitter_name", None)
    serialized.pop("submitter_email", None)
    return serialized


def _parse_submission_datetime(raw_value, is_end=False):
    """Parse submitted date/datetime strings to Chicago time."""

    if not raw_value or not raw_value.strip():
        return None

    value = raw_value.strip()

    if len(value) == 10:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
        dt = datetime.combine(parsed_date, time(23, 59, 59) if is_end else time.min)
        return dt.replace(tzinfo=ZoneInfo("America/Chicago"))

    try:
        normalized_value = value.replace("Z", "+00:00")
        parsed_datetime = datetime.fromisoformat(normalized_value)

        if parsed_datetime.tzinfo is not None:
            return parsed_datetime.astimezone(ZoneInfo("America/Chicago"))
        return parsed_datetime.replace(tzinfo=ZoneInfo("America/Chicago"))
    except ValueError as exc:
        raise ValueError(
            "Invalid date/time format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM"
        ) from exc


def _get_uploaded_files():
    """Collect image uploads from the request."""

    files = [
        upload
        for upload in request.files.getlist("images")
        if upload and upload.filename
    ]

    image_file = request.files.get("image_file")
    if image_file and image_file.filename:
        files.append(image_file)

    return files


def _create_pending_submission():
    """Validate and save a public submission; notify Slack."""

    title = (request.form.get("title") or "").strip()
    address = (request.form.get("address") or "").strip()

    if not title or not address:
        return jsonify({"error": "Missing title and address."}), 400

    try:
        event_type = normalize_public_event_category(request.form.get("event_type"))
        start_date = _parse_submission_datetime(request.form.get("start_date"))
        end_date = _parse_submission_datetime(request.form.get("end_date"), is_end=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if start_date and end_date and end_date < start_date:
        return jsonify({"error": "end_date must be after start_date."}), 400

    try:
        image_urls = upload_images_to_gcs(_get_uploaded_files())
        new_event = add_event(
            title=title,
            lat=None,
            long=None,
            url=request.form.get("url"),
            start_date=start_date,
            end_date=end_date,
            images=image_urls,
            address=address,
            event_type=event_type,
            description=request.form.get("description"),
            company_name=request.form.get("company_name"),
            submitter_name=request.form.get("submitter_name"),
            submitter_email=request.form.get("submitter_email"),
            is_accepted=False,
            highlight=False,
        )

        # Jacob review
        channel_id = CU_CALENDAR_ID
        link = "tenplink.com/admin/cu-calendar/dashboard"
        notification_text = (
            f"New event submitted: *{title}*. Click the link to review: {link}"
        )

        dm_channel_by_id(channel_id=channel_id, text=notification_text)

        return (
            jsonify(
                {
                    "message": "Event submitted for IMC approval!",
                    "uid": new_event["uid"],
                }
            ),
            201,
        )
    except Exception:
        logging.exception("Error during CU calendar submission")
        return jsonify({"error": "Failed to process image upload or save event."}), 500


# public routes
@calendar_routes.route("/events", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_public_events():
    """GET future accepted events (legacy JSON)."""

    events = [
        _serialize_legacy_public_event(event) for event in get_future_public_events()
    ]
    return jsonify(events), 200


@calendar_routes.route("/center", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_map_center():
    """
    Return default map center lat/long derived from future events (or campus default).
    """
    center = center_val()
    return jsonify({"lat": center[0], "long": center[1]}), 200


@calendar_routes.route("/submit", methods=["POST"])
@cross_origin()
@csrf.exempt
def submit_calendar_item():
    """POST a pending public event (multipart form)."""

    return _create_pending_submission()


@public_calendar_api_routes.route("", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_public_events_api():
    """GET /api/events — future accepted events."""

    events = [_serialize_public_event(event) for event in get_future_public_events()]
    return jsonify(events), 200


@public_calendar_api_routes.route("/submissions", methods=["POST"])
@cross_origin()
@csrf.exempt
def submit_public_event_api():
    """POST a pending public event (API)."""

    return _create_pending_submission()


@public_calendar_api_routes.route("/categories", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_public_event_categories():
    """GET allowed event categories."""

    return jsonify(get_public_event_categories()), 200


# admin routes
@admin_calendar_routes.route("/pending", methods=["GET"])
@login_required
def list_pending_events():
    """GET pending events (staff)."""

    return jsonify(get_pending_events()), 200


@admin_calendar_routes.route("/source/add", methods=["POST"])
@login_required
def add_and_process_source():
    """Import from a Google Calendar URL and save the source if new."""

    data = request.get_json(silent=True) or request.form or {}
    gcal_url = data.get("gcal_url")
    company = data.get("company_name")

    if not gcal_url:
        return jsonify({"error": "Missing gcal_url"}), 400

    existing_sources = get_all_calendar_sources()
    source_already_exists = any(s.get("gcal_url") == gcal_url for s in existing_sources)
    imported_event_type = DEFAULT_PUBLIC_EVENT_CATEGORY

    parsed_events = gcal_to_events(gcal_url)
    if parsed_events is None:
        return jsonify({"error": "Failed to parse Google Calendar URL."}), 400

    events_added = 0
    for event in parsed_events:
        if event_exists(gcal_url, event.get("title"), event.get("start_date")):
            continue

        coords = geocode_address(event.get("address"))
        if coords:
            lat, lng = coords
            add_event(
                title=event.get("title"),
                lat=lat,
                long=lng,
                url=gcal_url,
                start_date=event.get("start_date"),
                end_date=event.get("end_date"),
                images=[],
                address=event.get("address"),
                event_type=imported_event_type,
                description=event.get("description"),
                company_name=company,
                submitter_name="",
                submitter_email="",
                is_accepted=True,
                highlight=False,
            )
            events_added += 1

    if not source_already_exists:
        add_calendar_source(gcal_url, company or "")
        message = (
            f"Successfully linked new calendar and imported {events_added} events!"
        )
    else:
        message = f"Calendar already linked. Synced {events_added} new events!"

    return jsonify({"success": True, "message": message}), 200


@admin_calendar_routes.route("/<uid>/highlight", methods=["POST"])
@login_required
def highlight_event(uid):
    """POST highlight and accept an event."""

    if not uid:
        return jsonify({"error": "Invalid Event ID format."}), 400

    success = db_highlight_event(uid)

    if not success:
        return jsonify({"error": "Event not found."}), 404

    return jsonify({"message": "Event highlighted successfully!"}), 200


@admin_calendar_routes.route("/<uid>/accept", methods=["POST"])
@login_required
def accept_pending_event(uid):
    """POST geocode and accept a pending event."""

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


@admin_calendar_routes.route("/<uid>/reject", methods=["POST"])
@login_required
def reject_pending_event(uid):
    """POST delete a pending event (and its images)."""

    if not uid:
        return jsonify({"error": "Invalid Event ID format."}), 400

    success = db_remove_event(uid)
    if not success:
        return jsonify({"error": "Event not found."}), 404

    return jsonify({"message": "Event rejected."}), 200


@admin_calendar_routes.route("/dashboard", methods=["GET"])
@login_required
def admin_dashboard():
    """
    Render the CU Calendar admin dashboard.
    Shows: manual add form, add Google Calendar source form, and pending public submissions.
    """
    pending = get_pending_events()
    pending_sorted = sorted(
        pending,
        key=lambda ev: ev.get("start_date") or datetime.min,
        reverse=True,
    )
    today_iso = datetime.now().date().isoformat()

    return render_template(
        "cu_calendar/admin_dashboard.html",
        pending_events=pending_sorted,
        today_iso=today_iso,
        GOOGLE_MAPS_API_KEY=GOOGLE_MAP_API,
        event_categories=get_public_event_categories(),
    )


@admin_calendar_routes.route("/dashboard/add-event", methods=["POST"])
@login_required
def admin_add_event():
    """POST a manually added accepted event from the dashboard."""

    title = (request.form.get("title") or "").strip()
    address = (request.form.get("address") or "").strip()
    if not title or not address:
        return jsonify({"error": "Missing title and address."}), 400

    raw_start = request.form.get("start_date")
    raw_end = request.form.get("end_date")
    if not raw_start or not str(raw_start).strip():
        return jsonify({"error": "Start date and time are required."}), 400
    if not raw_end or not str(raw_end).strip():
        return jsonify({"error": "End date and time are required."}), 400

    try:
        event_type = normalize_public_event_category(request.form.get("event_type"))
        start_date = _parse_submission_datetime(raw_start)
        end_date = _parse_submission_datetime(raw_end, is_end=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if start_date and end_date and end_date < start_date:
        return jsonify({"error": "End must be after start."}), 400

    coords = geocode_address(address)
    if not coords:
        return jsonify({"error": "Failed to geocode address."}), 400
    lat, lng = coords

    try:
        image_urls = upload_images_to_gcs(_get_uploaded_files())
    except Exception:
        logging.exception("CU calendar admin image upload failed")
        return jsonify({"error": "Failed to upload images."}), 500

    highlight = bool(request.form.get("highlight"))

    new_event = add_event(
        title=title,
        lat=lat,
        long=lng,
        url=request.form.get("url"),
        start_date=start_date,
        end_date=end_date,
        images=image_urls,
        address=address,
        event_type=event_type,
        description=(request.form.get("description") or "").strip(),
        company_name=(request.form.get("company_name") or "").strip(),
        submitter_name=(request.form.get("submitter_name") or "").strip(),
        submitter_email=(request.form.get("submitter_email") or "").strip(),
        is_accepted=True,
        highlight=highlight,
    )

    return jsonify({"success": True, "uid": new_event.get("uid")}), 201
