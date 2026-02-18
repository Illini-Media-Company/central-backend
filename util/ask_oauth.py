"""

Created on Jan. 26 by Jon Hogg
Last modified Feb. 18, 2026
"""

from datetime import datetime, timedelta
from typing import Optional

import requests

from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from util.security import get_google_provider_cfg
from db.user import get_user_entity, set_user_ask_oauth_tokens


def refresh_access_token(refresh_token: str) -> dict:
    """
    Exchange a Google refresh token for a new access token.
    Uses the configured OAuth client credentials.
    """
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


def _is_expired(expiry: Optional[datetime], skew_seconds: int = 60) -> bool:
    """
    Check whether a token expiry is missing or effectively expired.
    Applies a small skew buffer before actual expiration.
    """
    if expiry is None:
        return True
    now = datetime.utcnow()
    return expiry <= now + timedelta(seconds=skew_seconds)


def get_valid_access_token(email: str) -> Optional[str]:
    """
    Get a usable access token for a user email.
    Returns cached token when valid, otherwise refreshes and saves one.
    """
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
