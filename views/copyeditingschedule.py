from flask import Blueprint, send_from_directory
from flask_login import login_required
from util.security import restrict_to
from db import client
import os

copyeditingroutes = Blueprint(
    "newSchedule", __name__, url_prefix="/copy-editing-schedule"
)


@copyeditingroutes.route("/admin", methods=["GET"])
@login_required
@restrict_to(["food-truck-admin", "imc-staff-webdev"])
def admin():
    with client.context():
        print("Loading admin page...")
    print("Done.")
    return send_from_directory(
        os.path.join("static", "copy-editing-frontend"), "index.html"
    )
