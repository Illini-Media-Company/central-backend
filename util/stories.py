import re

from bs4 import BeautifulSoup
import requests


def get_title_from_url(url):
    try:
        response = requests.get(url + "feed/?withoutcomments=1")
        soup = BeautifulSoup(response.content, "xml")
        return soup.find("channel").find("item").find("title").text
    except:
        return None


def get_published_url(editor_url):
    post_id_match = re.search(r"post=(\d+)", editor_url)
    if not post_id_match:
        return None

    post_id = post_id_match.group(1)
    api_url = f"https://dailyillini.com/wp-json/wp/v2/posts/{post_id}"
    response = requests.get(api_url)

    data = response.json()
    if "link" in data:
        return data["link"]
    else:
        return None
