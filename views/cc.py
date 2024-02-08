import re

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
import urllib
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for,
)
from db.kv_store import (
    kv_store_get,
    kv_store_set
)

cc_routes = Blueprint("cc_routes", __name__, url_prefix="/constant-contact")


@cc_routes.route("/dashboard")
@login_required
def dashboard():
    return render_template("cc.html")


client_id = "d0d8d364-b7b6-497a-a8e7-6e89ac0c754d"
client_secret = "A5sErJbUHdPu6pAHxo7x0w"
redirect_uri = "https://cavemanfury.github.io/"

@cc_routes.route('/constant-contact/login', methods=["GET"])
@login_required
def cc_login():
    authorization_url = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
    redirect_uri = "https://cavemanfury.github.io/" 
    state = "state"  

    # Params for authorization url
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "scope": "contact-data",
        "response_type": "code",
        "state": state
    }
    authorization_url += "?" + urllib.urlencode(params)
    return redirect(authorization_url)

@cc_routes.route('/constant-contact/login/callback', methods=["GET"])
@login_required
def cc_callback():
    auth_code = request.args.get("code")
    kv_store_set(auth_code)
    redirect(url_for('index'))