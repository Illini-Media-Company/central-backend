from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar

from constants import COPY_EDITING_GCAL_ID, SLACK_BOT_TOKEN
from util.security import get_creds
from util.slackbot import app
from db.user import add_user, get_user, update_user_last_edited


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
SHIFT_OFFSET = timedelta(
    minutes=15
)  # Threshold to skip shift if there are SHIFT_OFFSET minutes or less remaining in shift
BREAKING_SHIFTS = [0, 1, 2, 3]
CONTENT_DOC_SHIFTS = [3, 4]


# Returns the email address of the copy editor on shift who has edited a story least recently, or None if there's no copy editor on shift.
def get_copy_editor(is_breaking):
    # Generate credentials for service account
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)

    # Get today's shifts
    current_time = datetime.now(tz=ZoneInfo("America/Chicago"))
    current_time_offset = current_time + SHIFT_OFFSET
    today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    shifts = gc.get_events(today, tomorrow, single_events=True, order_by="startTime")

    current_shift = None
    for i, shift in enumerate(shifts):
        if is_breaking and i in BREAKING_SHIFTS:
            if shift.start <= current_time_offset <= shift.end:
                current_shift = shift
                break
        elif not is_breaking and i in CONTENT_DOC_SHIFTS:
            if current_time_offset <= shift.end:
                current_shift = shift
                break

    editor = None
    if current_shift:
        for attendee in current_shift.attendees:
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


def notify_copy_editor(story_url, copy_chief_email, is_breaking):
    if app == None:
        raise ValueError("Slack app cannot be None!")
    editor = get_copy_editor(is_breaking)
    email = editor.email if editor else copy_chief_email
    user = app.client.users_lookupByEmail(email=email)["user"]["id"]
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="IMC Notification Bot",
        channel=user["id"],
        text="A new story is ready to be copy edited.\n" + story_url,
    )
    if email != copy_chief_email:
        copy_chief = app.client.users_lookupByEmail(email=copy_chief_email)["user"]
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            username="IMC Notification Bot",
            channel=copy_chief["id"],
            text=f"A new story is ready to be copy edited. {user['name']} has also been notified.\n",
        )
    print(f"Slack message sent to {email}.")
