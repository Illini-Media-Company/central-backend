from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar

from constants import COPY_EDITING_GCAL_ID, SLACK_BOT_TOKEN
from util.security import get_creds
from util.slackbot import app
from db.user import add_user, get_user, update_user_last_edited


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
SHIFT_OFFSET = timedelta(
    minutes=10
)  # Threshold to skip shift if there is SHIFT_END_BUFFER minutes or less remaining in shift


# Returns the email address of the copy editor on shift who has edited a story least recently, or None if there's no copy editor on shift.
def get_current_copy_editor():
    # Generate credentials for service account
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)

    # Get current shift(s)
    current_time = datetime.now()
    events = gc.get_events(
        current_time - SHIFT_OFFSET, current_time, single_events=True
    )

    editor = None
    for event in events:
        for attendee in event.attendees:
            user = get_user(attendee.email)
            if user is None:
                user = add_user(
                    sub=None, name=attendee.display_name, email=attendee.email
                )

            # Select user who edited another story least recently, or first user who has not edited a story yet
            if user.last_edited is None:
                editor = user
                break
            elif editor is None or user.last_edited < editor.last_edited:
                editor = user

    if editor:
        update_user_last_edited(editor.email, current_time)
        return editor
    else:
        return None


def notify_current_copy_editor(story_url, copy_chief_email):
    if app == None:
        raise ValueError("Slack app cannot be None!")
    editor = get_current_copy_editor()
    email = editor.email if editor else copy_chief_email
    user_id = app.client.users_lookupByEmail(email=email)["user"]["id"]
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="IMC Notification Bot",
        channel=user_id,
        text="A new story is ready to be copy edited.\n" + story_url,
    )
