import requests


GOOGLE_DISCOVERY_URL = (
    'https://accounts.google.com/.well-known/openid-configuration'
)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()
