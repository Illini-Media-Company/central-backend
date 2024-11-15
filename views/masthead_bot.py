from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from util.security import restrict_to, get_creds
from constants import SLACK_BOT_TOKEN
from util.slackbot import app
from util.security import get_creds
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.background import BackgroundScheduler


# Slack config
SLACK_DEV_USER_ID = "C06FUS86EUD"
webdev_channel_id = "C07MSGFK7K3"

scheduler = BackgroundScheduler()
scheduler.start()

masthead_routes = Blueprint("mashead_routes", __name__, url_prefix="/masthead-ends")


def get_google_sheet_data():
    try:
        creds = get_creds(SCOPES)
        client = gspread.authorize(creds)

        # Sheet name or key
        sheet = client.open("Test script").sheet1
        return sheet
    except gspread.exceptions.APIError as e:
        print(f"Error accessing Google Sheet: {e}")
        return None


def check_masthead_and_notify():
    """Checks the masthead for the current month and notifies the web developer if it's empty."""
    now = datetime.now(ZoneInfo("America/Chicago"))
    month = now.strftime("%B")  # Current month as a string
    sheet = get_google_sheet_data()

    # Assuming masthead title is in the first column
    masthead_title = sheet.cell(1, now.month).value  # Need to offset

    if not masthead_title:  # If the masthead title is empty
        try:
            app.client.chat_postMessage(
                token=SLACK_BOT_TOKEN,
                channel=webdev_channel_id,
                text=f"Masthead title for {month} is empty. Please update it.",
            )
            return jsonify({"message": "Notification sent to web developer."}), 200
        except SlackApiError as e:
            return (
                jsonify({f"Error sending notification": str(e.response["error"])}),
                500,
            )


def schedule_monthly_check():
    """Schedules the check to run on the first day of each month at 9 AM."""
    now = datetime.now(ZoneInfo("America/Chicago"))
    first_day_next_month = (now.replace(day=1) + timedelta(days=31)).replace(day=1)
    next_run = first_day_next_month.replace(hour=9, minute=0, second=0, microsecond=0)

    scheduler.add_job(check_masthead_and_notify, DateTrigger(run_date=next_run))


@scheduler.scheduled_job("cron", day=1, hour=9, minute=0, id="monthly_check")
def scheduled_job():
    check_masthead_and_notify()


@masthead_routes.route("/notify-webdev", methods=["POST"])
def notify_web_developer():
    """
    Endpoint to notify a web developer about a masthead change.
    Sends a message to a specific channel or user in Slack.
    """
    try:
        response = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN, channel=webdev_channel_id, text="Masthead change"
        )
        return jsonify({"message": "Notification sent successfully!"}), 200

    except SlackApiError as e:
        return jsonify({"error": str(e.response["error"])}), 500


schedule_monthly_check()
