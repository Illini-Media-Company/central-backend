from flask import Blueprint
from flask_login import login_required

from db.user import get_all_users


users_routes = Blueprint('users_routes', __name__, url_prefix='/users')


@users_routes.route('')
@login_required
def list_users():
    return get_all_users()
