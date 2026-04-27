from flask import Blueprint, request, jsonify
from flask_login import login_required
from db.category import get_all_categories, create_category, delete_category
from db import client
from util.security import csrf

category_routes = Blueprint("category_routes", __name__, url_prefix="/categories")


@category_routes.route("/", methods=["GET"])
@login_required
def list_categories():
    with client.context():
        cats = get_all_categories()
    return jsonify(cats), 200


@category_routes.route("/", methods=["POST"])
@csrf.exempt
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not name:
        return "Name required.", 400
    with client.context():
        cat = create_category(name)
    return jsonify(cat), 201


@category_routes.route("/<int:uid>/delete", methods=["POST"])
@csrf.exempt
@login_required
def delete(uid):
    with client.context():
        delete_category(uid)
    return "", 204
