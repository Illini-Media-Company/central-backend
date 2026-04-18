"""
Utility / service functions for the editor's copy scheduler view.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from google.cloud import ndb

from db.copy_schedule import ShiftSlot, SeniorShiftSlot, ShiftRequest, BreakWeek
from db import client
from constants import (
    COPY_EDITOR_GROUPS,
    SENIOR_COPY_EDITOR_GROUPS,
    COPY_CHIEF_GROUPS,
    SHIFT_START_HOURS,
    SHIFT_DURATION,
    SHIFT_REQUIREMENTS,
    WEEKEND_SHIFT_REDUCTION,
    SENIOR_COPY_EDITOR_HOURS,
    BREAK_WEEK_SHIFT_HOURS,
    BREAK_WEEK_SHIFT_DURATION,
    BREAK_WEEK_REQUIREMENTS,
    SCHEDULER_TIMEZONE,
    COPY_SCHEDULE_NOTIFICATIONS_CHANNEL,
)
from util.slackbots.general import dm_user_by_email, dm_channel_by_id

DAYS_OF_WEEK = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]
WEEKEND_DAY_INDICES = {5, 6}


def _notify_channel(msg: str) -> None:
    dm_channel_by_id(COPY_SCHEDULE_NOTIFICATIONS_CHANNEL, msg)


def get_user_role(user) -> str:
    user_groups = set(user.groups)
    if user_groups & set(COPY_CHIEF_GROUPS):
        return "copy_chief"
    if user_groups & set(SENIOR_COPY_EDITOR_GROUPS):
        return "senior_copy_editor"
    return "copy_editor"


def get_slot_class_for_user(user):
    """
    Returns the NDB model class (ShiftSlot or SeniorShiftSlot) appropriate
    for this user's role. Copy chiefs see staff slots by default.
    """
    role = get_user_role(user)
    return SeniorShiftSlot if role == "senior_copy_editor" else ShiftSlot


def get_slot_type_for_user(user) -> str:
    """Returns 'senior' or 'staff' string for ShiftRequest.slot_type."""
    return "senior" if get_user_role(user) == "senior_copy_editor" else "staff"


def is_break_week(reference_date: date = None) -> bool:
    """Returns True if the week containing reference_date is a break week."""
    sunday, _ = get_week_bounds(reference_date)
    try:
        return ndb.Key(BreakWeek, sunday.isoformat()).get() is not None
    except Exception:
        with client.context():
            return ndb.Key(BreakWeek, sunday.isoformat()).get() is not None


def get_week_schedule(reference_date: date = None) -> dict:
    break_week = is_break_week(reference_date)
    return {
        "is_break_week": break_week,
        "hours": BREAK_WEEK_SHIFT_HOURS if break_week else SHIFT_START_HOURS,
        "duration": BREAK_WEEK_SHIFT_DURATION if break_week else SHIFT_DURATION,
    }


def get_all_break_weeks() -> list[str]:
    with client.context():
        entries = BreakWeek.query().fetch()
        return [e.key.id() for e in entries]


def toggle_break_week(week_start_iso: str, admin_email: str = None) -> dict:
    with client.context():
        key = ndb.Key(BreakWeek, week_start_iso)
        existing = key.get()
        if existing:
            key.delete()
            return {"is_break_week": False, "week_start": week_start_iso}
        else:
            entry = BreakWeek(id=week_start_iso, created_by=admin_email)
            entry.put()
            return {"is_break_week": True, "week_start": week_start_iso}


def get_required_shifts(user, reference_date: date = None) -> int:
    role = get_user_role(user)
    if is_break_week(reference_date):
        return BREAK_WEEK_REQUIREMENTS.get(role, 1)
    base = SHIFT_REQUIREMENTS.get(role, 2)
    if (
        role == "copy_editor"
        and base > 0
        and _has_weekend_shift(user.email, reference_date)
    ):
        return max(0, base - WEEKEND_SHIFT_REDUCTION)
    return base


def get_available_hours(user, reference_date: date = None) -> list:
    """
    Returns shift hours this user can sign up for.
    Break weeks override all role restrictions to the 3 break slots.
    Senior editors are restricted to 10am–10pm on regular weeks.
    """
    if is_break_week(reference_date):
        return BREAK_WEEK_SHIFT_HOURS
    role = get_user_role(user)
    if role == "senior_copy_editor":
        return SENIOR_COPY_EDITOR_HOURS
    return SHIFT_START_HOURS


def _has_weekend_shift(editor_id: str, reference_date: date = None) -> bool:
    shifts = get_editor_shifts_for_week(editor_id, reference_date)
    return any(s.date.weekday() in WEEKEND_DAY_INDICES for s in shifts)


def get_week_bounds(reference_date: date = None):
    if reference_date is None:
        reference_date = date.today()
    day_offset = (reference_date.weekday() + 1) % 7
    sunday = reference_date - timedelta(days=day_offset)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


def shift_label(start_hour: int, duration: int = 2) -> str:
    def _fmt(h):
        if h == 0 or h == 24:
            return "12am"
        elif h == 12:
            return "12pm"
        elif h < 12:
            return f"{h}am"
        else:
            return f"{h - 12}pm"

    return f"{_fmt(start_hour)}-{_fmt(start_hour + duration)}"


def day_label(d: date) -> str:
    name = DAYS_OF_WEEK[(d.weekday() + 1) % 7]
    return f"{name} {d.month}/{d.day}"


def format_today() -> str:
    today = date.today()
    day_name = DAYS_OF_WEEK[(today.weekday() + 1) % 7]
    month_name = today.strftime("%B")
    day_num = today.day
    if 11 <= day_num <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
    return f"{day_name}, {month_name} {day_num}{suffix}"


def is_shift_in_past(shift_date: date, start_hour: int) -> bool:
    tz = ZoneInfo(SCHEDULER_TIMEZONE)
    shift_start = datetime(
        shift_date.year, shift_date.month, shift_date.day, start_hour, 0, 0, tzinfo=tz
    )
    return datetime.now(tz) >= shift_start


def _slot_key_name(d: date, start_hour: int) -> str:
    return f"{d.isoformat()}_{start_hour}"


def _shift_duration_for_date(d: date) -> int:
    return 4 if is_break_week(d) else 2


def get_shift(d: date, start_hour: int, slot_class=ShiftSlot) -> ShiftSlot:
    key = ndb.Key(slot_class, _slot_key_name(d, start_hour))
    return key.get()


def get_shifts_for_week(reference_date: date = None, slot_class=ShiftSlot) -> dict:
    """Returns all shift slots for the week using break-week-aware hours."""
    sunday, saturday = get_week_bounds(reference_date)
    schedule = get_week_schedule(reference_date)
    hours = schedule["hours"]
    shifts = {}
    current = sunday
    while current <= saturday:
        for hour in hours:
            key_name = _slot_key_name(current, hour)
            shifts[key_name] = get_shift(current, hour, slot_class)
        current += timedelta(days=1)
    return shifts


def get_droppable_shifts_for_week(
    reference_date: date = None, slot_class=ShiftSlot
) -> set:
    sunday, saturday = get_week_bounds(reference_date)
    slots = slot_class.query(
        slot_class.up_for_drop == True,  # noqa: E712
        slot_class.date >= sunday,
        slot_class.date <= saturday,
    ).fetch()
    return {_slot_key_name(s.date, s.start_hour) for s in slots}


def get_editor_shifts_for_week(
    editor_id: str, reference_date: date = None, slot_class=ShiftSlot
) -> list:
    sunday, saturday = get_week_bounds(reference_date)
    return (
        slot_class.query(
            slot_class.editor_id == editor_id,
            slot_class.date >= sunday,
            slot_class.date <= saturday,
        )
        .order(slot_class.date, slot_class.start_hour)
        .fetch()
    )


def count_editor_shifts_for_week(
    editor_id: str, reference_date: date = None, slot_class=ShiftSlot
) -> int:
    sunday, saturday = get_week_bounds(reference_date)
    return slot_class.query(
        slot_class.editor_id == editor_id,
        slot_class.date >= sunday,
        slot_class.date <= saturday,
    ).count()


def assign_shift(
    d: date, start_hour: int, editor_id: str, editor_name: str, slot_class=ShiftSlot
):
    key_name = _slot_key_name(d, start_hour)
    slot = ndb.Key(slot_class, key_name).get()
    if slot is None:
        slot = slot_class(id=key_name, date=d, start_hour=start_hour)
    slot.editor_id = editor_id
    slot.editor_name = editor_name
    slot.up_for_drop = False
    slot.put()
    return slot


def clear_shift(d: date, start_hour: int, slot_class=ShiftSlot) -> None:
    slot = get_shift(d, start_hour, slot_class)
    if slot:
        slot.editor_id = None
        slot.editor_name = None
        slot.up_for_drop = False
        slot.put()


def mark_up_for_drop(d: date, start_hour: int, slot_class=ShiftSlot) -> None:
    slot = get_shift(d, start_hour, slot_class)
    if slot:
        slot.up_for_drop = True
        slot.put()


def get_pending_requests_for_editor(
    editor_id: str, reference_date: date = None, slot_type: str = "staff"
) -> list:
    sunday, saturday = get_week_bounds(reference_date)
    return ShiftRequest.query(
        ShiftRequest.requester_id == editor_id,
        ShiftRequest.slot_type == slot_type,
        ShiftRequest.status == "pending",
        ShiftRequest.source_shift_date >= sunday,
        ShiftRequest.source_shift_date <= saturday,
    ).fetch()


def build_pending_map(
    editor_id: str, reference_date: date = None, slot_type: str = "staff"
) -> dict:
    requests = get_pending_requests_for_editor(editor_id, reference_date, slot_type)
    pending = {}
    for req in requests:
        key = _slot_key_name(req.source_shift_date, req.source_shift_hour)
        if req.target_shift_date:
            target_dur = _shift_duration_for_date(req.target_shift_date)
            req.target_label = f"{day_label(req.target_shift_date)} {shift_label(req.target_shift_hour, target_dur)}"
        else:
            req.target_label = ""
        pending[key] = req
    return pending


def build_swap_requested_set(
    reference_date: date = None, slot_type: str = "staff"
) -> set:
    sunday, saturday = get_week_bounds(reference_date)
    reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.slot_type == slot_type,
        ShiftRequest.target_shift_date >= sunday,
        ShiftRequest.target_shift_date <= saturday,
    ).fetch(projection=[ShiftRequest.target_shift_date, ShiftRequest.target_shift_hour])
    return {
        _slot_key_name(r.target_shift_date, r.target_shift_hour)
        for r in reqs
        if r.target_shift_date and r.target_shift_hour is not None
    }


def get_incoming_requests_for_editor(
    editor_id: str, reference_date: date = None, slot_type: str = "staff"
) -> list:
    sunday, saturday = get_week_bounds(reference_date)
    return ShiftRequest.query(
        ShiftRequest.target_editor_id == editor_id,
        ShiftRequest.slot_type == slot_type,
        ShiftRequest.status == "pending",
        ShiftRequest.target_shift_date >= sunday,
        ShiftRequest.target_shift_date <= saturday,
    ).fetch()


def build_incoming_map(
    editor_id: str, reference_date: date = None, slot_type: str = "staff"
) -> list:
    requests = get_incoming_requests_for_editor(editor_id, reference_date, slot_type)
    incoming = []
    for req in requests:
        src_dur = _shift_duration_for_date(req.source_shift_date)
        tgt_dur = (
            _shift_duration_for_date(req.target_shift_date)
            if req.target_shift_date
            else 2
        )
        incoming.append(
            {
                "uid": req.key.id(),
                "request_type": req.request_type,
                "requester_name": req.requester_name,
                "requester_id": req.requester_id,
                "source_label": f"{day_label(req.source_shift_date)} {shift_label(req.source_shift_hour, src_dur)}",
                "target_label": f"{day_label(req.target_shift_date)} {shift_label(req.target_shift_hour, tgt_dur)}",
                "source_shift_date": req.source_shift_date.isoformat(),
                "source_shift_hour": req.source_shift_hour,
                "target_shift_date": req.target_shift_date.isoformat(),
                "target_shift_hour": req.target_shift_hour,
            }
        )
    return incoming


def request_drop(user, shift_date: date, shift_hour: int) -> dict:
    if is_shift_in_past(shift_date, shift_hour):
        return {"error": "Cannot drop a shift that has already started."}

    sc = get_slot_class_for_user(user)
    st = get_slot_type_for_user(user)
    mark_up_for_drop(shift_date, shift_hour, sc)

    req = ShiftRequest(
        request_type="drop",
        slot_type=st,
        requester_id=user.email,
        requester_name=user.name,
        source_shift_date=shift_date,
        source_shift_hour=shift_hour,
        approver_type="copy_chief",
    )
    req.put()
    send_drop_approval_to_slack(req)
    _schedule_unclaimed_drop_reminder(shift_date, shift_hour, req.key.id())
    return {"request_id": req.key.id(), "up_for_drop": True}


def _schedule_unclaimed_drop_reminder(
    shift_date: date, shift_hour: int, request_id: int
) -> None:
    try:
        from util.apscheduler import scheduler
        from apscheduler.triggers.date import DateTrigger

        tz = ZoneInfo(SCHEDULER_TIMEZONE)
        shift_start = datetime(
            shift_date.year,
            shift_date.month,
            shift_date.day,
            shift_hour,
            0,
            0,
            tzinfo=tz,
        )
        reminder_time = shift_start - timedelta(hours=2)
        now = datetime.now(tz)
        if reminder_time <= now:
            reminder_time = now + timedelta(seconds=5)

        scheduler.add_job(
            func=_unclaimed_drop_reminder_job,
            trigger=DateTrigger(run_date=reminder_time),
            args=[shift_date.isoformat(), shift_hour, request_id],
            id=f"drop_reminder_{shift_date.isoformat()}_{shift_hour}",
            replace_existing=True,
        )
    except Exception:
        pass


def _unclaimed_drop_reminder_job(
    shift_date_iso: str, shift_hour: int, request_id: int
) -> None:
    with client.context():
        shift_date = date.fromisoformat(shift_date_iso)
        req = ShiftRequest.get_by_id(request_id)
        if not req or req.status != "pending":
            return
        sc = (
            SeniorShiftSlot
            if getattr(req, "slot_type", "staff") == "senior"
            else ShiftSlot
        )
        slot = get_shift(shift_date, shift_hour, sc)
        if not slot or not slot.up_for_drop:
            return
        _notify_channel(
            f"⚠️ *Unclaimed Drop — Action Needed*\n"
            f"{req.requester_name}'s shift on "
            f"{day_label(shift_date)} {shift_label(shift_hour, _shift_duration_for_date(shift_date))} "
            f"starts in 2 hours and has not been picked up.\n"
            f"Please approve or deny the drop request in the admin dashboard."
        )


def _cancel_drop_reminder_job(shift_date: date, shift_hour: int) -> None:
    try:
        from util.apscheduler import scheduler

        job_id = f"drop_reminder_{shift_date.isoformat()}_{shift_hour}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception:
        pass


def pickup_shift(user, shift_date: date, shift_hour: int) -> dict:
    if is_shift_in_past(shift_date, shift_hour):
        return {"error": "Cannot pick up a shift that has already started."}

    sc = get_slot_class_for_user(user)
    st = get_slot_type_for_user(user)
    slot = get_shift(shift_date, shift_hour, sc)

    if not slot or not slot.editor_id:
        return {"error": "This shift is not currently assigned to anyone."}
    if not slot.up_for_drop:
        return {"error": "This shift is not available for pickup."}

    old_editor_id = slot.editor_id
    old_editor_name = slot.editor_name
    assign_shift(shift_date, shift_hour, user.email, user.name, sc)
    _cancel_drop_requests_for_shift(old_editor_id, shift_date, shift_hour, st)
    _cancel_drop_reminder_job(shift_date, shift_hour)

    req = ShiftRequest(
        request_type="pickup",
        status="approved",
        slot_type=st,
        requester_id=user.email,
        requester_name=user.name,
        source_shift_date=shift_date,
        source_shift_hour=shift_hour,
        target_editor_id=old_editor_id,
        target_editor_name=old_editor_name,
        approver_type="none",
        resolved_at=datetime.utcnow(),
    )
    req.put()
    notify_slack_shift_picked_up(req, old_editor_name)
    return {"success": True}


def _cancel_drop_requests_for_shift(
    editor_id: str, shift_date: date, shift_hour: int, slot_type: str = "staff"
):
    reqs = ShiftRequest.query(
        ShiftRequest.requester_id == editor_id,
        ShiftRequest.request_type == "drop",
        ShiftRequest.slot_type == slot_type,
        ShiftRequest.status == "pending",
        ShiftRequest.source_shift_date == shift_date,
        ShiftRequest.source_shift_hour == shift_hour,
    ).fetch()
    for r in reqs:
        r.status = "cancelled"
        r.resolved_at = datetime.utcnow()
    if reqs:
        ndb.put_multi(reqs)


def add_slot(user, shift_date: date, shift_hour: int) -> dict:
    sc = get_slot_class_for_user(user)
    slot = get_shift(shift_date, shift_hour, sc)
    if slot and slot.editor_id is not None:
        return {"success": False, "reason": "Slot is already occupied."}
    assign_shift(shift_date, shift_hour, user.email, user.name, sc)
    return {"success": True}


def request_swap(
    user,
    source_date: date,
    source_hour: int,
    target_date: date,
    target_hour: int,
    swap_mode: str,
) -> dict:
    if is_shift_in_past(source_date, source_hour):
        return {"error": "Cannot swap a shift that has already started."}

    sc = get_slot_class_for_user(user)
    st = get_slot_type_for_user(user)
    target_slot = get_shift(target_date, target_hour, sc)
    target_editor_id = target_slot.editor_id if target_slot else None
    target_editor_name = target_slot.editor_name if target_slot else None

    if swap_mode == "direct":
        if target_editor_id is None:
            return {"error": "Cannot direct swap with an empty slot."}
        req = ShiftRequest(
            request_type="swap_direct",
            slot_type=st,
            requester_id=user.email,
            requester_name=user.name,
            source_shift_date=source_date,
            source_shift_hour=source_hour,
            target_shift_date=target_date,
            target_shift_hour=target_hour,
            target_editor_id=target_editor_id,
            target_editor_name=target_editor_name,
            approver_type="editor",
            approver_id=target_editor_id,
        )
        req.put()
        send_direct_swap_to_slack(req)
        return {"request_id": req.key.id()}

    elif swap_mode == "swap_drop":
        if target_editor_id is None:
            return {"error": "Cannot swap-drop with an empty slot."}
        req = ShiftRequest(
            request_type="swap_drop",
            slot_type=st,
            requester_id=user.email,
            requester_name=user.name,
            source_shift_date=source_date,
            source_shift_hour=source_hour,
            target_shift_date=target_date,
            target_shift_hour=target_hour,
            target_editor_id=target_editor_id,
            target_editor_name=target_editor_name,
            approver_type="editor",
            approver_id=target_editor_id,
        )
        req.put()
        send_swap_drop_to_slack(req)
        return {"request_id": req.key.id()}

    else:  # add_into
        request_type = "swap_add" if target_editor_id else "swap_empty"
        req = ShiftRequest(
            request_type=request_type,
            slot_type=st,
            requester_id=user.email,
            requester_name=user.name,
            source_shift_date=source_date,
            source_shift_hour=source_hour,
            target_shift_date=target_date,
            target_shift_hour=target_hour,
            target_editor_id=target_editor_id,
            target_editor_name=target_editor_name,
            approver_type="copy_chief",
        )
        req.put()
        send_swap_approval_to_slack(req)
        if target_editor_id:
            notify_slack_swap_involves_your_shift(req, target_editor_name)
        return {"request_id": req.key.id()}


def cancel_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    sc = (
        SeniorShiftSlot if getattr(req, "slot_type", "staff") == "senior" else ShiftSlot
    )
    if req.request_type == "drop":
        slot = get_shift(req.source_shift_date, req.source_shift_hour, sc)
        if slot:
            slot.up_for_drop = False
            slot.put()
        _cancel_drop_reminder_job(req.source_shift_date, req.source_shift_hour)

    req.status = "cancelled"
    req.resolved_at = datetime.utcnow()
    req.put()
    notify_slack_cancelled(req)
    return {"success": True}


def approve_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    sc = (
        SeniorShiftSlot if getattr(req, "slot_type", "staff") == "senior" else ShiftSlot
    )
    req.status = "approved"
    req.resolved_at = datetime.utcnow()

    if req.request_type == "drop":
        clear_shift(req.source_shift_date, req.source_shift_hour, sc)
        _cancel_drop_reminder_job(req.source_shift_date, req.source_shift_hour)

    elif req.request_type in ("swap_direct", "swap_drop"):
        source = get_shift(req.source_shift_date, req.source_shift_hour, sc)
        target = get_shift(req.target_shift_date, req.target_shift_hour, sc)
        a_id, a_name = source.editor_id, source.editor_name
        b_id, b_name = target.editor_id, target.editor_name
        source.editor_id, source.editor_name = b_id, b_name
        target.editor_id, target.editor_name = a_id, a_name
        source.up_for_drop = False
        target.up_for_drop = False
        ndb.put_multi([source, target])
        if req.request_type == "swap_drop":
            _cancel_drop_requests_for_shift(
                req.target_editor_id,
                req.target_shift_date,
                req.target_shift_hour,
                req.slot_type,
            )
            _cancel_drop_reminder_job(req.target_shift_date, req.target_shift_hour)

    elif req.request_type in ("swap_add", "swap_empty"):
        clear_shift(req.source_shift_date, req.source_shift_hour, sc)
        target_slot = get_shift(req.target_shift_date, req.target_shift_hour, sc)
        if req.request_type == "swap_add" and target_slot and target_slot.editor_id:
            target_slot.editor_id_2 = req.requester_id
            target_slot.editor_name_2 = req.requester_name
            target_slot.up_for_drop = False
            target_slot.put()
        else:
            assign_shift(
                req.target_shift_date,
                req.target_shift_hour,
                req.requester_id,
                req.requester_name,
                sc,
            )

    req.put()
    notify_slack_approved(req)
    return {"success": True}


def deny_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    sc = (
        SeniorShiftSlot if getattr(req, "slot_type", "staff") == "senior" else ShiftSlot
    )
    if req.request_type == "drop":
        slot = get_shift(req.source_shift_date, req.source_shift_hour, sc)
        if slot:
            slot.up_for_drop = False
            slot.put()
        _cancel_drop_reminder_job(req.source_shift_date, req.source_shift_hour)

    req.status = "denied"
    req.resolved_at = datetime.utcnow()
    req.put()
    notify_slack_denied(req)
    return {"success": True}


def _source_label(req: ShiftRequest) -> str:
    dur = _shift_duration_for_date(req.source_shift_date)
    return (
        f"{day_label(req.source_shift_date)} {shift_label(req.source_shift_hour, dur)}"
    )


def _target_label(req: ShiftRequest) -> str:
    if req.target_shift_date and req.target_shift_hour is not None:
        dur = _shift_duration_for_date(req.target_shift_date)
        return f"{day_label(req.target_shift_date)} {shift_label(req.target_shift_hour, dur)}"
    return "—"


def _slot_type_label(req: ShiftRequest) -> str:
    return "Senior" if getattr(req, "slot_type", "staff") == "senior" else "Staff"


def send_drop_approval_to_slack(request: ShiftRequest) -> None:
    _notify_channel(
        f"📋 *Drop Request ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} has requested to drop their shift on {_source_label(request)}.\n"
        f"The shift is now marked as 'up for drop' so another editor can pick it up. "
        f"If no one does, copy chief approval is needed to remove it entirely.\n"
        f"👉 Review in the admin dashboard."
    )


def send_direct_swap_to_slack(request: ShiftRequest) -> None:
    _notify_channel(
        f"🔄 *Direct Swap Request ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} has requested to swap shifts with {request.target_editor_name}.\n"
        f"  • {request.requester_name}'s shift: {_source_label(request)}\n"
        f"  • {request.target_editor_name}'s shift: {_target_label(request)}\n"
        f"This requires {request.target_editor_name}'s approval via the shift dashboard."
    )
    if request.target_editor_id:
        dm_user_by_email(
            request.target_editor_id,
            f"🔄 *Swap Request — Action Needed*\n"
            f"{request.requester_name} has requested to swap shifts with you.\n"
            f"  • Their shift: {_source_label(request)}\n"
            f"  • Your shift: {_target_label(request)}\n"
            f"👉 Check the shift dashboard to approve or deny.",
        )


def send_swap_drop_to_slack(request: ShiftRequest) -> None:
    _notify_channel(
        f"🔄 *Swap-Drop Request ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} wants to swap with {request.target_editor_name}, "
        f"who has their shift up for drop.\n"
        f"  • {request.requester_name}'s shift: {_source_label(request)}\n"
        f"  • {request.target_editor_name}'s shift: {_target_label(request)}\n"
        f"Requires {request.target_editor_name}'s approval."
    )
    if request.target_editor_id:
        dm_user_by_email(
            request.target_editor_id,
            f"🔄 *Swap Offer — Action Needed*\n"
            f"{request.requester_name} is offering to swap shifts with you instead of you dropping yours.\n"
            f"  • Your shift: {_target_label(request)}\n"
            f"  • Their shift: {_source_label(request)}\n"
            f"👉 Check the shift dashboard to approve or deny.",
        )


def send_swap_approval_to_slack(request: ShiftRequest) -> None:
    target_desc = (
        f"a slot occupied by {request.target_editor_name}"
        if request.request_type == "swap_add" and request.target_editor_name
        else "an empty slot"
    )
    _notify_channel(
        f"📋 *Swap Request — Copy Chief Approval Needed ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} wants to move from {_source_label(request)} "
        f"into {target_desc} ({_target_label(request)}).\n"
        f"Their current shift would be dropped once approved.\n"
        f"👉 Review and approve or deny in the admin dashboard."
    )


def notify_slack_swap_involves_your_shift(
    request: ShiftRequest, target_editor_name: str
) -> None:
    if request.target_editor_id:
        dm_user_by_email(
            request.target_editor_id,
            f"ℹ️ *Heads Up — Your Shift Is Involved in a Swap Request*\n"
            f"{request.requester_name} has requested to join your shift on {_target_label(request)}.\n"
            f"This is pending copy chief approval. You'll be notified of the outcome.",
        )


def notify_slack_shift_picked_up(request: ShiftRequest, old_editor_name: str) -> None:
    _notify_channel(
        f"✅ *Shift Picked Up ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} has picked up {old_editor_name}'s shift on "
        f"{_source_label(request)}. No further action needed."
    )
    if request.target_editor_id:
        dm_user_by_email(
            request.target_editor_id,
            f"✅ *Your Shift Has Been Picked Up*\n"
            f"{request.requester_name} has taken over your shift on {_source_label(request)}. "
            f"You're all set — no further action needed.",
        )


def notify_slack_cancelled(request: ShiftRequest) -> None:
    _notify_channel(
        f"❌ *Request Cancelled ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name} has cancelled their "
        f"{request.request_type.replace('_', ' ')} request for {_source_label(request)}. "
        f"No further action needed."
    )


def notify_slack_approved(request: ShiftRequest) -> None:
    if (
        request.request_type in ("swap_direct", "swap_drop")
        and request.target_editor_name
    ):
        requester_msg = (
            f"✅ *Your Swap Request Was Accepted*\n"
            f"{request.target_editor_name} has accepted your swap request.\n"
            f"  • Your new shift: {_target_label(request)}\n"
            f"  • {request.target_editor_name}'s new shift: {_source_label(request)}\n"
            f"👉 Check the shift dashboard to see your updated schedule."
        )
    elif request.request_type == "swap_add":
        requester_msg = (
            f"✅ *Your Swap Request Was Approved*\n"
            f"The copy chief has approved your request to move into the {_target_label(request)} slot.\n"
            f"Your previous shift ({_source_label(request)}) has been cleared.\n"
            f"👉 Check the shift dashboard to see your updated schedule."
        )
        if request.target_editor_id:
            dm_user_by_email(
                request.target_editor_id,
                f"ℹ️ *Update on Your Shift*\n"
                f"The copy chief has approved {request.requester_name} joining your shift on {_target_label(request)}.",
            )
    elif request.request_type == "swap_empty":
        requester_msg = (
            f"✅ *Your Swap Request Was Approved*\n"
            f"The copy chief has approved your move from {_source_label(request)} to {_target_label(request)}.\n"
            f"👉 Check the shift dashboard to see your updated schedule."
        )
    elif request.request_type == "drop":
        requester_msg = (
            f"✅ *Your Drop Request Was Approved*\n"
            f"The copy chief has approved dropping your shift on {_source_label(request)}. You're all set."
        )
    else:
        requester_msg = (
            f"✅ *Your Request Was Approved*\n"
            f"Your {request.request_type.replace('_', ' ')} request for {_source_label(request)} has been approved.\n"
            f"👉 Check the shift dashboard to see your updated schedule."
        )
    dm_user_by_email(request.requester_id, requester_msg)
    _notify_channel(
        f"✅ *Request Approved ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name}'s {request.request_type.replace('_', ' ')} "
        f"request for {_source_label(request)} has been approved."
    )


def notify_slack_denied(request: ShiftRequest) -> None:
    if (
        request.request_type in ("swap_direct", "swap_drop")
        and request.target_editor_name
    ):
        requester_msg = (
            f"❌ *Your Swap Request Was Declined*\n"
            f"{request.target_editor_name} has declined your swap request for "
            f"{_source_label(request)} ↔ {_target_label(request)}.\n"
            f"Your current schedule is unchanged."
        )
    elif request.request_type in ("swap_add", "swap_empty"):
        requester_msg = (
            f"❌ *Your Swap Request Was Denied*\n"
            f"The copy chief has denied your request to move from {_source_label(request)} to {_target_label(request)}.\n"
            f"Your current schedule is unchanged."
        )
        if request.request_type == "swap_add" and request.target_editor_id:
            dm_user_by_email(
                request.target_editor_id,
                f"ℹ️ *Update on Your Shift*\n"
                f"The copy chief has denied {request.requester_name}'s request to join your shift on {_target_label(request)}. "
                f"No changes have been made to your schedule.",
            )
    elif request.request_type == "drop":
        requester_msg = (
            f"❌ *Your Drop Request Was Denied*\n"
            f"The copy chief has denied your request to drop your shift on {_source_label(request)}.\n"
            f"Your shift is still assigned to you and is no longer marked as up for drop."
        )
    else:
        requester_msg = (
            f"❌ *Your Request Was Denied*\n"
            f"Your {request.request_type.replace('_', ' ')} request for {_source_label(request)} has been denied.\n"
            f"Your current schedule is unchanged."
        )
    dm_user_by_email(request.requester_id, requester_msg)
    _notify_channel(
        f"❌ *Request Denied ({_slot_type_label(request)} Copy)*\n"
        f"{request.requester_name}'s {request.request_type.replace('_', ' ')} "
        f"request for {_source_label(request)} has been denied."
    )
