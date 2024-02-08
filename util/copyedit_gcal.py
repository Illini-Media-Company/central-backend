import pytz
from collections import defaultdict
from datetime import datetime, timedelta

from gcsa.google_calendar import GoogleCalendar
from google.oauth2 import service_account
from google.auth import (
    default,
    iam,
    transport
)

from constants import COPY_EDIT_GCAL_ID
from constants import COPY_CHIEF_EMAIL # TODO: maybe replace this with dynamically fetching GCloud DB user with copy chief role when implemented
from db.user import get_user

TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]

# This is meant to represent checking the last_edited field in Google Cloud user DB
# TODO: remove this once Google Cloud user DB is implemented
last_edited_dict = defaultdict(lambda: datetime.min.astimezone(pytz.utc).isoformat())

# Returns the email address of the copy editor on shift who has last edited a story the earliest. If no copy editor is on shift, returns a default email (i.e. copy chief's email).
def get_editor_email(is_urgent:bool=False):
    # Generating credentials for service account
    creds, _ = default()
    request = transport.requests.Request()
    creds.refresh(request)
    signer = iam.Signer(request, creds, creds.service_account_email)
    creds = service_account.Credentials(
        signer,
        creds.service_account_email,
        TOKEN_URL,
        scopes=SCOPES,
        subject="di_admin@illinimedia.com",
    )
    
    gc = GoogleCalendar(COPY_EDIT_GCAL_ID, credentials=creds)

    # Generating values for handling date/time. To simplify things, all date/time values will be stored as UTC
    curr_time = datetime.now(pytz.utc)
    tomorrow = datetime.today().astimezone(pytz.utc) + timedelta(days=1)
    end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=pytz.timezone("America/Chicago")).astimezone(pytz.utc)

    # If the story is not urgent and there are no events scheduled between now and midnight, then we fetch events for tomorrow morning as well
    if len(events) == 0 and not is_urgent:
        events = list(gc.get_events(curr_time, end + timedelta(hours=12), order_by="startTime", timezone=pytz.utc, single_events=True))
    # Otherwise, we only fetch the events for today
    else:
        events = list(gc.get_events(curr_time, end, order_by="startTime", timezone=pytz.utc, single_events=True))
    
    # Getting editor emails from events, then sorts them based on the last_edited value.
    # TODO: replace defaultdict implementation with Google Cloud user DB for checking last_edited field
    last_edited_list = [(event.attendees[0].email, last_edited_dict[event.attendees[0].email]) for event in events if event.end.replace(tzinfo=pytz.utc) > curr_time + timedelta(minutes=10)] # If statement for skipping events where the time remaining is less than a given num of minutes (i.e. shift is about to end)
    last_edited_list.sort(key=lambda x: x[1]) 

    # Returns email for the copy editor if list isn't empty and updates last_edited field
    if len(last_edited_list) > 0:
        email = last_edited_list[0][0]
        last_edited_dict.update({email:curr_time.isoformat()}) # TODO: replace this line with equiv Google Cloud user implementation
        return email
    
    # otherwise returns default email (i.e copy chief)
    return COPY_CHIEF_EMAIL

# Function to send slack message to copy editor
def send_copy_edit_slack_msg(content:str, status):
    # To be implemented
    pass
