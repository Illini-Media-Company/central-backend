# This file defines the API endpoints for adding, modifying and removing tools that
# appear on the homepage of the Illini Media Console. Also contains routes that add
# and remove favorite tools for a user.
#
# Created by Jacob Slabosz on Oct. 1, 2025
# Last modified Oct. 5, 2025

from flask import Blueprint, render_template, request
from flask_login import login_required
from flask_cors import cross_origin
from db.all_tools import (
    create_tool,
    modify_tool,
    remove_tool,
    remove_category,
    get_categories,
    get_all_tools,
    get_tool_by_uid,
)
from db.user import (
    add_user_favorite_tool,
    remove_user_favorite_tool,
)
from util.security import restrict_to, csrf
from constants import TOOLS_ADMIN_ACCESS_GROUPS
from db import client

tools_routes = Blueprint("tools_routes", __name__, url_prefix="/tools")


@tools_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def admin():
    with client.context():
        tools = get_all_tools()
        categories = get_categories()

    return render_template("all_tools.html", tools=tools, categories=categories)


@tools_routes.route("/add", methods=["POST"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def add_tool():
    with client.context():
        name = request.form["name"]
        description = request.form["description"]
        icon = request.form["icon"]
        url = request.form["url"]
        category = request.form["category"]
        # This part properly formats the restricted_to groups for storage in the database
        restricted_to_raw = request.form["restricted_to"].strip()
        if restricted_to_raw:
            restricted_to = [
                item.strip() for item in restricted_to_raw.split(",") if item.strip()
            ]
        else:
            restricted_to = []

        create_tool(
            name=name,
            description=description,
            icon=icon,
            url=url,
            category=category,
            restricted_to=restricted_to,
        )

    return "Tool created.", 200


@tools_routes.route("/<uid>/modify", methods=["POST"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def change_tool(uid):
    with client.context():
        uid = int(uid)

        name = request.form["name"]
        description = request.form["description"]
        icon = request.form["icon"]
        url = request.form["url"]
        category = request.form["category"]
        # This part properly formats the restricted_to groups for storage in the database
        restricted_to_raw = request.form["restricted_to"].strip()
        if restricted_to_raw:
            restricted_to = [
                item.strip() for item in restricted_to_raw.split(",") if item.strip()
            ]
        else:
            restricted_to = []

        status = modify_tool(
            uid=uid,
            name=name,
            description=description,
            icon=icon,
            url=url,
            category=category,
            restricted_to=restricted_to,
        )

        if not status:
            return "Tool not found.", 400

    return "Tool modified.", 200


@tools_routes.route("/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def delete_tool(uid):
    with client.context():
        if uid.isdigit() and remove_tool(int(uid)):
            return "Tool removed.", 200
        else:
            return "Tool not found.", 400


@tools_routes.route("/<uid>/get", methods=["GET"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def get_tool(uid):
    with client.context():
        if uid.isdigit():
            result = get_tool_by_uid(int(uid))
            if result is not False:
                return result, 200

        return "Invalid UID.", 400


@tools_routes.route("/category/delete", methods=["POST"])
@login_required
@restrict_to(TOOLS_ADMIN_ACCESS_GROUPS)
def delete_category():
    with client.context():
        category = request.form["category"]

        res = remove_category(category)

        if res == True:
            return "Category removed.", 200
        elif res == "NOTEMPTY":
            return "Category not empty.", 403
        else:
            return "Category not found.", 400


@tools_routes.route("/favorites/add", methods=["POST"])
@login_required
def add_favorite():
    email = request.form["email"]
    tool_uid = request.form["tool_uid"]

    if add_user_favorite_tool(email=email, tool_uid=tool_uid):
        return "Favorite added.", 200
    else:
        return "Failed to add favorite.", 400


@tools_routes.route("/favorites/remove", methods=["POST"])
@login_required
def remove_favorite():
    email = request.form["email"]
    tool_uid = request.form["tool_uid"]

    if remove_user_favorite_tool(email=email, tool_uid=tool_uid):
        return "Favorite removed.", 200
    else:
        return "Failed to remove favorite.", 400
