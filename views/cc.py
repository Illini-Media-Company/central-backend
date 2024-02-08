import re

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from constants import (
    CC_CLIENT_ID,
    CC_CLIENT_SECRET
)
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
    code = None if kv_store_get("AUTH_CODE") == None else kv_store_get("AUTH_CODE").value
    return render_template("cc.html", code = code)


redirect_uri = "https://cavemanfury.github.io/"

@cc_routes.route('/login', methods=["GET"])
@login_required
def cc_login():
    authorization_url = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
    redirect_uri = "https://localhost:5001/constant-contact/login/callback" 
    state = "state"  

    # Params for authorization url
    params = {
        "client_id": CC_CLIENT_ID,
        "client_secret": CC_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "scope": "contact_data",
        "response_type": "code",
        "state": state
    }
    authorization_url += "?" + urllib.parse.urlencode(params)
    return redirect(authorization_url)

@cc_routes.route('/login/callback', methods=["GET"])
@login_required
def cc_callback():
    auth_code = request.args.get("code")
    kv_store_set("AUTH_CODE", auth_code)
    return redirect(url_for('index'))