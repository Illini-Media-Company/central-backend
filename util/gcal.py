# Functions in this file can be used to fetch upcoming events from a Google Calendar.
# In order to access the events, the calendar must be shared with the email associated
# with the Central Backend's Google Cloud service account. This email is the project's
# ID with @appspot.gserviceaccount.com appended to the end. The project ID can be found
# either through the Google Cloud Console or in the .env file.
#
# Calendar IDs are stored in constants.py

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from gcsa.google_calendar import GoogleCalendar
from util.security import get_creds
from util.helpers.ap_datetime import ap_datetime, ap_date, ap_time

from constants import MAIN_IMC_GCAL_ID

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


# Returns a list of all events on the main IMC Google Calendar occurring in the next 14 days.
def get_allstaff_events():
    creds = get_creds(SCOPES)
    gc = GoogleCalendar(MAIN_IMC_GCAL_ID, credentials=creds)

    events = gc.get_events(
        time_min=datetime.now(tz=ZoneInfo("America/Chicago")),
        time_max=datetime.now(tz=ZoneInfo("America/Chicago")) + timedelta(days=14),
        single_events=True,
        order_by="startTime",
    )

    formatted_events = []
    for event in events:
        # Check if this is an all-day event by seeing if it's a date or a datetime
        if isinstance(event.start, datetime):
            start = ap_datetime(event.start)
            end = ap_datetime(event.end)
        else:
            start = ap_date(event.start) + ", all day"
            end = ap_date(event.end) + ", all day"
        formatted_events.append(
            {
                "title": event.summary,
                "location": event.location.split(",")[0] if event.location else "",
                "start": start,
                "end": end,
                "description": event.description if event.description else "",
            }
        )

    return formatted_events


def get_resource_events_today(resource_calid: str, start_hour: int, end_hour: int):
    """
    Gets all events happening on the current day from start_hour to end_hour

    :param resource_calid: The ID of the Google Calendar to fetch events from
    :type resource_calid: str
    :param start_hour: The integer hour (0-24) to be considered as time=0
    :type start_hour: int
    :param end_hour: The integer hour (0-24) to be considered as time=100
    :type end_hour: int
    :returns: All events, each containing the following:
        \n\t"title" — (str) The name/title of the event.
        \n\t"start" — (str) The start time of the event formatted to AP style.
        \n\t"end" — (str) The end time of the event formatted to AP style.
        \n\t"start_percent" — (int) The time that this event starts as a percentage,
                                where 0% is start_hour and 100% is end_hour.
        \n\t"duration_percent" — (int) The duration of this event as a percentage,
                                where 0% is zero time and 100% is the duration between
                                start_hour and end_hour.
    :rtype: list
    """

    creds = get_creds(SCOPES)
    gc = GoogleCalendar(resource_calid, credentials=creds)

    tz = ZoneInfo("America/Chicago")
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=tz)
    end_of_day = start_of_day + timedelta(days=1)
    day_seconds = (end_of_day - start_of_day).total_seconds()

    events = gc.get_events(
        time_min=start_of_day,
        time_max=end_of_day,
        single_events=True,
        order_by="startTime",
    )

    formatted_events = []
    for event in events:
        start = event.start
        end = event.end

        start_percent = ((start - start_of_day).total_seconds() / day_seconds) * 100
        end_percent = ((end - start_of_day).total_seconds() / day_seconds) * 100

        # Clip the events percentages to be between the start_hour and end_hour
        lower_percent = (start_hour / 24) * 100
        upper_percent = (end_hour / 24) * 100

        def scale_time_percent(percent):
            return max(
                0,
                min(
                    100,
                    (percent - lower_percent) / (upper_percent - lower_percent) * 100,
                ),
            )

        scaled_start = scale_time_percent(start_percent)
        scaled_end = scale_time_percent(end_percent)
        scaled_duration = scaled_end - scaled_start

        formatted_events.append(
            {
                "title": event.summary,
                "start": ap_time(start),
                "end": ap_time(end),
                "start_percent": scaled_start,
                "duration_percent": scaled_duration,
            }
        )

    return formatted_events
