from flask import url_for
from util.slackbots._slackbot import app
from util.helpers.email_to_slackid import email_to_slackid
from constants import SLACK_BOT_TOKEN


def send_employee_agreement_notification(email: str, agreement_name: str):
    """
    Send a Slack message to an employee notifying them that an agreement is awaiting their signature.

    :param email: The email of the employee
    :type email: str
    :param agreement_name: The name of the agreement
    :type agreement_name: str
    :returns: A dictionary containing "ok" (bool, denotes whether successful).
        If False, "error" is the error message.
        If True, "channel" and "ts" are the Slack channel_id and timestamp of the message.
    :rtype: dit[str, Any]
    """
    try:
        user_slack_id = email_to_slackid(email)

        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=user_slack_id,
            text=f":wave: \"{agreement_name}\" is awaiting your signature. Sign it by clicking <{url_for('employee_agreement_routes.dashboard', _external=True)}|this link>.",
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[agreement-notif] DM to user failed: {e}")
        return {"ok": False, "error": str(e)}


def send_reviewer_notification(email: str, employee_email: str, agreement_name: str):
    """
    Send a Slack message to an editor, manager or EIC notifying them that an agreement is awaiting their signature.

    :param email: Email address of the editor, manager or EIC
    :type email: str
    :param employee_email: Email address of the employee
    :type employee_email: str
    :param agreement_name: The name of the agreement
    :type agreement_name: str
    :returns: A dictionary containing "ok" (bool, denotes whether successful).
        If False, "error" is the error message.
        If True, "channel" and "ts" are the Slack channel_id and timestamp of the message.
    :rtype: dict[str, Any]
    """

    try:
        recipient_slack_id = email_to_slackid(email)
        employee_slack_id = email_to_slackid(employee_email)

        text = f":wave: \"{agreement_name}\" for <@{employee_slack_id}> is awaiting your signature. Sign it by clicking <{url_for('employee_agreement_routes.dashboard', _external=True)}|this link>"

        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=recipient_slack_id,
            text=text,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[agreement-notif] DM to reviewer failed: {e}")
        return {"ok": False, "error": str(e)}


def send_confirmation_notification(email: str, agreement_name: str, ch: str, ts: str):
    """
    Send a Slack message to an employee notifying them that their agreement has been signed by all parties .

    :param email: The email of the employee
    :type email: str
    :param agreement_name: The name of the agreement
    :type agreement_name: str
    :param ch: The Slack channel_id that the original message was sent to
    :type ch: str
    :param ts: The Slack timestamp of the original message's send event
    :type ts: str

    :returns: A dictionary containing "ok" (bool, denotes whether successful).
        If False, "error" is the error message.
        If True, "channel" and "ts" are the Slack channel_id and timestamp of the message.
    :rtype: dit[str, Any]
    """
    try:
        user_slack_id = email_to_slackid(email)

        print(ch)
        print(ts)

        res = app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            channel=ch,
            text=f'"{agreement_name}" has been signed by all parties.',
            thread_ts=ts,
            reply_broadcast=True,
        )
        return {"ok": True, "channel": res["channel"], "ts": res["ts"]}
    except Exception as e:
        print(f"[agreement-notif] DM to user failed: {e}")
        return {"ok": False, "error": str(e)}
