from flask import (
    Blueprint,
    request
)
from flask_login import login_required

from db.user import get_all_users, add_user


users_routes = Blueprint('users_routes', __name__, url_prefix='/users')


@users_routes.route('', methods=['GET'])
@login_required
def list_users():
    return get_all_users()

@users_routes.route('', methods=['POST'])
@login_required
def create_user():
    name = request.form['name']
    email = request.form['email']
    add_user(sub=None, name=name, email=email)
    return 'User created.', 200
