from functools import wraps
from threading import Thread

from flask_login import current_user
from flask_seasurf import SeaSurf
from google.auth import (
    default,
    iam,
    impersonated_credentials,
    transport,
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
import networkx as nx
import requests

from constants import ENV, GOOGLE_POJECT_ID
from db.group import add_group, get_extended_groups


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]


csrf = SeaSurf()


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def get_creds(scopes):
    creds, _ = default()
    if ENV == "dev":
        creds = impersonated_credentials.Credentials(
            source_credentials=creds,
            target_principal=f"{GOOGLE_POJECT_ID}@appspot.gserviceaccount.com",
            delegates=[],
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            lifetime=300,
        )

    request = transport.requests.Request()
    creds.refresh(request)
    signer = iam.Signer(request, creds, creds.service_account_email)
    creds = service_account.Credentials(
        signer,
        creds.service_account_email,
        TOKEN_URL,
        scopes=scopes,
        subject="di_admin@illinimedia.com",
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

    with build("admin", "directory_v1", credentials=get_creds(SCOPES)) as service:
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
    with build("admin", "directory_v1", credentials=get_creds(SCOPES)) as service:
        response = (
            service.groups()
            .list(domain="illinimedia.com", userKey=user_email)
            .execute()
        )
        groups = response.get("groups", [])
        groups = [group["email"].split("@")[0] for group in groups]
        thread = Thread(target=update_groups, args=[groups])
        thread.run()
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
            return "This action is restricted to Illini Media staff."

    return wrapper


def restrict_to(groups):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if is_user_in_group(current_user, groups) or ENV == "dev":
                return func(*args, **kwargs)
            else:
                return "This action is restricted to specific Google Groups.", 403

        return wrapper

    return decorator
