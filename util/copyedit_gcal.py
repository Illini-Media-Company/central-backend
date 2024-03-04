from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar

from constants import COPY_CHIEF_EMAIL, COPY_EDIT_GCAL_ID, SLACK_BOT_TOKEN
from util.security import get_creds
from util.slackbot import app
from db.user import get_user_last_edited, update_user_last_edited

ZONE_UTC = ZoneInfo("UTC")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
SHIFT_END_BUFFER = 10  # Threshold to skip shift if there is SHIFT_END_BUFFER minutes or less remaining in shift

# Returns the email address of the copy editor on shift who has last edited a story the earliest. If no copy editor is on shift, returns a default email (i.e. copy chief's email).
def get_editor_email(is_urgent=False):
    # Generating credentials for service account
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDIT_GCAL_ID, credentials=creds)

    # Generating values for handling date/time. To simplify things, all date/time values will be stored as UTC
    curr_time = datetime.now(tz=ZONE_UTC)
    end = curr_time + timedelta(hours=2)

    if is_urgent:
        end = curr_time + timedelta(minutes=SHIFT_END_BUFFER + 5)
    
    events = list(gc.get_events(curr_time, end, single_events=True, timezone=ZONE_UTC))

    # Simplified handling of instances where there is only a single event/shift
    if len(events) == 1 and events[0].end.replace(tzinfo=ZONE_UTC) < (curr_time + timedelta(minutes=SHIFT_END_BUFFER)) and len(events[0].attendees) != 0:
        email = events[0].attendees[0].email
        name = events[0].attendees[0].display_name
        update_user_last_edited(name, email, curr_time)
        return email
    elif len(events) == 1: # if there is only a single shift AND it is about to end, then return default email
        return None

    # List of tuples: [(editor email, last edited, name), ...] for cases with are multiple events
    last_edited_list = [(event.attendees[0].email, get_user_last_edited(event.attendees[0].email) or datetime.min.replace(tzinfo=ZONE_UTC), event.attendees[0].display_name) 
                        for event in events 
                        # If statement for skipping events where an editor's shift is about to end
                        if event.end.replace(tzinfo=ZONE_UTC) < (curr_time + timedelta(minutes=SHIFT_END_BUFFER)) and len(event.attendees) != 0] 

    # Returns email for the copy editor if last_edited_list isn't empty and updates last_edited field
    if len(last_edited_list) == 1:
        email = last_edited_list[0][0]
        name = last_edited_list[0][2]
        update_user_last_edited(name, email, curr_time)
        return email
    elif len(last_edited_list) > 1:
        last_edited_list.sort(key=lambda x: x[1])
        email = last_edited_list[0][0]
        name = last_edited_list[0][2]
        update_user_last_edited(name, email, curr_time)
        return email

    # otherwise returns default email
    return None

def copy_edit_messaging(edit_link):
    if app == None:
        raise ValueError("Slackbolt app cannot be None")
    userEmail = get_editor_email() or COPY_CHIEF_EMAIL
    userInfo = app.client.users_lookupByEmail(email=userEmail)
    userId = userInfo["user"]["id"]
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        username="Copy Bot",
        channel=userId,
        text="A new story is ready for copyediting: " + edit_link
    )