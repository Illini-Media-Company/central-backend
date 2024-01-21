from functools import wraps

from flask_login import current_user
from google.auth import (
    default,
    iam,
    transport,
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

from constants import ENV


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def get_groups_for_user(user_email):
    if ENV == "dev":
        return []

    creds, _ = default()
    request = transport.requests.Request()
    creds.refresh(request)
    signer = iam.Signer(request, creds, creds.service_account_email)
    creds = service_account.Credentials(
        signer,
        creds.service_account_email,
        TOKEN_URL,
        scopes=SCOPES,
        subject="di_admin@illinimedia.com",
    )

    with build("admin", "directory_v1", credentials=creds) as service:
        response = (
            service.groups()
            .list(domain="illinimedia.com", userKey=user_email)
            .execute()
        )
        groups = response.get("groups", [])
        groups = [group["email"].split("@")[0] for group in groups]

        # Hardcode derived groups
        derived_groups = groups.copy()
        for group in groups:
            if group in ["editor", "di-mer", "di-mev", "di-meo"]:
                derived_groups.extend(["editors", "di-section-editors"])
            if group in ["editor", "di-mer"]:
                derived_groups.extend(
                    ["buzz", "features", "news", "sports", "opinions"]
                )
            if group in ["editor", "di-mev"]:
                derived_groups.extend(["design", "photo", "graphics", "social"])
            if group in ["editor", "di-meo"]:
                derived_groups.extend(["copy", "webdev"])
            if group in [
                "buzz",
                "features",
                "news",
                "sports",
                "opinions",
                "design",
                "photo",
                "graphics",
                "social",
                "copy",
            ]:
                derived_groups.append("di-section-editors")
            if group == "online-team":
                derived_groups.extend(["webdev", "di-section-editors"])
        return derived_groups


def require_internal(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.email.endswith("@illinimedia.com"):
            return func(*args, **kwargs)
        else:
            return "This action is restricted to Illini Media staff."

    return wrapper


def restrict_to(groups):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if set(groups) & set(current_user.groups) or ENV == "dev":
                return func(*args, **kwargs)
            else:
                return "This action is restricted to specific Google groups.", 403

        return wrapper

    return decorator
