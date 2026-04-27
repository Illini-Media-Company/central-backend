from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from db.follow_up import get_all_items, create_item
from db.category import get_all_categories, seed_default_categories
from db import client
from util.security import csrf
from datetime import datetime, timedelta

followup_tracker_routes = Blueprint(
    "followup_tracker_routes", __name__, url_prefix="/followup-tracker"
)


@followup_tracker_routes.route("/", methods=["GET"])
@login_required
def dashboard():
    with client.context():
        categories = get_all_categories()
        if not categories:
            seed_default_categories()
            categories = get_all_categories()
        items = get_all_items()
    for item in items:
        created = item.get("created_at")
        item["date"] = created.strftime("%-m/%d") if created else ""
        item["age_days"] = (datetime.now() - created).days if created else 0
    category_map = {c["name"]: c for c in categories}
    return render_template(
        "followup_tracker.html",
        items=items,
        categories=categories,
        category_map=category_map,
    )


@followup_tracker_routes.route("/create", methods=["POST"])
@csrf.exempt
@login_required
def create():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("followup_tracker_routes.dashboard"))
    with client.context():
        create_item(
            title=title,
            notes=request.form.get("notes", ""),
            status="New",
            priority=request.form.get("priority", "Unassigned"),
            category=request.form.get("category", "General"),
            email_link=request.form.get("email_link", ""),
        )
    return redirect(url_for("followup_tracker_routes.dashboard"))
