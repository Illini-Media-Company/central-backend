import base64

from flask import Blueprint, redirect, request, url_for
from flask_login import login_required
import requests
import urllib

from constants import CC_CLIENT_ID, CC_CLIENT_SECRET, CC_LIST_MAPPING
from db.kv_store import kv_store_get, kv_store_set
from util.security import csrf


CC_AUTHORIZATION_URL = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
CC_SUBSCRIBE_URL = "https://api.cc.email/v3/contacts/sign_up_form"


constant_contact_routes = Blueprint(
    "constant_contact_routes", __name__, url_prefix="/constant-contact"
)


@constant_contact_routes.route("/login", methods=["GET"])
@login_required
def cc_login():
    redirect_url = request.url_root[:-1] + url_for(
        "constant_contact_routes.cc_login_callback"
    )
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

    redirect_url = request.url_root[:-1] + url_for(
        "constant_contact_routes.cc_login_callback"
    )
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

    if newsletter in CC_LIST_MAPPING:
        newsletter_id = CC_LIST_MAPPING[newsletter]
    else:
        return "Invalid newsletter.", 400

    redirect_url = request.url_root[:-1] + url_for(
        "constant_contact_routes.cc_login_callback"
    )
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
        "create_source": "Account",
        "email_address": email,
        "list_memberships": [newsletter_id],
    }

    response = requests.post(CC_SUBSCRIBE_URL, headers=headers, json=data)
    if response.status_code == 201 or response.status_code == 200:
        return "Contact created successfully!", 200
    else:
        return "Failed to create contact.", response.status_code


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
    a = requests.post(request_url, headers=auth_headers)
    return a.json()
