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

def send_reviewer_notification(recipient_slack_id, role, agreement):

    text = ""
    user_name = ""
    try: 
        user_info = app.client.users_info(user=agreement.user_id)
        user_name = user_info.get("user", {}).get("profile", {}).get("real_name", "the new hire")
        if role == "editor":
            text = f":wave: {user_name} has signed their employee agreement. It's now ready for your review: {agreement.agreement_url}"
        elif role == "manager": 
            text = f":information_source: {user_name}'s agreement has been approved by the editor. It's now ready for your review: {agreement.agreement_url}"
        elif role == "chief":
            text = f":information_source: {user_name}'s agreement has been approved by the manager and is ready for your final signature: {agreement.agreement_url}"
    except Exception as e:
        print(f"Error fetching user names for notification: {e}")
        text = f"An agreement is ready for your review. Please check your queue. {agreement.agreement_url}"

    app.client.chat_postMessage(
        token =SLACK_BOT_TOKEN,
        username="EA Bot",
        icon_emoji=":robot_face:",
        channel=recipient_slack_id,
        text=text,
    )
    