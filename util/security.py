from functools import wraps
from threading import Thread

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

from constants import ENV, ADMIN_EMAIL, GOOGLE_POJECT_ID
from db.group import add_group, get_extended_groups


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]


csrf = SeaSurf()
default_creds, _ = default()
http_request = transport.requests.Request()


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def get_creds(scopes):
    if ENV == "dev":
        creds = impersonated_credentials.Credentials(
            source_credentials=default_creds,
            target_principal=f"{GOOGLE_POJECT_ID}@appspot.gserviceaccount.com",
            delegates=[],
            target_scopes=scopes,
            lifetime=300,
        )
        creds.refresh(http_request)
        return creds
    else:
        default_creds.refresh(http_request)
        return default_creds


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


def update_groups(groups):
    graph = nx.DiGraph()
    queue = set(groups.copy())

    def update_graph(request_id, response, exception):
        parent_groups = response.get("groups", [])
        parent_groups = [group["email"].split("@")[0] for group in parent_groups]
        for group in parent_groups:
            graph.add_edge(group, request_id)
            queue.add(group)

    with build("admin", "directory_v1", credentials=get_admin_creds(SCOPES)) as service:
        while len(queue) > 0:
            batch = service.new_batch_http_request()
            for group in queue:
                batch.add(
                    service.groups().list(
                        domain="illinimedia.com",
                        query=(f"memberKey={group}@illinimedia.com"),
                    ),
                    callback=update_graph,
                    request_id=group,
                )
            queue = set()
            batch.execute()

    for group in graph:
        ancestors = list(nx.ancestors(graph, group))
        add_group(name=group, ancestors=ancestors)


def get_immediate_groups_for_user(user_email):
    with build("admin", "directory_v1", credentials=get_admin_creds(SCOPES)) as service:
        response = (
            service.groups()
            .list(domain="illinimedia.com", userKey=user_email)
            .execute()
        )
        groups = response.get("groups", [])
        groups = [group["email"].split("@")[0] for group in groups]
        thread = Thread(target=update_groups, args=[groups])
        thread.start()
        return groups


def is_user_in_group(user, groups):
    user_groups = get_extended_groups(user.groups)
    return len(set(user_groups) & set(groups)) > 0


def require_internal(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.email.endswith("@illinimedia.com"):
            return func(*args, **kwargs)
        else:
            return "This action is restricted to specific users or groups.", 403

    return wrapper


# Restrict an endpoint to specifc user email addresses or Google Groups.
# Optionally allow OIDC ID tokens from an external source.
# ID token email must be included in users_or_groups.
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
