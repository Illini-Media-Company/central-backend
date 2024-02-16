from bs4 import BeautifulSoup
import praw
import requests
import tweepy

from constants import (
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    SUBREDDIT,
    FLAIR_ID,
    TWITTER_API_KEY,
    TWITTER_API_SECRET_KEY,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET
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

def post_to_twitter(title, url):
    API_KEY = TWITTER_API_KEY
    API_SECRET_KEY = TWITTER_API_SECRET_KEY
    ACCESS_TOKEN = TWITTER_ACCESS_TOKEN
    ACCESS_TOKEN_SECRET = TWITTER_ACCESS_TOKEN_SECRET

    # Handling Twitter authentication
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    # Creating API object
    api = tweepy.API(auth)

    # Combining title and URL to form tweet content
    tweet = f"{title} {url}"

    # Tweeting
    status = api.update_status(status=tweet)

    # Return the tweet URL (assuming tweet was successful)
    tweet_id = status.id
    tweet_url = f"https://twitter.com/user/status/{tweet_id}"
    return tweet_url
