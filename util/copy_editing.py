from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar
from gcsa.attendee import Attendee

from constants import COPY_EDITING_GCAL_ID, SLACK_BOT_TOKEN
from db.kv_store import kv_store_get, kv_store_set
from db.user import add_user, get_user, update_user_last_edited
from util.security import get_creds
from util.slackbot import app


SCOPES = ["https://www.googleapis.com/auth/calendar"]
SHIFT_OFFSET = timedelta(
    minutes=15
)  # Threshold to skip shift if there are SHIFT_OFFSET minutes or less remaining in shift
BREAKING_SHIFTS = [0, 1, 2, 3]
CONTENT_DOC_SHIFTS = [3, 4, 5, 6]


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
    print(shifts)

    current_shift = None
    for i, shift in enumerate(shifts):
        # if is_breaking and i in BREAKING_SHIFTS:
        #     if shift.start <= current_time_offset <= shift.end:
        #         current_shift = shift
        #         break
        # elif not is_breaking and i in CONTENT_DOC_SHIFTS:
        #     if current_time_offset <= shift.end:
        #         current_shift = shift
        #         break
        if i in BREAKING_SHIFTS or i in CONTENT_DOC_SHIFTS:
            if shift.start <= current_time_offset <= shift.end:
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


def notify_copy_editor(story_url, is_breaking, copy_chief_email=None):
    if app is None:
        raise ValueError("Slack app cannot be None!")

    if copy_chief_email is None:
        # Get cached copy chief email
        copy_chief_email = kv_store_get("COPY_CHIEF_EMAIL")
    else:
        kv_store_set("COPY_CHIEF_EMAIL", copy_chief_email)

    editor = get_copy_editor(is_breaking)
    email = editor.email if editor else copy_chief_email
    slack_id = app.client.users_lookupByEmail(email=email)["user"]["id"]
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="IMC Notification Bot",
        channel=slack_id,
        text="A new story is ready to be copy edited.\n" + story_url,
    )
    if email != copy_chief_email:
        app.client.chat_postMessage(
            token=SLACK_BOT_TOKEN,
            username="IMC Notification Bot",
            channel=app.client.users_lookupByEmail(email=copy_chief_email)["user"][
                "id"
            ],
            text=(
                "A new story is ready to be copy edited. "
                f"<@{slack_id}> has also been notified.\n"
            )
            + story_url,
        )
    print(f"Slack message sent to {email}.")


def add_copy_editor(editor_email, day_of_week, shift_num):
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)

    # Define shift start times
    shift_starts = ["8:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]

    try:
        # Convert inputs to integers
        shift_num = int(shift_num)
        day_of_week = int(day_of_week)
    except ValueError:
        # Handle invalid inputs
        print("Error: shift_num and/or day_of_week is not a valid integer.")
        return

    # Check if shift_num is within range
    if not 0 <= shift_num < len(shift_starts):
        print("Error: shift_num is out of range.")
        return

    # Calculate the next occurrence of the specified day of the week
    today = datetime.now().date()
    days_ahead = (day_of_week - today.weekday()) % 7
    next_day_of_week = today + timedelta(days=days_ahead)
    print("Next day of week: ", next_day_of_week)

    # Retrieve events from the Google Calendar API
    event = gc.get_events(
        time_min=datetime.now().date(),
        single_events=True,
        timezone="America/Chicago",
        order_by="startTime",
    )

    # Iterate over events to find the relevant one for the specified shift
    for e in list(event):
        if (e.start.strftime("%H:%M") == shift_starts[shift_num]) and (
            (e.start.date() - next_day_of_week).days % 7 == 0
        ):
            sample_event = e
            print(e.attendees)
            break

    # Retrieve instances of the recurring event
    recurr = gc.get_instances(sample_event.recurring_event_id)

    # Iterate over instances to check and add the editor email if not already present
    for e in list(recurr):
        if editor_email in e.attendees:
            continue
        e.add_attendee(editor_email)
        gc.update_event(e)
        print(e.start, "  |  ", e.attendees)


def remove_copy_editor(editor_email, day_of_week, shift_num):
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)

    # Define shift start times
    shift_starts = ["8:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]

    try:
        # Convert inputs to integers
        shift_num = int(shift_num)
        day_of_week = int(day_of_week)
    except ValueError:
        # Handle invalid inputs
        print("Error: shift_num and/or day_of_week is not a valid integer.")
        return
    # Check if shift_num is within range
    if not 0 <= shift_num < len(shift_starts):
        print("Error: shift_num is out of range.")
        return

    # Calculate the next occurrence of the specified day of the week
    today = datetime.now().date()
    days_ahead = (day_of_week - today.weekday()) % 7
    next_day_of_week = today + timedelta(days=days_ahead)
    print("Next day of week: ", next_day_of_week)

    event = gc.get_events(
        time_min=datetime.now().date(),
        single_events=True,
        timezone="America/Chicago",
        order_by="startTime",
    )

    # Iterate over events to find the relevant one for the specified shift
    for e in list(event):
        if (e.start.strftime("%H:%M") == shift_starts[shift_num]) and (
            (e.start.date() - next_day_of_week).days % 7 == 0
        ):
            r_id = e.recurring_event_id
            print(e.attendees)
            break

    # Retrieve instances of the recurring event
    recurr = gc.get_instances(r_id)

    # Iterate over instances to remove the editor email if present
    for e in list(recurr):
        l = e.attendees
        try:
            l.remove(editor_email)
            e.attendees = l
            gc.update_event(e)
        except ValueError:
            # Handle the case where editor_email is not in the attendee's list
            return "Not yet in attendee's list.", 401
        print(e.start, "  |  ", e.attendees)
