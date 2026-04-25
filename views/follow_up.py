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
    pass


@follow_up_routes.route("/", methods=["GET"])
@login_required
def list_active():
    pass


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
