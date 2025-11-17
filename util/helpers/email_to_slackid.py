from util.slackbots._slackbot import app


def email_to_slackid(email: str):
    """
    Convert an email address to a Slack user ID using the Slack API.

    :param email: The @illinimedia.com email address of the user
    :type email: str
    :returns: The corresponding Slack ID
    :rtype: str
    """

    print(f"Converting email {email} to Slack ID...")
    try:
        user_info = app.client.users_lookupByEmail(email=email)
        slack_id = user_info["user"]["id"]
        print(f"Email {email} corresponds to Slack ID {slack_id}.")
        return slack_id
    except Exception as e:
        print(f"Error fetching Slack ID for email {email}: {e}")
        return None
