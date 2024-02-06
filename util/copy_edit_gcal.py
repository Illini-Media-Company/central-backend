from gcsa.google_calendar import GoogleCalendar
from google.oauth2 import service_account
from collections import defaultdict
from datetime import datetime, timedelta
import pytz

cred = service_account.Credentials.from_service_account_file("[filepath to json]")
GCAL_ID = "[calendar id]"

gc = GoogleCalendar(GCAL_ID, credentials=cred)

# This is meant to represent checking the last_edited field in Google Cloud user DB
# TODO: remove this once Google Cloud user DB is implemented
last_edited_dict = defaultdict(lambda: datetime.min)
last_edited_dict["test2@test.test"] = datetime.fromisoformat("2024-02-01T20:07:02.000Z")
last_edited_dict["test@test.com"] = datetime.fromisoformat("2024-01-25T20:07:02.000Z")

# TODO: replace this with dynamically fetching GCloud user with copy chief role
DEFAULT_EDITOR_EMAIL = "copychief@test.test"

# Returns the email address of the copy editor on shift who has last edited a story the earliest. If no copy editor is on shift, returns a default email (i.e. copy chief's email).
def get_editor_email(is_urgent:bool=False):
    # Generating values for handling date/time. To simplify things, all date/time values will be in UTC
    curr_time = datetime.now(pytz.utc)
    tomorrow = datetime.today().astimezone(pytz.utc) + timedelta(days=1)
    end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=pytz.timezone("America/Chicago")).astimezone(pytz.utc)

    # Fetches events from now to midnight tomorrow Chicago time
    events = list(gc.get_events(curr_time, end, order_by="startTime", timezone=pytz.utc, single_events=True))

    # Unless the story is urgent and if no events scheduled, then we fetch events for tomorrow as well (if this is empty, then function returns DEFAULT_EDITOR_EMAIL)
    if len(events) == 0 and not is_urgent:
        events = list(gc.get_events(curr_time, end + timedelta(days=1), order_by="startTime", timezone=pytz.utc, single_events=True))
    
    # Getting editor emails from events, then sorts them based on the last_edited value.
    # TODO: replace defaultdict implementation with Google Cloud user DB for checking last_edited field
    last_edited_list = [(event.attendees[0].email, last_edited_dict[event.attendees[0].email]) for event in events if event.end.replace(tzinfo=pytz.utc) > curr_time + timedelta(minutes=15)] # If statement skips events where the time remaining is less than a given num of minutes (i.e. shift is about to end)
    last_edited_list.sort(key=lambda x: x[1]) 

    # Returns email for the copy editor if list isn't empty, otherwise returns default email (i.e copy chief)
    if len(last_edited_list) > 0:
        email = last_edited_list[0][0]
        last_edited_dict.update({email:curr_time}) # TODO: replace this line with equiv Google Cloud user implementation
        return email
    
    return DEFAULT_EDITOR_EMAIL

def send_copy_edit_slack_msg(content:str, status):
    # To be implemented -- i.e. sending actual slack message
    pass
