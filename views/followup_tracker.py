from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required
from db.follow_up import (
    get_all_items,
    create_item,
    get_all_active_items,
    get_item_by_id,
    update_item,
    resolve_item,
    get_resolved_items,
    delete_item,
)
from db.category import get_all_categories, seed_default_categories
from db import client
from util.security import csrf
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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


# ── API routes ────────────────────────────────────────────────────────────────


@followup_tracker_routes.route("/api/", methods=["POST"])
@login_required
def api_create():
    title = request.form.get("title")
    notes = request.form.get("notes")
    status = request.form.get("status", "New")
    priority = request.form.get("priority", "Normal")
    category = request.form.get("category", "General")
    owner = request.form.get("owner", "Unassigned")
    email_link = request.form.get("email_link")

    if not title or not notes:
        return "Title and notes are required.", 400

    with client.context():
        item = create_item(
            title=title,
            notes=notes,
            status=status,
            priority=priority,
            category=category,
            owner=owner,
            email_link=email_link,
        )
    return jsonify(item), 201


@followup_tracker_routes.route("/api/", methods=["GET"])
@login_required
def api_list_active():
    with client.context():
        items = get_all_active_items()
    return jsonify(items), 200


@followup_tracker_routes.route("/api/<int:uid>", methods=["GET"])
@login_required
def api_get_item(uid):
    with client.context():
        item = get_item_by_id(uid)
    if item is None:
        return "Item not found.", 404
    return jsonify(item), 200


@followup_tracker_routes.route("/api/<int:uid>", methods=["POST"])
@csrf.exempt
@login_required
def api_update(uid):
    fields = {
        key: request.form[key]
        for key in [
            "title",
            "notes",
            "status",
            "priority",
            "category",
            "owner",
            "email_link",
        ]
        if key in request.form
    }
    if not fields:
        return "No fields provided.", 400
    with client.context():
        item = update_item(uid, **fields)
    if item is None:
        return "Item not found.", 404
    return jsonify(item), 200


@followup_tracker_routes.route("/api/<int:uid>/resolve", methods=["POST"])
@login_required
def api_resolve(uid):
    with client.context():
        item = resolve_item(uid)
    if item is None:
        return "Item not found.", 404
    return jsonify(item), 200


@followup_tracker_routes.route("/api/<int:uid>/delete", methods=["POST"])
@csrf.exempt
@login_required
def api_delete(uid):
    with client.context():
        delete_item(uid)
    return "", 204


@followup_tracker_routes.route("/api/resolved", methods=["GET"])
@login_required
def api_list_resolved():
    with client.context():
        items = get_resolved_items()
    return jsonify(items), 200
