from datetime import datetime, timedelta

from flask import Blueprint, current_app, redirect, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from constants import PUBLIC_BASE_URL
from db.user import add_user, get_user_entity, set_user_ask_oauth_tokens
from util.ask_oauth import (
    build_authorization_url,
    exchange_code_for_tokens,
    get_userinfo,
)
from util.slackbots._slackbot import app


ask_oauth_routes = Blueprint("ask_oauth_routes", __name__, url_prefix="/ask/oauth")


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="ask-oauth")


def _redirect_uri():
    base = (
        PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else request.url_root.rstrip("/")
    )
    return base + url_for("ask_oauth_routes.oauth_callback")


@ask_oauth_routes.route("/start", methods=["GET"])
def oauth_start():
    slack_user_id = request.args.get("slack_user_id")
    if not slack_user_id:
        return "Missing slack_user_id.", 400
    state = _serializer().dumps({"slack_user_id": slack_user_id})
    auth_url = build_authorization_url(state=state, redirect_uri=_redirect_uri())
    return redirect(auth_url)


@ask_oauth_routes.route("/callback", methods=["GET"])
def oauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return "Missing OAuth parameters.", 400

    try:
        state_data = _serializer().loads(state, max_age=600)
    except SignatureExpired:
        return "OAuth request expired. Please try again.", 400
    except BadSignature:
        return "Invalid OAuth state.", 400

    slack_user_id = state_data.get("slack_user_id")

    token_response = exchange_code_for_tokens(code=code, redirect_uri=_redirect_uri())
    if "error" in token_response:
        return f"OAuth error: {token_response.get('error')}", 400

    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in")
    if not access_token:
        return "OAuth failed to return an access token.", 400

    userinfo = get_userinfo(access_token)
    if not userinfo.get("email_verified"):
        return "Email not verified for this Google account.", 400

    email = userinfo.get("email")
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    if not email:
        return "OAuth did not return an email address.", 400

    if slack_user_id:
        try:
            slack_info = app.client.users_info(user=slack_user_id)
            slack_email = slack_info["user"]["profile"].get("email")
            if slack_email and slack_email.lower() != email.lower():
                return (
                    "Google account email does not match your Slack email.",
                    400,
                )
        except Exception:
            pass

    user = get_user_entity(email)
    if user is None:
        add_user(
            sub=userinfo.get("sub"), name=name, email=email, picture=picture, groups=[]
        )

    expiry = (
        datetime.utcnow() + timedelta(seconds=int(expires_in))
        if expires_in is not None
        else None
    )

    set_user_ask_oauth_tokens(
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        expiry=expiry,
    )

    return "Google account connected. Return to Slack and try /ask again.", 200
