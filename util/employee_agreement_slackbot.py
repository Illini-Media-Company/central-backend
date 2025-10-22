from util.slackbot import app
from constants import ENV
from constants import SLACK_BOT_TOKEN

IMC_GENERAL_ID = "C13TEC3QE" if ENV == "prod" else "C06GADGT60Z"
EA_BOT_TESTER_ID = "C09M4KA1ZCL"


def send_employee_agreement_notification(user_slack_id, agreement_url):
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="EA Bot",
        icon_emoji=":robot_face:",
        channel=user_slack_id,
        text=f":wave: Hello! Please review and sign the Employee Agreement here: {agreement_url}",
    )

def send_hiring_manager_notification(manager_slack_id, user_name, agreement_url):
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="EA Bot",
        icon_emoji=":robot_face:",
        channel=manager_slack_id,
        text=f":information_source: {user_name} has signed the Employee Agreement. You can review it here: {agreement_url}",
    )



def follow_up_notification(user_slack_id):
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            username="EA Bot",
            icon_emoji=":robot_face:",
            channel=user_slack_id,
            text=":white_check_mark: Thank you for signing the Employee Agreement!",
        )