import os

from dotenv import load_dotenv


load_dotenv()


ENV = os.environ.get("ENV", "dev")

ADMIN_EMAIL = "di_admin@illinimedia.com"
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

RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", None)

CC_CLIENT_ID = os.environ.get("CC_CLIENT_ID", None)
CC_CLIENT_SECRET = os.environ.get("CC_CLIENT_SECRET", None)
CC_LIST_MAPPING = {
    "headline_news": "01d15d60-4c11-11e3-826c-d4ae52725666",
    "sports": "0fa0f9d0-f33e-11e8-bed9-d4ae52733d3a",
    "wpgu": "01ff9950-4c11-11e3-826c-d4ae52725666",
    "daily-urbana": "8f76cac0-dfdf-11ee-9c51-fa163e5bc304",
    "daily-champaign": "4ab95568-f215-11ee-9e0c-fa163e7b09ec",
    "chambana-eats": "85312ef2-2292-11ef-8298-fa163edfff7e"
}

RETOOL_API_KEY = os.environ.get("RETOOL_API_KEY", None)

COPY_EDITING_GCAL_ID = "c_ce11637c04b9e766b04cf09ca41c971bd6b567648308d2ee53823cea6672ae4a@group.calendar.google.com"
WPGU_ON_AIR_GCAL_ID = "c_b888554deb36a74a61aea32bac28ab500ade0003cd2ae61085354e07c2fa0fa0@group.calendar.google.com"

APPS_SCRIPT_RUNNER_EMAIL = "apps-script-runner@illinimedia.com"
CONTEND_DOC_AUD = (
    "906651552672-3vsqi0s6ggr50gs1u7chgcn15hqlgg4e.apps.googleusercontent.com"
)
