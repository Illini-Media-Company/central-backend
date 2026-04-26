import logging
from flask import Blueprint, request, render_template
from util.security import restrict_to
from flask_login import current_user, login_required

from util.slackbots.content_doc import (
    send_writer_assignment_notification,
    send_copy_chief_notification,
    send_visual_reminder_notification
)
from db.content_doc import (
    add_story,
    get_all_stories,
    get_story_by_id,
    update_story
)

# Initialize logger for this module
logger = logging.getLogger(__name__)

story_routes = Blueprint(
    "content-doc", __name__, url_prefix="/content-doc"
)


@story_routes.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """
    Main page where the current stories that need to be edited lie.
    """
    user_name = current_user.name
    logger.info("[Dashboard] User %s accessed the story dashboard.", current_user.email)
    
    logger.debug("[Dashboard] Fetching all active stories from the database.")
    active_stories = get_all_stories()
    logger.debug("[Dashboard] Successfully fetched %s stories.", len(active_stories))

    return render_template(
        "content_doc.html",
        currentUserName=user_name,
        stories=active_stories
    )


@story_routes.route("/submit", methods=["POST"])
@login_required
def submit_story():
    """
    Creates a new story event and notifies the assigned writer via Slack.
    """
    logger.info("[Submit Story] User %s is attempting to create a new story.", current_user.email)
    data = request.get_json()

    title = data.get("title", "")
    description = data.get("description", "")
    writer = data.get("writer", "")
    writer_email = data.get("writer_email", "")
    department = data.get("department", "")

    if not title or not writer or not writer_email or not department:
        logger.warning("[Submit Story] Failed validation: Missing required fields. Data received: %s", data)
        return "Missing required story information.", 400

    logger.debug("[Submit Story] Validation passed. Adding story '%s' to database.", title)
    
    # Add to DB
    add_story(
        title=title,
        description=description,
        writer=writer,
        writer_email=writer_email,
        department=department,
        google_doc_link=data.get("google_doc_link", ""),
        snow_link=data.get("snow_link", ""),
        writer_status="pitch", 
        copy_status="",
        publish_time=None,
        notes=data.get("notes", ""),
        editors=[current_user.email], # Logs the editor who created it
        copy_editors="",
        visuals=data.get("visuals", ""),
        graphics=data.get("graphics", "")
    )
    
    logger.info("[Submit Story] Story '%s' successfully added to database.", title)
    logger.debug("[Submit Story] Attempting to send Slack assignment notification to %s.", writer_email)

    res = send_writer_assignment_notification(writer_email, title)
    if not res.get("ok"):
        logger.error("[Submit Story] Story created, but failed to notify writer %s via Slack.", writer_email)
        return "Story created, but failed to notify writer.", 400

    logger.info("[Submit Story] Successfully created story and notified writer %s.", writer_email)
    return "Story successfully created and writer notified.", 200


@story_routes.route("/<uid>/update", methods=["POST"])
@login_required
def update_story_status(uid):
    """
    Updates story details. Automatically pings copy chief when hitting 2nd edited with a snow link.
    """
    logger.info("[Update Story] User %s is attempting to update story ID: %s.", current_user.email, uid)
    data = request.get_json()

    # Extract updateable fields
    writer_status = data.get("writer_status")
    copy_status = data.get("copy_status")
    google_doc_link = data.get("google_doc_link")
    snow_link = data.get("snow_link")
    
    update_data = {}
    if writer_status is not None: update_data["writer_status"] = writer_status
    if copy_status is not None: update_data["copy_status"] = copy_status
    if google_doc_link is not None: update_data["google_doc_link"] = google_doc_link
    if snow_link is not None: update_data["snow_link"] = snow_link

    if not update_data:
        logger.warning("[Update Story] Failed validation for story %s: No valid data provided to update.", uid)
        return "No data provided to update.", 400

    logger.debug("[Update Story] Attempting database update for story %s with data: %s", uid, update_data)

    try:
        updated_story = update_story(int(uid), **update_data)
        logger.info("[Update Story] Successfully updated story %s in the database.", uid)
    except ValueError as e:
        logger.error("[Update Story] Database error updating story %s: %s", uid, str(e))
        return "Error updating story. Story ID not found.", 400

    # Workflow Check: Notify copy chief if conditions are met
    current_copy_status = updated_story.get("copy_status")
    current_snow_link = updated_story.get("snow_link")

    if current_copy_status == "2nd edited" and current_snow_link:
        logger.info("[Update Story] Workflow condition met: Story %s is '2nd edited' with a snow link. Notifying copy chief.", uid)
        
        res = send_copy_chief_notification(updated_story.get("title"), current_snow_link)
        if not res.get("ok"):
            logger.error("[Update Story] Story %s updated, but failed to notify copy chief via Slack.", uid)
            return "Story updated, but failed to notify copy chief.", 400
        logger.debug("[Update Story] Successfully notified copy chief for story %s.", uid)

    return "Story status updated successfully.", 200