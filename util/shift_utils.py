"""
shift_utils.py
Utility / service functions for the shift scheduler.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from google.cloud import ndb

from db.shift_schedule import ShiftSlot, ShiftRequest
from constants import (
    COPY_EDITOR_GROUPS,
    SENIOR_COPY_EDITOR_GROUPS,
    COPY_CHIEF_GROUPS,
    SHIFT_REQUIREMENTS,
    WEEKEND_SHIFT_REDUCTION,
    SCHEDULER_TIMEZONE,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHIFT_START_HOURS = [8, 10, 12, 14, 16, 18, 20, 22]
DAYS_OF_WEEK = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]
WEEKEND_DAY_INDICES = {5, 6}  # Saturday=5, Sunday=6 in Python weekday()


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------


def get_user_role(user) -> str:
    user_groups = set(user.groups)
    if user_groups & set(COPY_CHIEF_GROUPS):
        return "copy_chief"
    if user_groups & set(SENIOR_COPY_EDITOR_GROUPS):
        return "senior_copy_editor"
    return "copy_editor"


def get_required_shifts(user, reference_date: date = None) -> int:
    role = get_user_role(user)
    base = SHIFT_REQUIREMENTS.get(role, 2)
    if base > 0 and _has_weekend_shift(user.email, reference_date):
        return max(0, base - WEEKEND_SHIFT_REDUCTION)
    return base


def _has_weekend_shift(editor_id: str, reference_date: date = None) -> bool:
    shifts = get_editor_shifts_for_week(editor_id, reference_date)
    return any(s.date.weekday() in WEEKEND_DAY_INDICES for s in shifts)


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------


def get_week_bounds(reference_date: date = None):
    if reference_date is None:
        reference_date = date.today()
    day_offset = (reference_date.weekday() + 1) % 7
    sunday = reference_date - timedelta(days=day_offset)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


def shift_label(start_hour: int) -> str:
    def _fmt(h):
        if h == 0 or h == 24:
            return "12am"
        elif h == 12:
            return "12pm"
        elif h < 12:
            return f"{h}am"
        else:
            return f"{h - 12}pm"

    return f"{_fmt(start_hour)}-{_fmt(start_hour + 2)}"


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
        shift_date.year,
        shift_date.month,
        shift_date.day,
        start_hour,
        0,
        0,
        tzinfo=tz,
    )
    return datetime.now(tz) >= shift_start


# ---------------------------------------------------------------------------
# Shift key helper
# ---------------------------------------------------------------------------


def _slot_key_name(d: date, start_hour: int) -> str:
    return f"{d.isoformat()}_{start_hour}"


# ---------------------------------------------------------------------------
# Shift queries
# ---------------------------------------------------------------------------


def get_shift(d: date, start_hour: int) -> ShiftSlot:
    key = ndb.Key(ShiftSlot, _slot_key_name(d, start_hour))
    return key.get()


def get_shifts_for_week(reference_date: date = None) -> dict:
    sunday, saturday = get_week_bounds(reference_date)
    shifts = {}
    current = sunday
    while current <= saturday:
        for hour in SHIFT_START_HOURS:
            key_name = _slot_key_name(current, hour)
            shift = get_shift(current, hour)
            shifts[key_name] = shift
        current += timedelta(days=1)
    return shifts


def get_droppable_shifts_for_week(reference_date: date = None) -> set:
    sunday, saturday = get_week_bounds(reference_date)
    slots = ShiftSlot.query(
        ShiftSlot.up_for_drop == True,  # noqa: E712
        ShiftSlot.date >= sunday,
        ShiftSlot.date <= saturday,
    ).fetch()
    return {_slot_key_name(s.date, s.start_hour) for s in slots}


def get_editor_shifts_for_week(editor_id: str, reference_date: date = None) -> list:
    sunday, saturday = get_week_bounds(reference_date)
    return (
        ShiftSlot.query(
            ShiftSlot.editor_id == editor_id,
            ShiftSlot.date >= sunday,
            ShiftSlot.date <= saturday,
        )
        .order(ShiftSlot.date, ShiftSlot.start_hour)
        .fetch()
    )


def count_editor_shifts_for_week(editor_id: str, reference_date: date = None) -> int:
    sunday, saturday = get_week_bounds(reference_date)
    return ShiftSlot.query(
        ShiftSlot.editor_id == editor_id,
        ShiftSlot.date >= sunday,
        ShiftSlot.date <= saturday,
    ).count()


def assign_shift(
    d: date, start_hour: int, editor_id: str, editor_name: str
) -> ShiftSlot:
    key_name = _slot_key_name(d, start_hour)
    slot = ndb.Key(ShiftSlot, key_name).get()
    if slot is None:
        slot = ShiftSlot(id=key_name, date=d, start_hour=start_hour)
    slot.editor_id = editor_id
    slot.editor_name = editor_name
    slot.up_for_drop = False
    slot.put()
    return slot


def clear_shift(d: date, start_hour: int) -> None:
    slot = get_shift(d, start_hour)
    if slot:
        slot.editor_id = None
        slot.editor_name = None
        slot.up_for_drop = False
        slot.put()


def mark_up_for_drop(d: date, start_hour: int) -> None:
    slot = get_shift(d, start_hour)
    if slot:
        slot.up_for_drop = True
        slot.put()


# ---------------------------------------------------------------------------
# ShiftRequest queries
# ---------------------------------------------------------------------------


def get_pending_requests_for_editor(
    editor_id: str, reference_date: date = None
) -> list:
    sunday, saturday = get_week_bounds(reference_date)
    return ShiftRequest.query(
        ShiftRequest.requester_id == editor_id,
        ShiftRequest.status == "pending",
        ShiftRequest.source_shift_date >= sunday,
        ShiftRequest.source_shift_date <= saturday,
    ).fetch()


def build_pending_map(editor_id: str, reference_date: date = None) -> dict:
    requests = get_pending_requests_for_editor(editor_id, reference_date)
    pending = {}
    for req in requests:
        key = _slot_key_name(req.source_shift_date, req.source_shift_hour)
        if req.target_shift_date:
            req.target_label = (
                f"{day_label(req.target_shift_date)} "
                f"{shift_label(req.target_shift_hour)}"
            )
        else:
            req.target_label = ""
        pending[key] = req
    return pending


def build_swap_requested_set(reference_date: date = None) -> set:
    sunday, saturday = get_week_bounds(reference_date)
    reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.target_shift_date >= sunday,
        ShiftRequest.target_shift_date <= saturday,
    ).fetch(projection=[ShiftRequest.target_shift_date, ShiftRequest.target_shift_hour])
    return {
        _slot_key_name(r.target_shift_date, r.target_shift_hour)
        for r in reqs
        if r.target_shift_date and r.target_shift_hour is not None
    }


# ---------------------------------------------------------------------------
# Business logic: Drop
# ---------------------------------------------------------------------------


def request_drop(user, shift_date: date, shift_hour: int) -> dict:
    """
    Mark shift as up-for-drop. Stays assigned until someone picks it up
    or copy chief approves the removal.
    """
    if is_shift_in_past(shift_date, shift_hour):
        return {"error": "Cannot drop a shift that has already started."}

    editor_id = user.email
    mark_up_for_drop(shift_date, shift_hour)

    req = ShiftRequest(
        request_type="drop",
        requester_id=editor_id,
        requester_name=user.name,
        source_shift_date=shift_date,
        source_shift_hour=shift_hour,
        approver_type="copy_chief",
    )
    req.put()
    send_drop_approval_to_slack(req)
    return {"request_id": req.key.id(), "up_for_drop": True}


# ---------------------------------------------------------------------------
# Business logic: Pickup (claim an up-for-drop shift)
# ---------------------------------------------------------------------------


def pickup_shift(user, shift_date: date, shift_hour: int) -> dict:
    """
    Pick up a shift marked as up_for_drop. Immediate, no approval needed.
    """
    if is_shift_in_past(shift_date, shift_hour):
        return {"error": "Cannot pick up a shift that has already started."}

    slot = get_shift(shift_date, shift_hour)
    if not slot or not slot.editor_id:
        return {"error": "This shift is not currently assigned to anyone."}
    if not slot.up_for_drop:
        return {"error": "This shift is not available for pickup."}

    old_editor_id = slot.editor_id
    old_editor_name = slot.editor_name

    # Assign to new editor (also clears up_for_drop)
    assign_shift(shift_date, shift_hour, user.email, user.name)

    # Cancel any pending drop request from the original editor
    _cancel_drop_requests_for_shift(old_editor_id, shift_date, shift_hour)

    # Audit trail
    req = ShiftRequest(
        request_type="pickup",
        status="approved",
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


def _cancel_drop_requests_for_shift(editor_id: str, shift_date: date, shift_hour: int):
    reqs = ShiftRequest.query(
        ShiftRequest.requester_id == editor_id,
        ShiftRequest.request_type == "drop",
        ShiftRequest.status == "pending",
        ShiftRequest.source_shift_date == shift_date,
        ShiftRequest.source_shift_hour == shift_hour,
    ).fetch()
    for r in reqs:
        r.status = "cancelled"
        r.resolved_at = datetime.utcnow()
    if reqs:
        ndb.put_multi(reqs)


# ---------------------------------------------------------------------------
# Business logic: Add Slot
# ---------------------------------------------------------------------------


def add_slot(user, shift_date: date, shift_hour: int) -> dict:
    """Add editor into an empty shift slot. No approval needed."""
    slot = get_shift(shift_date, shift_hour)
    if slot and slot.editor_id is not None:
        return {"success": False, "reason": "Slot is already occupied."}
    assign_shift(shift_date, shift_hour, user.email, user.name)
    return {"success": True}


# ---------------------------------------------------------------------------
# Business logic: Swap
# ---------------------------------------------------------------------------


def request_swap(
    user,
    source_date: date,
    source_hour: int,
    target_date: date,
    target_hour: int,
    swap_mode: str,  # "direct" | "add_into" | "swap_drop"
) -> dict:
    """
    Handle a swap request.

    swap_mode="direct": exchange shifts with target editor. Needs their approval.
    swap_mode="add_into": join target slot, drop source. Needs copy chief approval.
    swap_mode="swap_drop": swap with an editor who has their shift up for drop.
        Instead of just picking up their shift, you offer to exchange slots.
        Needs the dropping editor's approval (they swap instead of dropping).
    """
    if is_shift_in_past(source_date, source_hour):
        return {"error": "Cannot swap a shift that has already started."}

    target_slot = get_shift(target_date, target_hour)
    target_editor_id = target_slot.editor_id if target_slot else None
    target_editor_name = target_slot.editor_name if target_slot else None

    if swap_mode == "direct":
        if target_editor_id is None:
            return {"error": "Cannot direct swap with an empty slot."}
        req = ShiftRequest(
            request_type="swap_direct",
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
        # Swap with someone who wants to drop — they take your slot instead
        if target_editor_id is None:
            return {"error": "Cannot swap-drop with an empty slot."}
        req = ShiftRequest(
            request_type="swap_drop",
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


# ---------------------------------------------------------------------------
# Business logic: Cancel / Approve / Deny
# ---------------------------------------------------------------------------


def cancel_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    if req.request_type == "drop":
        slot = get_shift(req.source_shift_date, req.source_shift_hour)
        if slot:
            slot.up_for_drop = False
            slot.put()

    req.status = "cancelled"
    req.resolved_at = datetime.utcnow()
    req.put()
    notify_slack_cancelled(req)
    return {"success": True}


def approve_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    req.status = "approved"
    req.resolved_at = datetime.utcnow()

    if req.request_type == "drop":
        clear_shift(req.source_shift_date, req.source_shift_hour)

    elif req.request_type in ("swap_direct", "swap_drop"):
        # Exchange: A gets B's slot, B gets A's slot
        source = get_shift(req.source_shift_date, req.source_shift_hour)
        target = get_shift(req.target_shift_date, req.target_shift_hour)
        a_id, a_name = source.editor_id, source.editor_name
        b_id, b_name = target.editor_id, target.editor_name
        source.editor_id, source.editor_name = b_id, b_name
        target.editor_id, target.editor_name = a_id, a_name
        source.up_for_drop = False
        target.up_for_drop = False
        ndb.put_multi([source, target])

        # If this was a swap_drop, cancel the original drop request
        if req.request_type == "swap_drop":
            _cancel_drop_requests_for_shift(
                req.target_editor_id,
                req.target_shift_date,
                req.target_shift_hour,
            )

    elif req.request_type in ("swap_add", "swap_empty"):
        clear_shift(req.source_shift_date, req.source_shift_hour)
        assign_shift(
            req.target_shift_date,
            req.target_shift_hour,
            req.requester_id,
            req.requester_name,
        )

    req.put()
    notify_slack_approved(req)
    return {"success": True}


def deny_request(request_id) -> dict:
    req = ndb.Key(ShiftRequest, int(request_id)).get()
    if not req or req.status != "pending":
        return {"success": False, "reason": "Request not found or not pending."}

    if req.request_type == "drop":
        slot = get_shift(req.source_shift_date, req.source_shift_hour)
        if slot:
            slot.up_for_drop = False
            slot.put()

    req.status = "denied"
    req.resolved_at = datetime.utcnow()
    req.put()
    notify_slack_denied(req)
    return {"success": True}


# ---------------------------------------------------------------------------
# Slack integration stubs
# ---------------------------------------------------------------------------


def send_drop_approval_to_slack(request: ShiftRequest):
    """Send to copy chief: editor wants to drop. Shift is up for pickup."""
    # TODO: implement
    pass


def send_direct_swap_to_slack(request: ShiftRequest):
    """Send DM to target editor: requester wants to exchange shifts."""
    # TODO: implement
    pass


def send_swap_drop_to_slack(request: ShiftRequest):
    """
    Send DM to the editor who has their shift up for drop:
    'Instead of dropping, would you like to swap shifts with [requester]?
    You would take their [source shift] and they would take your [target shift].'
    Include Approve/Deny buttons.
    """
    # TODO: implement
    pass


def send_swap_approval_to_slack(request: ShiftRequest):
    """Send to copy chief: editor wants to swap-add or swap into empty slot."""
    # TODO: implement
    pass


def notify_slack_swap_involves_your_shift(
    request: ShiftRequest, target_editor_name: str
):
    """Inform editor their shift is target of a swap_add (copy chief decides)."""
    # TODO: implement
    pass


def notify_slack_shift_picked_up(request: ShiftRequest, old_editor_name: str):
    """Notify original editor their up-for-drop shift was picked up."""
    # TODO: implement
    pass


def notify_slack_cancelled(request: ShiftRequest):
    # TODO: implement
    pass


def notify_slack_approved(request: ShiftRequest):
    # TODO: implement
    pass


def notify_slack_denied(request: ShiftRequest):
    # TODO: implement
    pass
