from flask import Blueprint, request

from util.copy_editing import notify_current_copy_editor


content_doc_routes = Blueprint(
    "content_doc_routes", __name__, url_prefix="/content-doc"
)


@content_doc_routes.route("/send-to-copy", methods=["POST"])
def send_story_to_copy():
    story_url = request.form["story_url"]
    copy_chief_email = request.form["copy_chief_email"]

    return notify_current_copy_editor(story_url, copy_chief_email)
