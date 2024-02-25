import base64

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required
import requests
import urllib

from constants import CC_CLIENT_ID, CC_CLIENT_SECRET
from db.kv_store import kv_store_get, kv_store_set


CC_AUTHORIZATION_URL = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
CC_SUBSCRIBE_URL = "https://api.cc.email/v3/contacts/sign_up_form"


constant_contact_routes = Blueprint(
    "constant_contact_routes", __name__, url_prefix="/constant-contact"
)

from main import csrf  # Must be after blueprint


@constant_contact_routes.route("/dashboard")
@login_required
def dashboard():
    code = "NOT SET" if kv_store_get("CC_REFRESH_TOKEN") == None else "SET"
    return render_template("cc.html", code=code)


@constant_contact_routes.route("/login", methods=["GET"])
@login_required
def cc_login():
    redirect_url = url_for("constant_contact_routes.cc_login_callback")
    params = {
        "client_id": CC_CLIENT_ID,
        "client_secret": CC_CLIENT_SECRET,
        "redirect_uri": redirect_url,
        "scope": "contact_data offline_access",
        "response_type": "code",
        "state": "state",
    }
    authorization_url = CC_AUTHORIZATION_URL + "?" + urllib.parse.urlencode(params)
    return redirect(authorization_url)


@constant_contact_routes.route("/login/callback", methods=["GET"])
@login_required
def cc_login_callback():
    auth_code = request.args.get("code")

    redirect_url = url_for("constant_contact_routes.cc_login_callback")
    print(auth_code)
    ref_token = get_refresh_token(
        redirect_url, CC_CLIENT_ID, CC_CLIENT_SECRET, auth_code
    )["refresh_token"]
    kv_store_set("CC_REFRESH_TOKEN", ref_token)
    return redirect(url_for("index"))


@csrf.exempt
@constant_contact_routes.route("/subscribe", methods=["POST"])
def cc_create_contact():
    email = request.form["email"]
    newsletter = request.form["newsletter"]

    redirect_url = url_for("constant_contact_routes.cc_login_callback")
    ref_token = kv_store_get("CC_REFRESH_TOKEN")
    keys_json = get_access_token(
        redirect_url, CC_CLIENT_ID, CC_CLIENT_SECRET, ref_token
    )
    access_token = keys_json["access_token"]
    new_ref_token = keys_json["refresh_token"]
    kv_store_set("CC_REFRESH_TOKEN", new_ref_token)

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
        "custom_fields": [
            {
                "custom_field_id": "57637580-9006-11ee-b3f6-fa163e56233d",
                "value": newsletter,
            }
        ],
    }

    response = requests.post(CC_SUBSCRIBE_URL, headers=headers, json=data)
    if response.status_code == 201 or response.status_code == 200:
        print("Contact created successfully!")
    else:
        print(f"Failed to create contact. Status code: {response.status_code}")
        print(response.text)

    return redirect(url_for("index"))


def get_refresh_token(redirect_uri, client_id, client_secret, auth_code):
    base_url = "https://authz.constantcontact.com/oauth2/default/v1/token"
    to_b64 = client_id + ":" + client_secret
    auth_headers = {
        "Accept": "application/json",
        "Content-type": "application/x-www-form-urlencoded",
        "Authorization": "Basic "
        + base64.b64encode(bytes(to_b64, "utf-8")).decode("utf-8"),
        "create_source": "Account",
    }
    params = {
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    request_url = base_url + "?" + urllib.parse.urlencode(params)
    print(request_url)
    a = requests.post(request_url, headers=auth_headers)
    return a.json()


def get_access_token(redirect_uri, client_id, client_secret, ref_token):
    base_url = "https://authz.constantcontact.com/oauth2/default/v1/token"
    to_b64 = client_id + ":" + client_secret
    auth_headers = {
        "Accept": "application/json",
        "Content-type": "application/x-www-form-urlencoded",
        "Authorization": "Basic "
        + base64.b64encode(bytes(to_b64, "utf-8")).decode("utf-8"),
        "create_source": "Account",
    }
    params = {
        "refresh_token": ref_token,
        "redirect_uri": redirect_uri,
        "grant_type": "refresh_token",
    }
    request_url = base_url + "?" + urllib.parse.urlencode(params)
    print(request_url)
    a = requests.post(request_url, headers=auth_headers)
    print(a.json())
    return a.json()
