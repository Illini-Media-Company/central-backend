from datetime import datetime, timedelta
from typing import Optional
import urllib.parse

import requests

from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PUBLIC_BASE_URL
from util.security import get_google_provider_cfg
from db.user import get_user_entity, set_user_ask_oauth_tokens


ASK_OAUTH_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/cloud-platform",
]


def build_oauth_start_link(slack_user_id: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/ask/oauth/start?slack_user_id={urllib.parse.quote(slack_user_id)}"


def build_authorization_url(state: str, redirect_uri: str) -> str:
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID is not set.")
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": " ".join(ASK_OAUTH_SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    return authorization_endpoint + "?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET is not set.")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(token_endpoint, data=data, timeout=15)
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET is not set.")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = requests.post(token_endpoint, data=data, timeout=15)
    return resp.json()


def get_userinfo(access_token: str) -> dict:
    google_provider_cfg = get_google_provider_cfg()
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    resp = requests.get(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    return resp.json()


def _is_expired(expiry: Optional[datetime], skew_seconds: int = 60) -> bool:
    if expiry is None:
        return True
    now = datetime.utcnow()
    return expiry <= now + timedelta(seconds=skew_seconds)


def get_valid_access_token(email: str) -> Optional[str]:
    user = get_user_entity(email)
    if user is None:
        return None

    if user.ask_oauth_access_token and not _is_expired(user.ask_oauth_expiry):
        return user.ask_oauth_access_token

    if not user.ask_oauth_refresh_token:
        return None

    token_response = refresh_access_token(user.ask_oauth_refresh_token)
    access_token = token_response.get("access_token")
    if not access_token:
        return None

    expires_in = token_response.get("expires_in")
    expiry = (
        datetime.utcnow() + timedelta(seconds=int(expires_in))
        if expires_in is not None
        else None
    )
    refresh_token = token_response.get("refresh_token")

    set_user_ask_oauth_tokens(
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        expiry=expiry,
    )
    return access_token
