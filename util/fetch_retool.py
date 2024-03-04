import requests

def fetch_retool_embed_url(retool_token):
    headers = {
        'Authorization': f'Bearer {retool_token}',
        'Content-Type': 'application/json',
    }
    body = {
        'landingPageUuid': '0afdf92e-b0d4-11ee-ab5f-83b642f596fa',
        'groupIds': [2681115],
        'externalIdentifier': 'central-backend',
    }

    response = requests.post("https://retool.illinimedia.com/api/embed-url/external-user", headers=headers, json=body)

    if response.ok:
        return response.json()['embedUrl']
    else:
        raise Exception("Failed to fetch Retool embed URL")
