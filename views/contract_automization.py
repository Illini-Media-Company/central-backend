import re

from flask import Blueprint, render_template, request
from flask_login import login_required

from db.social_post import (
    SocialPlatform,
    get_all_posts,
    get_recent_posts,
    delete_all_posts,
)
from util.security import restrict_to
from util.social_posts import (
    send_illinois_app_notification,
    post_to_reddit,
    post_to_twitter,
)
from util.stories import get_title_from_url


onboarding_routes = Blueprint("onboarding", __name__, url_prefix="/onboarding")


@onboarding_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def dashboard():
    return render_template("di_contract_automization_dashboard.html")


@onboarding_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def admin_dashboard():
    return render_template("di_contract_automization_admin.html")
