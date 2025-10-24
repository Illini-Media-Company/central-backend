from util.slackbot import app


def email_to_slackid(email):
    """Convert an email address to a Slack user ID using the Slack API."""
    print(f"Converting email {email} to Slack ID...")
    try:
        user_info = app.client.users_lookupByEmail(email=email)
        slack_id = user_info["user"]["id"]
        print(f"Email {email} corresponds to Slack ID {slack_id}.")
        return slack_id
    except Exception as e:
        print(f"Error fetching Slack ID for email {email}: {e}")
        return None
