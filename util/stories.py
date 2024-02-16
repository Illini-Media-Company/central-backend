from bs4 import BeautifulSoup
import praw
import requests
from requests_oauthlib import OAuth1

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
    # Setup OAuth1 authentication
    oauth = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET_KEY, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    
    # Endpoint for tweeting
    api_url = "https://api.twitter.com/2/tweets"
    
    # Prepare the tweet
    tweet_text = f"{title} {url}"
    
    # Make a POST request to TwitterAPI
    response = requests.post(api_url, json={"text": tweet_text}, auth=oauth)
    
    if response.status_code == 201:
        tweet_data = response.json()
        tweet_id = tweet_data["data"]["id"]
        tweet_url = f"https://twitter.com/user/status/{tweet_id}"
        return tweet_url
    else:
        raise Exception(f"Failed to post tweet: {response.text}")