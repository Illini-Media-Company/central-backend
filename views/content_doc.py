from flask import Blueprint, request
from flask_cors import cross_origin
from flask_login import login_required

from constants import APPS_SCRIPT_RUNNER_EMAIL, CONTEND_DOC_AUD
from util.slackbots.copy_editing import (
    notify_copy_editor,
    get_copy_editor,
    test,
    scheduler,
)
from util.security import csrf, restrict_to
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


content_doc_routes = Blueprint(
    "content_doc_routes", __name__, url_prefix="/content-doc"
)


@content_doc_routes.route("/send-to-copy", methods=["POST"])
@csrf.exempt
@cross_origin()
@restrict_to(
    [APPS_SCRIPT_RUNNER_EMAIL, "editors", "webdev"], google_id_token_aud=CONTEND_DOC_AUD
)
def send_story_to_copy():
    story_url = request.form["story_url"]
    copy_chief_email = request.form["copy_chief_email"]

    notify_copy_editor(story_url, False, copy_chief_email)
    return "slack message sent", 200


@content_doc_routes.route("/test", methods=["POST"])
@csrf.exempt
@cross_origin()
def test_message():
    test()
    present = datetime.now(tz=ZoneInfo("America/Chicago"))
    post_time = present + timedelta(minutes=2)
    return f"This process was accessed {present} and will execute {post_time}"


@content_doc_routes.route("/clear-scheduler", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def clear():
    scheduler.remove_all_jobs()
    return "cleared COPY_JOBS scheduler", 200
