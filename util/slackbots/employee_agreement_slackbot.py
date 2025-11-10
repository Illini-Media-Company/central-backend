# SEEN
from util.slackbots.slackbot import app
from constants import SLACK_BOT_TOKEN


def send_employee_agreement_notification(user_slack_id, agreement_url):
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=user_slack_id,
            text=f":wave: Hello! A new agreement is awaiting your signature. Sign it by clicking <{agreement_url}|this link>.",
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[EA_agreement_notif] DM to user failed: {e}")
        return {"ok": False, "error": str(e)}


def send_reviewer_notification(recipient_slack_id, agreement):
    if not agreement:
        return {"ok": False, "error": "No agreement provided."}

    text = f":wave: <@{agreement.user_id}>'s employee agreement is awaiting your signature. Sign it by clicking <{agreement.agreement_url}|this link>"
    try:
        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=recipient_slack_id,
            text=text,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[EA_agreement_notif] DM to reviewer failed: {e}")
        return {"ok": False, "error": str(e)}
