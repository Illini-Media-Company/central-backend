import os

from dotenv import load_dotenv


load_dotenv()


ENV = os.environ.get("ENV", "dev")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_POJECT_ID = os.environ.get("DATASTORE_PROJECT_ID", None)

REDDIT_USERNAME = "TheDailyIllini"
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", None)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", None)
SUBREDDIT = "UIUC"
FLAIR_ID = "a3994b2e-d384-11ea-bf32-0e7e74729027"  # News flair

TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", None)
TWITTER_API_KEY_SECRET = os.environ.get("TWITTER_API_KEY_SECRET", None)
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", None)
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", None)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", None)
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", None)
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", None)

CC_CLIENT_ID = os.environ.get("CC_CLIENT_ID", None)
CC_CLIENT_SECRET = os.environ.get("CC_CLIENT_SECRET", None)
