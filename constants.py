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

SNO_ADMIN_USERNAME = "di_admin"
SNO_ADMIN_PASSWORD = os.environ.get("SNO_ADMIN_PASSWORD", None)

# TwitterAPI credentials
TWITTER_API_KEY = ''
TWITTER_API_SECRET_KEY = ''
TWITTER_ACCESS_TOKEN = ''
TWITTER_ACCESS_TOKEN_SECRET = ''