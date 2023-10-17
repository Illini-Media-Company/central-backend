from functools import wraps

from flask_login import current_user
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

from constants import ENV


GOOGLE_DISCOVERY_URL = (
    'https://accounts.google.com/.well-known/openid-configuration'
)
SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.group.readonly'
]


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def get_groups_for_user(user_email):
    creds = google.auth.default(scopes=SCOPES)
    if isinstance(creds, service_account.Credentials):
        creds = creds.with_subject('di_admin@illinimedia.com')
    else:
        return []

    with build('admin', 'directory_v1', credentials=creds) as service:
        response = service.groups().list(domain='illinimedia.com', userKey=user_email).execute()
        groups = response.get('groups', [])
        groups = [ group['email'].split('@')[0] for group in groups ]

        # Hardcode derived groups
        derived_groups = groups.copy()
        for group in groups:
            if group in ['editor', 'di-mer', 'di-mev', 'di-meo']:
                derived_groups.extend(['editors', 'di-section-editors'])
            if group in ['editor', 'di-mer']:
                derived_groups.extend(['buzz', 'features', 'news', 'sports', 'opinions'])
            if group in ['editor', 'di-mev']:
                derived_groups.extend(['design', 'photo', 'graphics', 'social'])
            if group in ['editor', 'di-meo']:
                derived_groups.extend(['copy', 'webdev'])
            if group in ['buzz', 'features', 'news', 'sports', 'opinions', 
                         'design', 'photo', 'graphics', 'social', 'copy']:
                derived_groups.append('di-section-editors')
            if group == 'online-team':
                derived_groups.extend(['webdev', 'di-section-editors'])
        return derived_groups


def restrict_to(groups):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if set(groups) & set(current_user.groups) or ENV == 'dev':
                return func(*args, **kwargs)
            else:
                return 'Access denied.', 403
        return wrapper
    return decorator
