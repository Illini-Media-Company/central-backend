from typing import List, Optional, Tuple

from db.user import get_user
from util.security import update_groups
from util.slackbots._slackbot import app


def get_email_and_groups(
    slack_user_id: str, refresh_if_missing: bool = True
) -> Tuple[Optional[str], List[str]]:
    """
    Resolve a Slack user id to (email, groups).
    If groups are missing/empty, optionally refresh from Google Directory
    (synchronously) before returning.
    Returns (None, []) if the email cannot be resolved.
    """
    try:
        info = app.client.users_info(user=slack_user_id)
    except Exception as e:
        print(f"[slack_groups] users_info failed for {slack_user_id}: {e}")
        return None, []

    profile = (info or {}).get("user", {}).get("profile", {}) or {}
    email = profile.get("email")
    if not email:
        return None, []

    user = get_user(email)
    groups = user.groups if user else []

    if refresh_if_missing and not groups:
        try:
            update_groups(email)
            refreshed = get_user(email)
            groups = refreshed.groups if refreshed else []
        except Exception as e:
            print(f"[slack_groups] update_groups failed for {email}: {e}")
            groups = []

    return email, groups
