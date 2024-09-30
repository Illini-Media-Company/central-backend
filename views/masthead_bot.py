from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from util.security import restrict_to, get_creds  
from constants import SLACK_BOT_TOKEN
from util.slackbot import app

# Slack config
SLACK_DEV_USER_ID = "C06FUS86EUD"  
webdev_channel_id = "C07MSGFK7K3"  


masthead_routes = Blueprint("mashead_routes", __name__, url_prefix="/masthead-ends")

    


@masthead_routes.route('/notify-webdev', methods=['POST'])
def notify_web_developer():
    """
    Endpoint to notify a web developer about a masthead change.
    Sends a message to a specific channel or user in Slack.
    """
    try:
        response = app.client.chat_postMessage(
            channel=webdev_channel_id, 
            text="Masthead change"
        )
        return jsonify({"message": "Notification sent successfully!"}), 200

    except SlackApiError as e:
        return jsonify({"error": str(e.response['error'])}), 500





