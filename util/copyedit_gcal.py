import pytz
from collections import defaultdict
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar

#from constants import COPY_EDIT_GCAL_ID
from util.security import get_creds
from db.user import get_user_last_edited, update_user_last_edited

COPY_EDIT_GCAL_ID = "c_7f9830c5fef0310931ee81c0c61b63bb05612190984b8bc15652a34bffffa618@group.calendar.google.com"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# This is meant to represent checking the last_edited field in Google Cloud user DB
ISO_MIN_STR = datetime.min.isoformat()
#last_edited_dict = defaultdict(lambda: ISO_MIN_STR)

# Returns the email address of the copy editor on shift who has last edited a story the earliest. If no copy editor is on shift, returns a default email (i.e. copy chief's email).
def get_editor_email():
    # Generating credentials for service account
    creds = get_creds(SCOPES)
    
    gc = GoogleCalendar(COPY_EDIT_GCAL_ID, credentials=creds)

    # Generating values for handling date/time. To simplify things, all date/time values will be stored as UTC
    curr_time = datetime.now(pytz.utc)
    tomorrow = datetime.today().astimezone(pytz.utc) + timedelta(days=1)
    end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=pytz.timezone("America/Chicago")).astimezone(pytz.utc)
    
    events = list(gc.get_events(curr_time, end + timedelta(hours=12), single_events=True))
    
    # Getting editor emails from events, then sorts them based on the last_edited value.
    # TODO: replace defaultdict implementation with Google Cloud user DB for checking last_edited field
    last_edited_list = [(event.attendees[0].email, get_user_last_edited(event.attendees[0].email) or datetime.min, event.attendees[0].display_name) for event in events if event.end.replace(tzinfo=pytz.utc) > curr_time + timedelta(minutes=10) and len(event.attendees) != 0] # If statement for skipping events where the time remaining is less than a given num of minutes (i.e. shift is about to end)

    # Returns email for the copy editor if list isn't empty and updates last_edited field
    if len(last_edited_list) == 1:
        email = last_edited_list[0][0]
        name = last_edited_list[0][2]
        update_user_last_edited(name, email, curr_time)
        #last_edited_dict.update({email:curr_time.isoformat()})
        return email
    elif len(last_edited_list) > 1:
        last_edited_list.sort(key=lambda x: x[1])
        email = last_edited_list[0][0]
        name = last_edited_list[0][2]
        update_user_last_edited(name, email, curr_time)
        #last_edited_dict.update({email:curr_time.isoformat()})
        return email
    
    # otherwise returns None
    return None

# Function to send slack message to copy editor
def send_copy_edit_slack_msg(content:str, status):
    # To be implemented
    pass