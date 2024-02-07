import os

from dotenv import load_dotenv


load_dotenv()

ENV = "dev" #os.environ.get("ENV", "dev")

GOOGLE_CLIENT_ID = "***REMOVED***"#os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = "***REMOVED***"#os.environ.get("GOOGLE_CLIENT_SECRET", None)

REDDIT_USERNAME = "TheDailyIllini"
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", None)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", None)
SUBREDDIT = "UIUC"
FLAIR_ID = "a3994b2e-d384-11ea-bf32-0e7e74729027"  # News flair

SNO_ADMIN_USERNAME = "di_admin"
SNO_ADMIN_PASSWORD = os.environ.get("SNO_ADMIN_PASSWORD", None)

CC_CLIENT_ID = os.environ.get("CC_CLIENT_ID", None)
CC_CLIENT_SECRET = os.environ.get("CC_CLIENT_SECRET", None)
