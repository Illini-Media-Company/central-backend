from bs4 import BeautifulSoup
import praw
import requests
import re
from flask import jsonify

from constants import (
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    SUBREDDIT,
    FLAIR_ID,
)

def get_title_from_url(url):
    try:
        response = requests.get(url + "feed/?withoutcomments=1")
        soup = BeautifulSoup(response.content, "xml")
        return soup.find("channel").find("item").find("title").text
    except:
        return None

def post_to_reddit(title, url):
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=f"story submission by u/{REDDIT_USERNAME}",
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
    )
    subreddit = reddit.subreddit(SUBREDDIT)
    submission = subreddit.submit(title, url=url, flair_id=FLAIR_ID)
    return "https://www.reddit.com" + submission.permalink


def get_published_url(url):
    post_id_match = re.search(r'post=(\d+)', url)
    if not post_id_match:
        return jsonify({"error": "Invalid URL format. Please enter a valid URL."}), 400

    post_id = post_id_match.group(1)

    api_url = f"https://dailyillini.com/wp-json/wp/v2/posts/{post_id}"
    response = requests.get(api_url)

    data = response.json()

    if "code" in data and data["code"] == "rest_post_invalid_id":
        return jsonify({"result": "No publication could be found"})

    if "link" in data:
        return jsonify({"result": data["link"]})
    else:
        return jsonify({"result": "Unexpected response from the server"}), 500