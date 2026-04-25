from flask import Blueprint, request, jsonify
from flask_login import login_required
from db.follow_up import (
    create_item,
    get_all_active_items,
    get_item_by_id,
    update_item,
    resolve_item,
    get_resolved_items,
)
from util.security import restrict_to, csrf
from db import client
import logging

logger = logging.getLogger(__name__)

follow_up_routes = Blueprint("follow_up_routes", __name__, url_prefix="/follow-up")


@follow_up_routes.route("/", methods=["POST"])
@login_required
def create():
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


@follow_up_routes.route("/", methods=["GET"])
@login_required
def list_active():
    with client.context():
        items = get_all_active_items()
    return jsonify(items), 200


@follow_up_routes.route("/<uid>", methods=["GET"])
@login_required
def get_item(uid):
    pass


@follow_up_routes.route("/<uid>", methods=["POST"])
@login_required
def update(uid):
    pass


@follow_up_routes.route("/<uid>/resolve", methods=["POST"])
@login_required
def resolve(uid):
    pass


@follow_up_routes.route("/resolved", methods=["GET"])
@login_required
def list_resolved():
    pass
