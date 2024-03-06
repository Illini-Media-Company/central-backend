import requests

from constants import RETOOL_API_KEY


def fetch_retool_embed_url(landing_page_uuid):
    headers = {
        "Authorization": f"Bearer {RETOOL_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "landingPageUuid": landing_page_uuid,
        "groupIds": [2681115],
        "externalIdentifier": "central-backend",
    }

    response = requests.post(
        "https://retool.illinimedia.com/api/embed-url/external-user",
        headers=headers,
        json=body,
    )

    if response.ok:
        return response.json()["embedUrl"]
    else:
        print(response)
        raise Exception("Failed to fetch Retool embed URL")
