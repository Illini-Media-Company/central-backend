from flask_login import current_user
import praw

from constants import (
    ENV,
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    SUBREDDIT,
    FLAIR_ID,
)
from db.social_post import SocialPlatform, create_post, check_limit


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
            reddit_url = "https://www.reddit.com" + submission.permalink
        except Exception as e:
            return None, (str(e), 500)

    create_post(
        title=title,
        url=reddit_url,
        platform=SocialPlatform.REDDIT,
        created_by=current_user.name,
    )
    return reddit_url, None
