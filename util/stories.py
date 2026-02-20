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


def get_story_details_from_url(url):
    try:
        response = requests.get(url + "feed/?withoutcomments=1")
        soup = BeautifulSoup(response.content, "xml")
        item = soup.find("channel").find("item")

        title = None
        try:
            title = item.find("title").text
        except:
            title = None

        writer_name = None
        try:
            dc_creator = item.find("dc:creator")
            if dc_creator and dc_creator.text:
                writer_name = dc_creator.text.strip()
        except:
            writer_name = None

        image_url = None
        try:
            media_content = item.find("media:content")
            if media_content and media_content.get("url"):
                image_url = media_content.get("url").strip()
        except:
            image_url = None

        photographer_name = None

        return {
            "title": title,
            "writer_name": writer_name,
            "photographer_name": photographer_name,
            "image_url": image_url,
        }
    except:
        return {
            "title": None,
            "writer_name": None,
            "photographer_name": None,
            "image_url": None,
        }
