from flask import Blueprint
from flask_login import login_required

from db.group import get_all_groups


groups_routes = Blueprint("groups_routes", __name__, url_prefix="/groups")


@groups_routes.route("", methods=["GET"])
@login_required
def list_groups():
    return get_all_groups()
