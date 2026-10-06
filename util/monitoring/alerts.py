"""Slack alert transitions for monitoring results."""

import logging

from constants import ENV, MONITORING_SLACK_CHANNEL_ID
from util.monitoring.definitions import get_check_target


logger = logging.getLogger(__name__)

if ENV == "prod" and not MONITORING_SLACK_CHANNEL_ID:
    raise RuntimeError("MONITORING_SLACK_CHANNEL_ID must be configured in production")


def _post_message(text):
    if not MONITORING_SLACK_CHANNEL_ID:
        logger.error("MONITORING_SLACK_CHANNEL_ID is not configured")
        return False
    try:
        from util.slackbots._slackbot import app as slack_app

        response = slack_app.client.chat_postMessage(
            channel=MONITORING_SLACK_CHANNEL_ID, text=text
        )
        return bool(response.get("ok", True))
    except Exception:
        logger.exception("Unable to send backend monitoring Slack alert")
        return False


def send_alert_transition(definition, result, alert_active):
    """Send a new failure or recovery transition and report whether it was sent."""
    if definition["severity"] != "major":
        return False

    if result.status == "failed" and not alert_active:
        details = result.error_message or result.error_type or "Unknown failure"
        return _post_message(
            ":rotating_light: *Backend monitor failure*\n"
            f"*Service:* {definition['name']} (`{definition['id']}`)\n"
            f"*Target:* {get_check_target(definition)}\n"
            f"*Failure:* {details}\n"
            f"*Checked:* {result.checked_at.isoformat()}"
        )

    if result.status != "failed" and alert_active:
        return _post_message(
            ":white_check_mark: *Backend monitor recovered*\n"
            f"*Service:* {definition['name']} (`{definition['id']}`)\n"
            f"*Current status:* {result.status}\n"
            f"*Checked:* {result.checked_at.isoformat()}"
        )

    return False
