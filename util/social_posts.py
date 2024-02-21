from flask_login import current_user
import praw
import requests
from requests_oauthlib import OAuth1

from constants import (
    ENV,
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    SUBREDDIT,
    FLAIR_ID,
    TWITTER_API_KEY,
    TWITTER_API_KEY_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
)
from db.social_post import SocialPlatform, create_post, check_limit


TWITTER_API_URL = "https://api.twitter.com/2/tweets"


def send_illinois_app_notification(title, url):
    if check_limit(SocialPlatform.ILLINOIS_APP, 3, 7):
        return None, (
            "ERROR: 3 push notifications have been sent in the past 7 days.",
            403,
        )
    # TODO implement this

    create_post(
        title=title,
        url=url,
        platform=SocialPlatform.ILLINOIS_APP,
        created_by=current_user.name,
    )
    return url, None


def post_to_reddit(title, url):
    if ENV == "dev" and REDDIT_CLIENT_SECRET is None:
        reddit_url = ""
    else:
        try:
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=f"story submission by u/{REDDIT_USERNAME}",
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD,
            )
            subreddit = reddit.subreddit(SUBREDDIT)
            submission = subreddit.submit(title, url=url, flair_id=FLAIR_ID)
            post_url = "https://www.reddit.com" + submission.permalink
        except Exception as e:
            return None, (str(e), 500)

    create_post(
        title=title,
        url=post_url,
        platform=SocialPlatform.REDDIT,
        created_by=current_user.name,
    )
    return post_url, None


def post_to_twitter(title, url):
    if ENV == "dev" and TWITTER_API_KEY_SECRET is None:
        tweet_url = ""
    else:
        # Setup OAuth1 authentication
        oauth = OAuth1(
            TWITTER_API_KEY,
            TWITTER_API_KEY_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET,
        )
        tweet_text = f"{title} {url}"
        response = requests.post(TWITTER_API_URL, json={"text": tweet_text}, auth=oauth)
        if response.status_code != 201:
            return None, (response.text, 500)

        tweet_data = response.json()
        tweet_id = tweet_data["data"]["id"]
        tweet_url = f"https://twitter.com/user/status/{tweet_id}"

    create_post(
        title=title,
        url=tweet_url,
        platform=SocialPlatform.TWITTER,
        created_by=current_user.name,
    )
    return tweet_url, None
