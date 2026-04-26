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
    
    # In a fully fleshed-out version, you would filter this by current date
    # or relevant active status for the user's view.
    active_stories = get_all_stories()

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
    data = request.get_json()

    title = data.get("title", "")
    description = data.get("description", "")
    writer = data.get("writer", "")
    writer_email = data.get("writer_email", "")
    department = data.get("department", "")

    if not title or not writer or not writer_email or not department:
        return "Missing required story information.", 400

    # Add to DB
    new_story = add_story(
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


    res = send_writer_assignment_notification(writer_email, title)
    if not res.get("ok"):
        return "Story created, but failed to notify writer.", 400

    return "Story successfully created and writer notified.", 200


@story_routes.route("/<uid>/update", methods=["POST"])
@login_required
def update_story_status(uid):
    """
    Updates story details. Automatically pings copy chief when hitting 2nd edited with a snow link.
    """
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
        return "No data provided to update.", 400

    try:
        updated_story = update_story(int(uid), **update_data)
    except ValueError:
        return "Error updating story. Story ID not found.", 400

    # Workflow Check: Notify copy chief if conditions are met
    current_copy_status = updated_story.get("copy_status")
    current_snow_link = updated_story.get("snow_link")

    if current_copy_status == "2nd edited" and current_snow_link:
        res = send_copy_chief_notification(updated_story.get("title"), current_snow_link)
        if not res.get("ok"):
            return "Story updated, but failed to notify copy chief.", 400

    return "Story status updated successfully.", 200