"""
Implements functions for automatic posting to Twitter/X, Reddit, and the 
Illinois app.

Created on ___ by ___
Last modified by Jacob Slabosz on Feb. 21, 2026
"""

from flask_login import current_user
import praw
import logging
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
from db.social_post import SocialPlatform, add_post, check_limit

logger = logging.getLogger(__name__)

TWITTER_API_URL = "https://api.twitter.com/2/tweets"


def send_illinois_app_notification(title, url):
    if check_limit(SocialPlatform.ILLINOIS_APP, 3, 7):
        return None, (
            "ERROR: 3 push notifications have been sent in the past 7 days.",
            403,
        )
    # TODO implement this

    try:
        add_post(
            title=title,
            url=url,
            platform=SocialPlatform.ILLINOIS_APP,
            created_by=current_user.name,
        )
        logger.debug(
            f"Successfully created SocialPost object for Illinois app notification: {title} - {url}"
        )
    except Exception as e:
        logger.error(f"Error adding post to database: {e}")
        return None, (str(e), 500)

    return url, None


def post_to_reddit(title, url):
    logger.info(f"Attempting to post to Reddit: {title} - {url}")
    if ENV == "dev" and REDDIT_CLIENT_SECRET is None:
        logger.warning(
            "Environment is 'dev' and REDDIT_CLIENT_SECRET is missing. Skipping actual Reddit API call."
        )
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
            reddit_url = "https://www.reddit.com" + submission.permalink
        except Exception as e:
            logger.exception(f"Error posting to Reddit: {e}")
            return None, (str(e), 500)

    try:
        if current_user and current_user.is_authenticated:
            logger.info(f"Current user is authenticated: {current_user.name}")
            created_by = current_user.name
        else:
            logger.info(
                "No authenticated user found. Defaulting created_by to 'System (Scout)'."
            )
            created_by = "System (Scout)"

        add_post(
            title=title,
            url=reddit_url,
            platform=SocialPlatform.REDDIT,
            created_by=created_by,
        )
        logger.debug(
            f"Successfully created SocialPost object for Reddit post: {title} - {reddit_url}"
        )
    except Exception as e:
        logger.exception(f"Error adding post to database: {e}")
        return None, (str(e), 500)

    return reddit_url, None


def post_to_twitter(title, url):
    logger.info(f"Attempting to post to Twitter: {title} - {url}")
    if ENV == "dev" and TWITTER_API_KEY_SECRET is None:
        logger.warning(
            "Environment is 'dev' and TWITTER_API_KEY_SECRET is missing. Skipping actual Twitter API call."
        )
        tweet_url = ""
    else:
        try:
            # Setup OAuth1 authentication
            logger.debug("Setting up OAuth1 authentication.")
            oauth = OAuth1(
                TWITTER_API_KEY,
                TWITTER_API_KEY_SECRET,
                TWITTER_ACCESS_TOKEN,
                TWITTER_ACCESS_TOKEN_SECRET,
            )
            tweet_text = f"{title}\n\n📲 Click the link to read more: {url}"

            logger.info(f"Sending POST request to Twitter API with text: {tweet_text}")
            response = requests.post(
                TWITTER_API_URL, json={"text": tweet_text}, auth=oauth
            )
            if response.status_code != 201:
                logger.error(
                    f"Twitter API error: {response.status_code} - {response.text}"
                )
                return None, (response.text, 500)

            tweet_data = response.json()
            tweet_id = tweet_data["data"]["id"]
            tweet_url = f"https://twitter.com/user/status/{tweet_id}"
        except Exception as e:
            logger.exception(f"Error posting to Twitter: {e}")
            return None, (str(e), 500)

    try:
        if current_user and current_user.is_authenticated:
            logger.info(f"Current user is authenticated: {current_user.name}")
            created_by = current_user.name
        else:
            logger.info(
                "No authenticated user found. Defaulting created_by to 'System (Scout)'."
            )
            created_by = "System (Scout)"

        add_post(
            title=title,
            url=tweet_url,
            platform=SocialPlatform.TWITTER,
            created_by=created_by,
        )
        logger.debug(
            f"Successfully created SocialPost object for Twitter post: {title} - {tweet_url}"
        )
    except Exception as e:
        logger.exception(f"Error adding post to database: {e}")
        return None, (str(e), 500)

    return tweet_url, None
