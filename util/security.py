from functools import wraps

from flask import request
from flask_login import current_user
from flask_seasurf import SeaSurf
from google.auth import (
    default,
    iam,
    impersonated_credentials,
    transport,
)
from google.oauth2 import id_token, service_account
from googleapiclient.discovery import build
import networkx as nx
import requests

from constants import ENV, ADMIN_EMAIL, GOOGLE_PROJECT_ID, RECAPTCHA_SECRET_KEY
from db.group import add_group
from db.user import update_user_groups


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


csrf = SeaSurf()
default_creds, _ = default()
http_request = transport.requests.Request()


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def get_creds(scopes):
    if ENV == "dev":
        creds = impersonated_credentials.Credentials(
            source_credentials=default_creds,
            target_principal=f"{GOOGLE_PROJECT_ID}@appspot.gserviceaccount.com",
            delegates=[],
            target_scopes=scopes,
            lifetime=300,
        )
    else:
        creds = default_creds.with_scopes(scopes)

    creds.refresh(http_request)
    return creds


def get_admin_creds(scopes):
    creds = get_creds(["https://www.googleapis.com/auth/cloud-platform"])
    signer = iam.Signer(http_request, creds, creds.service_account_email)
    creds = service_account.Credentials(
        signer,
        creds.service_account_email,
        TOKEN_URL,
        scopes=scopes,
        subject=ADMIN_EMAIL,
    )
    return creds


def update_groups(user_email):
    graph = nx.DiGraph()
    queue = set([user_email])

    def update_graph(request_id, response, exception):
        parent_groups = response.get("groups", [])
        parent_emails = [group["email"] for group in parent_groups]
        for email in parent_emails:
            graph.add_edge(email, request_id)
            queue.add(email)

    with build("admin", "directory_v1", credentials=get_admin_creds(SCOPES)) as service:
        while len(queue) > 0:
            batch = service.new_batch_http_request()
            for email in queue:
                batch.add(
                    service.groups().list(
                        domain="illinimedia.com",
                        query=(f"memberKey={email}"),
                    ),
                    callback=update_graph,
                    request_id=email,
                )
            queue = set()
            batch.execute()

    for email in graph:
        ancestors = [ancestor.split("@")[0] for ancestor in nx.ancestors(graph, email)]
        if email == user_email:
            update_user_groups(email=email, groups=ancestors)
        else:
            add_group(name=email.split("@")[0], ancestors=ancestors)


def is_user_in_group(user, groups):
    return len(set(user.groups) & set(groups)) > 0


def require_internal(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.email.endswith("@illinimedia.com"):
            return func(*args, **kwargs)
        else:
            return "This action is restricted to specific users or groups.", 403

    return wrapper


# Restrict an endpoint to specific user email addresses or Google Groups.
# Optionally allow Google OIDC ID tokens from an external source.
# If using ID tokens, user email(s) must be explicitly included in users_or_groups.
def restrict_to(users_or_groups, google_id_token_aud=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated:
                if current_user.email in users_or_groups or is_user_in_group(
                    current_user, users_or_groups
                ):
                    return func(*args, **kwargs)
                else:
                    return "This action is restricted to specific users or groups.", 403
            elif google_id_token_aud and "X-ID-Token" in request.headers:
                token = request.headers["X-ID-Token"]
                try:
                    claims = id_token.verify_oauth2_token(token, http_request)
                except:
                    return "Invalid ID token.", 401

                if claims["aud"] != google_id_token_aud:
                    return "The provided ID token audience is not allowed.", 403
                elif claims["email"] not in users_or_groups:
                    return "This action is restricted to specific users or groups.", 403
                else:
                    return func(*args, **kwargs)
            else:
                return "You must be logged in to perform this action.", 401

        return wrapper

    return decorator


def verify_recaptcha(token):
    data = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": token,
    }

    response = requests.post(RECAPTCHA_VERIFY_URL, data=data).json()
    if response["success"]:
        return response["score"]
    else:
        return -1
