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

COPY_EDIT_GCAL_ID = "c_7f9830c5fef0310931ee81c0c61b63bb05612190984b8bc15652a34bffffa618@group.calendar.google.com" # Google Calendar ID for copy editing schedule
COPY_CHIEF_EMAIL = "***REMOVED***" if ENV != "dev" else "default@test.test"