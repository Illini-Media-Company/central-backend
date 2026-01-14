import os

from dotenv import load_dotenv


load_dotenv()


ENV = os.environ.get("ENV", "dev")

# Google API keys and secrets
ADMIN_EMAIL = "di_admin@illinimedia.com"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_PROJECT_ID = os.environ.get("DATASTORE_PROJECT_ID", None)
GOOGLE_MAP_API = os.environ.get("GOOGLE_MAP_API", None)
FOOD_TRUCK_MAPS_ID = os.environ.get("FOOD_TRUCK_MAPS_ID", None)

APPS_SCRIPT_RUNNER_EMAIL = "apps-script-runner@illinimedia.com"
CONTEND_DOC_AUD = (
    "906651552672-3vsqi0s6ggr50gs1u7chgcn15hqlgg4e.apps.googleusercontent.com"
)

# Reddit API information
REDDIT_USERNAME = "TheDailyIllini"
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", None)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", None)
SUBREDDIT = "UIUC"
FLAIR_ID = "a3994b2e-d384-11ea-bf32-0e7e74729027"  # News flair

# Twitter API information
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", None)
TWITTER_API_KEY_SECRET = os.environ.get("TWITTER_API_KEY_SECRET", None)
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", None)
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", None)

# Tokens and secrets for the Slack app
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", None)
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", None)
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", None)

RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", None)

# Constant Contact secrets and keys
CC_CLIENT_ID = os.environ.get("CC_CLIENT_ID", None)
CC_CLIENT_SECRET = os.environ.get("CC_CLIENT_SECRET", None)
CC_LIST_MAPPING = {
    "headline_news": "01d15d60-4c11-11e3-826c-d4ae52725666",
    "sports": "0fa0f9d0-f33e-11e8-bed9-d4ae52733d3a",
    "wpgu": "01ff9950-4c11-11e3-826c-d4ae52725666",
    "daily-urbana": "8f76cac0-dfdf-11ee-9c51-fa163e5bc304",
    "daily-champaign": "4ab95568-f215-11ee-9e0c-fa163e7b09ec",
    "chambana-eats": "85312ef2-2292-11ef-8298-fa163edfff7e",
}

OV_ENDPOINT = os.environ.get("OV_ENDPOINT", None)

RETOOL_API_KEY = os.environ.get("RETOOL_API_KEY", None)

# Google Calendar IDs
MAIN_IMC_GCAL_ID = (
    "illinimedia.com_8cati95103kg5o3h8i11hmu0lo@group.calendar.google.com"
)
COPY_EDITING_GCAL_ID = "c_ce11637c04b9e766b04cf09ca41c971bd6b567648308d2ee53823cea6672ae4a@group.calendar.google.com"

# Google Resource Calendar IDs
NEWS_CONF_RESOURCE_GCAL_ID = (
    "c_1880trl645hpqj39k57idpvutni6g@resource.calendar.google.com"
)
BIS_CONF_RESOURCE_GCAL_ID = (
    "c_188756k7nm7tkgu4gpsiqsb07802a@resource.calendar.google.com"
)
WPGU_OFFICE_RESOURCE_GCAL_ID = (
    "c_188ejl7c2di5uisrjp7qdcu8f7pto@resource.calendar.google.com"
)
WPGU_ONAIR_GCAL_ID = "c_b888554deb36a74a61aea32bac28ab500ade0003cd2ae61085354e07c2fa0fa0@group.calendar.google.com"

################################################################################
### EMPLOYEE MANAGEMENT SYSTEM #################################################
################################################################################

# Google Groups with admin access to EMS
EMS_ADMIN_ACCESS_GROUPS = [
    "webdev",
    "imc-staff-webdev",
    "helpdesk",
    "student-managers",
    "professional-staff",
]

IMC_BRANDS = [
    "IMC",
    "The Daily Illini",
    "WPGU",
    "Illio",
    "Chambana Eats",
    "Illini Content Studio",
]
PAY_TYPES = ["Unpaid", "Hourly", "Salary", "Stipend"]
EMPLOYEE_STATUS_OPTIONS = ["Active", "Inactive", "Onboarding", "Offboarding"]
DEPART_CATEGORIES = ["Voluntary", "Involuntary", "Administrative"]
DEPART_REASON_VOL = [
    "Resigned",
    "Dissatisfaction",
    "Did Not Return",
    "Higher Pay Elsewhere",
    "Personal Reasons",
]
DEPART_REASON_INVOL = [
    "Terminated for Performance",
    "Terminated for Misconduct",
    "Attendance Issue",
    "Position Eliminated",
    "Insubordination",
]
DEPART_REASON_ADMIN = [
    "Promoted",
    "Completed Term",
    "Graduated",
    "No Longer Student",
    "Duplicate Record",
    "Administrative Error",
    "Reorganization",
    "Other/Unknown",
]

################################################################################

# Lists of Google Groups that control access to APIs
TOOLS_ADMIN_ACCESS_GROUPS = [
    "webdev",
    "imc-staff-webdev",
    "ceo",
    "student-managers",
]  # Ability to add and modify tools that display on the index page

# Slack channels (used by Slack bot)
IMC_GENERAL_ID = "C13TEC3QE" if ENV == "prod" else "C06GADGT60Z"
IMC_GENERAL_TEST_ID = "C06LDL7RG3X" if ENV == "prod" else None
DI_ANNOUNCEMENTS_ID = "C06BSL71W2Z" if ENV == "prod" else "C06G089F8S0"
ILLIO_ANNOUNCEMENTS_ID = "C06BVLLQPAP" if ENV == "prod" else "C06FXMB42MR"
WPGU_ANNOUNCEMENTS_ID = "C06BY7S6F44" if ENV == "prod" else "C06G08KP11S"
ICS_GENERAL_ID = "C06CB7QMZ97" if ENV == "prod" else "C06FXQSRB5G"

IMC_ADVERTISING_ID = "C06C12D8H6Y" if ENV == "prod" else "C06FR635SPQ"
IMC_MARKETING_ID = "C06BYF9TD99" if ENV == "prod" else "C06FR63HURL"
IMC_FRONTDESK_ID = "C0696V7DMJQ" if ENV == "prod" else "C06FUT4LHHT"

ILLIO_DESIGN_ID = "C06BV3CL1B4" if ENV == "prod" else "C06FXMHUQ3V"
ILLIO_PHOTO_ID = "C06BV033D4K" if ENV == "prod" else "C06GAE3QKMX"
ILLIO_WRITER_ID = "C06BXGP8Y12" if ENV == "prod" else "C06FH8HF46B"

WPGU_ENGINEERING_ID = "C09E51RTPRB" if ENV == "prod" else "C06G08SQZEG"
WPGU_ILLINI_DRIVE_ID = "C06BJ1XSPK9" if ENV == "prod" else "C06FXMKG97D"
WPGU_MARKETING_ID = "C09FP4VLHL4" if ENV == "prod" else "C06FXMKPMU3"
WPGU_MUSIC_ID = "C09E7KWAR7C" if ENV == "prod" else "C06GLJD5VUY"
WPGU_NEWS_ID = "C08KCADDCD8" if ENV == "prod" else "C06FXML7BHR"
WPGU_ON_AIR_ID = "C06BRUCMUG6" if ENV == "prod" else "C06FR61KDJS"
WPGU_PRODUCTION_ID = "C09ET1PT762" if ENV == "prod" else "C06FXQXKJAE"
WPGU_SPORTS_ID = "C09FRSTPVAL" if ENV == "prod" else "C09V8V4K5K8"

PHOTO_REQUESTS_CHANNEL_ID = (
    "C09NCRWU8T1" if ENV == "dev" else "C09CJMTAYHW"
)  # #imc_photo — Channel that all photo request get sent to
COURTESY_REQUESTS_CHANNEL_ID = (
    "C09R16GJZBP" if ENV == "dev" else "C09SG769Y6L"
)  # #imc_courtesy-photos — Channel that all courtesy photo requests get sent to
