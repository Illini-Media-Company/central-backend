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
import requests
import base64

cc_routes = Blueprint("cc_routes", __name__, url_prefix="/constant-contact")
def get_access_token(redirect_uri, client_id, client_secret, auth_code):
    base_url = "https://authz.constantcontact.com/oauth2/default/v1/token"
    to_b64 = client_id + ":" + client_secret
    auth_headers = {
        "Accept": "application/json",
        "Content-type": "application/x-www-form-urlencoded",
        "Authorization": "Basic " + base64.b64encode(bytes(to_b64, 'utf-8')).decode('utf-8'),
        "create_source": "Account"
    }
    params = {
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    request_uri =  base_url + "?" + urllib.parse.urlencode(params)
    print(request_uri)
    a = requests.post(request_uri, headers=auth_headers)
    print(a.json())
    return a.json()["access_token"]


@cc_routes.route("/dashboard")
@login_required
def dashboard():
    code = None if kv_store_get("AUTH_CODE") == None else kv_store_get("AUTH_CODE")
    return render_template("cc.html", code = code)


redirect_uri = "https://localhost:5001/constant-contact/login/callback" 

@cc_routes.route('/login', methods=["GET"])
@login_required
def cc_login():
    authorization_url = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
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
    kv_store_set('AUTH_CODE', auth_code)
    return redirect(url_for('index'))


@cc_routes.route('/subscribe', methods=["GET"])
def cc_create_contact():
    base_url = "https://api.cc.email/v3"
    endpoint = "/contacts/sign_up_form"
    url = base_url + endpoint
    email = request.args.get("email")
    newsletter = request.args.get("newsletter")
    auth_code = kv_store_get('AUTH_CODE')
    access_token = get_access_token(redirect_uri, CC_CLIENT_ID, CC_CLIENT_SECRET, auth_code)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {
        "first_name": "Joe",
        "last_name": "Joe",
        "create_source": "Account",
        "email_address": email,
        "list_memberships": ["c69be490-79c8-11ee-9cf7-fa163e1ce73c"],
        "custom_fields": [{
            "custom_field_id": "57637580-9006-11ee-b3f6-fa163e56233d",
            "value": newsletter
        }]
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201 or response.status_code == 200:
        print("Contact created successfully!")
    else:
        print(f"Failed to create contact. Status code: {response.status_code}")
        print(response.text)

    return redirect(url_for('index'))

    