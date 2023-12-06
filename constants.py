import os

from dotenv import load_dotenv


load_dotenv()

ENV = os.environ.get('ENV', 'dev')

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)

REDDIT_USERNAME = 'TheDailyIllini'
REDDIT_PASSWORD = os.environ.get('REDDIT_PASSWORD', None)
REDDIT_CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID', None)
REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET', None)
SUBREDDIT = 'UIUC'
