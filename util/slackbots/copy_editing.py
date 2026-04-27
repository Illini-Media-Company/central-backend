"""
copy_editing_slackbot.py

Tags copy editors for incoming stories via Slack.

Priority (new schedule path):
  1. Staff copy editor in current ShiftSlot
  2. Senior copy editor in current SeniorShiftSlot (if staff slot empty)
  3. Copy chief (if both empty)

Feature flag: COPY_BOT_USE_SHIFT_SCHEDULE in KV store.
  "1" = use shift schedule   (flip when copy team has migrated)
  "0" = use Google Calendar  (default until migration complete)
"""

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, date

from constants import COPY_EDITING_GCAL_ID, SLACK_BOT_TOKEN, ENV
from db.kv_store import kv_store_get, kv_store_set
from db.user import add_user, get_user, update_user_last_edited
from db import client as dbclient
from db.copy_schedule import ShiftSlot, SeniorShiftSlot
from util.security import get_creds
from util.slackbots._slackbot import app
from util.copy_schedule import SHIFT_START_HOURS, _slot_key_name
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.background import BackgroundScheduler
import random
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
SHIFT_OFFSET = timedelta(minutes=15)
BREAKING_SHIFTS = [1, 2, 3, 4, 5, 6, 7]
CONTENT_DOC_SHIFTS = [1, 2, 3, 4, 5, 6, 7]
DI_COPY_TAG_CHANNEL_ID = "C02EZ0QE9CM" if ENV == "prod" else "C07T8TAATDF"
DI_SCHED_CHANNEL_ID = "C089U20NDGB"


def _use_shift_schedule() -> bool:
    return str(kv_store_get("COPY_BOT_USE_SHIFT_SCHEDULE")) == "1"


def _get_current_shift_hour(current_time: datetime) -> int | None:
    """Returns the start hour of the active shift slot, respecting SHIFT_OFFSET."""
    current_with_offset = current_time + SHIFT_OFFSET
    for hour in SHIFT_START_HOURS:
        slot_start = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        slot_end = slot_start + timedelta(hours=2)
        if slot_start <= current_with_offset <= slot_end:
            return hour
    return None


def _pick_least_recently_edited(emails: list[str], now: datetime) -> str | None:
    """Return the editor from the list who last edited least recently."""
    best = None
    best_user = None
    for email in emails:
        user = get_user(email)
        if user is None:
            user = add_user(sub=None, name=email, email=email)
        if user.last_edited is None:
            best = email
            best_user = user
            break
        elif best_user is None or user.last_edited < best_user.last_edited:
            best = email
            best_user = user
    if best_user:
        update_user_last_edited(best_user.email, now)
    return best


def _get_editor_from_shift_schedule(current_time: datetime):
    """
    New path. Returns (editor_email | None, on_shift: bool).

    Priority:
      1. Staff copy editor in ShiftSlot for current hour
      2. Senior copy editor in SeniorShiftSlot for current hour
      3. None → caller falls back to copy chief
    """
    tz = ZoneInfo("America/Chicago")
    now = current_time.astimezone(tz)

    if now.hour < 8:
        return None, False  # signal to delay until 8am

    shift_hour = _get_current_shift_hour(now)
    if shift_hour is None:
        logger.info("No active shift slot at this time.")
        return None, True

    today = now.date()
    slot_key = _slot_key_name(today, shift_hour)

    with dbclient.context():
        staff_slot = ShiftSlot.get_by_id(slot_key)
        senior_slot = SeniorShiftSlot.get_by_id(slot_key)

    # Priority 1: staff copy
    if staff_slot:
        staff_candidates = [
            e for e in [staff_slot.editor_id, staff_slot.editor_id_2] if e
        ]
        if staff_candidates:
            email = _pick_least_recently_edited(staff_candidates, now)
            logger.info(f"Assigning staff copy editor: {email}")
            return email, True

    # Priority 2: senior copy
    if senior_slot:
        senior_candidates = [
            e for e in [senior_slot.editor_id, senior_slot.editor_id_2] if e
        ]
        if senior_candidates:
            email = _pick_least_recently_edited(senior_candidates, now)
            logger.info(f"Staff slot empty. Assigning senior copy editor: {email}")
            return email, True

    logger.info(f"Both staff and senior slots empty for {slot_key}.")
    return None, True


def _get_editor_from_calendar(story_url: str, is_breaking: bool):
    from gcsa.google_calendar import GoogleCalendar

    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)

    current_time = datetime.now(tz=ZoneInfo("America/Chicago"))

    if current_time.hour < 8 and current_time.hour > 0:
        trigger = DateTrigger(
            current_time.replace(
                hour=8, minute=0, second=0 + random.randint(0, 5), microsecond=0
            )
        )
        scheduler.add_job(
            lambda: notify_copy_editor(story_url, is_breaking), trigger=trigger
        )
        logger.info("Outside shift hours (calendar). Delayed to 8am.")
        return None, False

    current_time_offset = current_time + SHIFT_OFFSET
    today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    shifts = gc.get_events(today, tomorrow, single_events=True, order_by="startTime")

    current_shift = None
    for i, shift in enumerate(shifts):
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
            if user.last_edited is None:
                editor = user
                break
            elif editor is None or user.last_edited < editor.last_edited:
                editor = user

    if editor:
        update_user_last_edited(editor.email, current_time)
        return editor, True
    return None, True


def get_copy_editor(story_url: str, is_breaking: bool):
    """
    Returns (editor_user | None, on_shift: bool).
    Routes to schedule or calendar path based on the feature flag.
    """
    if _use_shift_schedule():
        current_time = datetime.now(tz=ZoneInfo("America/Chicago"))

        if current_time.hour < 8:
            trigger = DateTrigger(
                current_time.replace(
                    hour=8, minute=0, second=0 + random.randint(0, 5), microsecond=0
                )
            )
            scheduler.add_job(
                lambda: notify_copy_editor(story_url, is_breaking), trigger=trigger
            )
            logger.info("Outside shift hours (schedule). Delayed to 8am.")
            return None, False

        editor_email, on_shift = _get_editor_from_shift_schedule(current_time)
        if editor_email:
            return get_user(editor_email), on_shift
        return None, on_shift

    else:
        return _get_editor_from_calendar(story_url, is_breaking)


def notify_copy_editor(
    story_url: str, is_breaking: bool, copy_chief_email: str = None, call: bool = False
):
    logger.info(
        f"notify_copy_editor: url={story_url}, breaking={is_breaking}, chief={copy_chief_email}"
    )

    if app is None:
        raise ValueError("Slack app cannot be None!")

    if copy_chief_email is None:
        copy_chief_email = kv_store_get("COPY_CHIEF_EMAIL")
    else:
        kv_store_set("COPY_CHIEF_EMAIL", copy_chief_email)

    editor, on_shift = get_copy_editor(story_url, is_breaking)
    if not on_shift:
        logger.info("Not on shift — waiting.")
        return "waiting"

    email = editor.email if editor else copy_chief_email
    logger.info(f"Tagging: {email}")

    slack_id = app.client.users_lookupByEmail(email=email)["user"]["id"]
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        channel=DI_COPY_TAG_CHANNEL_ID,
        text=f"<@{slack_id}> A new story is ready to be copy edited.\n {story_url}",
    )
    logger.info(f"Slack message sent to {email}.")


def add_copy_editor(editor_email, day_of_week, shift_num):
    from gcsa.google_calendar import GoogleCalendar

    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)
    shift_starts = ["8:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    try:
        shift_num = int(shift_num)
        day_of_week = int(day_of_week)
    except ValueError:
        return
    if not 0 <= shift_num < len(shift_starts):
        return
    today = datetime.now().date()
    next_dow = today + timedelta(days=(day_of_week - today.weekday()) % 7)
    event = gc.get_events(
        time_min=datetime.now().date(),
        single_events=True,
        timezone="America/Chicago",
        order_by="startTime",
    )
    for e in list(event):
        if (
            e.start.strftime("%H:%M") == shift_starts[shift_num]
            and (e.start.date() - next_dow).days % 7 == 0
        ):
            sample_event = e
            break
    for e in list(gc.get_instances(sample_event.recurring_event_id)):
        if editor_email in e.attendees:
            continue
        e.add_attendee(editor_email)
        gc.update_event(e)


def remove_copy_editor(editor_email, day_of_week, shift_num):
    from gcsa.google_calendar import GoogleCalendar

    creds = get_creds(SCOPES)
    gc = GoogleCalendar(COPY_EDITING_GCAL_ID, credentials=creds)
    shift_starts = ["8:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    try:
        shift_num = int(shift_num)
        day_of_week = int(day_of_week)
    except ValueError:
        return
    if not 0 <= shift_num < len(shift_starts):
        return
    today = datetime.now().date()
    next_dow = today + timedelta(days=(day_of_week - today.weekday()) % 7)
    event = gc.get_events(
        time_min=datetime.now().date(),
        single_events=True,
        timezone="America/Chicago",
        order_by="startTime",
    )
    r_id = None
    for e in list(event):
        if (
            e.start.strftime("%H:%M") == shift_starts[shift_num]
            and (e.start.date() - next_dow).days % 7 == 0
        ):
            r_id = e.recurring_event_id
            break
    if r_id is None:
        return
    for e in list(gc.get_instances(r_id)):
        l = e.attendees
        try:
            l.remove(editor_email)
            e.attendees = l
        except ValueError:
            return "Not yet in attendee's list.", 401


def test():
    present = datetime.now(tz=ZoneInfo("America/Chicago"))
    post_time = present + timedelta(minutes=2)
    scheduler.add_job(trigger=DateTrigger(post_time), func=post_test_message)


def post_test_message():
    app.client.chat_postMessage(
        token=SLACK_BOT_TOKEN,
        channel=DI_SCHED_CHANNEL_ID,
        text="Scheduling test testing",
    )
