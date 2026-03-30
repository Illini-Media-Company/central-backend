"""
copy_scheduler_admin.py

Service functions for the admin dashboard.

Admin operations bypass normal business-logic guards (past-shift checks,
pending-request cancellation, approval flows). Every mutation is a direct
Datastore write. Functions return a result dict with either the affected
entity data or an {"error": "..."} entry on failure.
"""

import datetime
from datetime import date
from google.cloud import ndb

from db.copy_schedule import CopyEditorAdmin, ShiftSlot, ShiftRequest
from db import client
from util.copy_schedule import (
    SHIFT_START_HOURS,
    get_week_bounds,
    _slot_key_name,
)


def add_copy_editor(
    name: str, email: str, phone: str = None, category: str = None
) -> dict:
    """Create a new copy editor."""
    with client.context():
        entity = CopyEditorAdmin(
            name=name,
            email=email,
            phone=phone or None,
            category=category or None,
        )
        entity.put()
        return entity.to_dict()


def get_all_copy_editors() -> list[dict]:
    """Return all copy editors, sorted by name."""
    with client.context():
        editors = CopyEditorAdmin.query().order(CopyEditorAdmin.name).fetch()
        return [e.to_dict() for e in editors]


def get_copy_editor_by_uid(uid) -> dict | None:
    """Return a single editor by uid, or None if not found."""
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        return entity.to_dict() if entity else None


def update_copy_editor(
    uid,
    name: str = None,
    email: str = None,
    phone: str = None,
    category: str = None,
) -> dict | None:
    """
    Update any fields on a copy editor.
    phone and category are always overwritten (pass None to clear them).
    Returns updated dict, or None if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return None
        if name is not None:
            entity.name = name
        if email is not None:
            entity.email = email
        entity.phone = phone
        entity.category = category
        entity.put()
        return entity.to_dict()


def delete_copy_editor(uid) -> dict | None:
    """
    Delete a copy editor by uid.
    Returns the deleted entity dict, or None if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return None
        d = entity.to_dict()
        entity.key.delete()
        return d


def upsert_editors_from_groups(group_map: dict) -> dict:
    """
    Sync editors from Google Groups into the DB.

    Arguments:
        `group_map` (`dict`): maps category string -> list of member dicts
            e.g. {"Copy Editor": [{"email": "...", "displayName": "..."}], ...}
    Returns:
        dict with "added" and "skipped" counts
    """
    added = 0
    skipped = 0
    with client.context():
        existing_emails = {
            e.email for e in CopyEditorAdmin.query().fetch(projection=["email"])
        }
        for category, members in group_map.items():
            for m in members:
                email = m.get("email", "").strip().lower()
                if not email or email in existing_emails:
                    skipped += 1
                    continue
                name = m.get("displayName") or email.split("@")[0]
                entity = CopyEditorAdmin(name=name, email=email, category=category)
                entity.put()
                existing_emails.add(email)
                added += 1
    return {"added": added, "skipped": skipped}


def get_editor_with_shifts(uid, reference_date: date = None) -> dict | None:
    """
    Return an editor dict with a "shifts" key containing all their
    ShiftSlots for the current (or given) week.
    Returns None if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return None
        sunday, saturday = get_week_bounds(reference_date)
        shifts = (
            ShiftSlot.query(
                ShiftSlot.editor_id == entity.email,
                ShiftSlot.date >= sunday,
                ShiftSlot.date <= saturday,
            )
            .order(ShiftSlot.date, ShiftSlot.start_hour)
            .fetch()
        )
        result = entity.to_dict()
        result["shifts"] = [s.to_dict() for s in shifts]
        return result


def get_all_editors_with_shifts(reference_date: date = None) -> list[dict]:
    """
    Return all editors, each with a "shifts" key for the current (or given) week.
    """
    with client.context():
        sunday, saturday = get_week_bounds(reference_date)
        editors = CopyEditorAdmin.query().order(CopyEditorAdmin.name).fetch()
        all_shifts = ShiftSlot.query(
            ShiftSlot.date >= sunday,
            ShiftSlot.date <= saturday,
        ).fetch()

        # Group shifts by editor email (editor_id is always email).
        shifts_by_editor: dict[str, list] = {}
        for s in all_shifts:
            if s.editor_id:
                shifts_by_editor.setdefault(s.editor_id, []).append(s.to_dict())
            if s.editor_id_2:
                shifts_by_editor.setdefault(s.editor_id_2, []).append(s.to_dict())

        result = []
        for e in editors:
            d = e.to_dict()
            d["shifts"] = shifts_by_editor.get(e.email, [])
            result.append(d)
        return result


def get_all_shifts() -> list[dict]:
    """Return every shift slot across all weeks, sorted by date/hour."""
    with client.context():
        shifts = ShiftSlot.query().order(ShiftSlot.date, ShiftSlot.start_hour).fetch()
        return [s.to_dict() for s in shifts]


def get_shifts_for_week(reference_date: date = None) -> list[dict]:
    """Return all shift slots for the current (or given) week, sorted by date/hour."""
    with client.context():
        sunday, saturday = get_week_bounds(reference_date)
        shifts = (
            ShiftSlot.query(
                ShiftSlot.date >= sunday,
                ShiftSlot.date <= saturday,
            )
            .order(ShiftSlot.date, ShiftSlot.start_hour)
            .fetch()
        )
        return [s.to_dict() for s in shifts]


def get_shift_by_uid(uid: str) -> dict | None:
    """Lookup a shift slot by its string key (e.g. '2025-02-03_14')."""
    with client.context():
        shift = ShiftSlot.get_by_id(uid)
        return shift.to_dict() if shift else None


def add_shift(
    date: date,
    start_hour: int,
    editor_id: str = None,
    editor_name: str = None,
    editor_id_2: str = None,
    editor_name_2: str = None,
) -> dict:
    """
    Create a shift slot directly.
    editor_id and editor_id_2 must be email addresses.
    Key uses the shared convention: "{YYYY-MM-DD}_{H}" (no zero-padding).
    Returns {"error": ...} if the slot already exists.
    """
    if start_hour not in SHIFT_START_HOURS:
        return {
            "error": f"Invalid start_hour {start_hour}. Must be one of {SHIFT_START_HOURS}."
        }
    with client.context():
        key_name = _slot_key_name(date, start_hour)
        existing = ShiftSlot.get_by_id(key_name)
        if existing is not None:
            return {"error": f"Slot {key_name} already exists."}
        entity = ShiftSlot(
            id=key_name,
            date=date,
            start_hour=start_hour,
            editor_id=editor_id or None,
            editor_name=editor_name or None,
            editor_id_2=editor_id_2 or None,
            editor_name_2=editor_name_2 or None,
        )
        entity.put()
        return entity.to_dict()


def update_shift(
    uid: str,
    date: date = None,
    start_hour: int = None,
    editor_id: str = None,
    editor_name: str = None,
    editor_id_2: str = None,
    editor_name_2: str = None,
) -> dict | None:
    """
    Update a shift slot by its string key.
    editor_id and editor_id_2 must be email addresses.
    Cancels any pending requests for this slot since the assignment changed.
    Returns updated dict, or None if not found.
    """
    with client.context():
        entity = ShiftSlot.get_by_id(uid)
        if entity is None:
            return None
        if date is not None:
            entity.date = date
        if start_hour is not None:
            entity.start_hour = start_hour
        entity.editor_id = editor_id or None
        entity.editor_name = editor_name or None
        entity.editor_id_2 = editor_id_2 or None
        entity.editor_name_2 = editor_name_2 or None
        entity.up_for_drop = False
        entity.put()

        # Cancel stale pending requests since the slot changed hands.
        _cancel_pending_requests_for_slot(entity.date, entity.start_hour)

        return entity.to_dict()


def delete_shift(uid: str) -> dict | None:
    """
    Delete a single shift slot by its string key.
    Also cancels any pending requests that reference it.
    Returns the deleted entity dict, or None if not found.
    """
    with client.context():
        entity = ShiftSlot.get_by_id(uid)
        if entity is None:
            return None
        d = entity.to_dict()
        slot_date = entity.date
        slot_hour = entity.start_hour
        entity.key.delete()
        _cancel_pending_requests_for_slot(slot_date, slot_hour)
        return d


def get_all_shift_requests(status: str = None) -> list[dict]:
    """
    Return all shift requests, optionally filtered by status.
    Sorted by created_at descending (newest first).
    """
    with client.context():
        q = ShiftRequest.query()
        if status is not None:
            q = q.filter(ShiftRequest.status == status)
        requests = q.order(-ShiftRequest.created_at).fetch()
        return [r.to_dict() for r in requests]


def get_pending_shift_requests() -> list[dict]:
    """Convenience wrapper — returns only pending requests."""
    return get_all_shift_requests(status="pending")


def approve_shift_request(uid) -> dict:
    """
    Approve a pending shift request and apply its effect to the slot(s).
    Handles all request types: drop, swap_direct, swap_drop, swap_add, swap_empty.
    Returns updated request dict, or {"error": ...}.
    """
    print(f"DEBUG approve_shift_request called with uid={uid}, type={type(uid)}")

    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        print(
            f"DEBUG req found: {req}, type={req.request_type if req else None}, status={req.status if req else None}"
        )

        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        req.status = "approved"
        req.resolved_at = datetime.datetime.utcnow()

        if req.request_type == "drop":
            _clear_slot(req.source_shift_date, req.source_shift_hour)

        elif req.request_type in ("swap_direct", "swap_drop"):
            source = ShiftSlot.get_by_id(
                _slot_key_name(req.source_shift_date, req.source_shift_hour)
            )
            target = ShiftSlot.get_by_id(
                _slot_key_name(req.target_shift_date, req.target_shift_hour)
            )
            if source and target:
                source.editor_id, target.editor_id = target.editor_id, source.editor_id
                source.editor_name, target.editor_name = (
                    target.editor_name,
                    source.editor_name,
                )
                source.up_for_drop = False
                target.up_for_drop = False
                ndb.put_multi([source, target])
            if req.request_type == "swap_drop":
                # Cancel the original drop request from the other editor.
                _cancel_pending_requests_for_slot(
                    req.target_shift_date, req.target_shift_hour
                )

        elif req.request_type in ("swap_add", "swap_empty"):
            _clear_slot(req.source_shift_date, req.source_shift_hour)
            target_slot = ShiftSlot.get_by_id(
                _slot_key_name(req.target_shift_date, req.target_shift_hour)
            )
            if req.request_type == "swap_add" and target_slot and target_slot.editor_id:
                target_slot.editor_id_2 = req.requester_id
                target_slot.editor_name_2 = req.requester_name
                target_slot.up_for_drop = False
                target_slot.put()
            else:
                _assign_slot(
                    req.target_shift_date,
                    req.target_shift_hour,
                    req.requester_id,
                    req.requester_name,
                )

        req.put()
        return req.to_dict()


def deny_shift_request(uid) -> dict:
    """
    Deny a pending shift request.
    Clears up_for_drop on the source slot if it was a drop request.
    Returns updated request dict, or {"error": ...}.
    """
    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        if req.request_type == "drop":
            slot = ShiftSlot.get_by_id(
                _slot_key_name(req.source_shift_date, req.source_shift_hour)
            )
            if slot:
                slot.up_for_drop = False
                slot.put()

        req.status = "denied"
        req.resolved_at = datetime.datetime.utcnow()
        req.put()
        return req.to_dict()


def cancel_shift_request(uid) -> dict:
    """
    Cancel any pending request regardless of type.
    Returns updated request dict, or {"error": ...}.
    """
    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        if req.request_type == "drop":
            slot = ShiftSlot.get_by_id(
                _slot_key_name(req.source_shift_date, req.source_shift_hour)
            )
            if slot:
                slot.up_for_drop = False
                slot.put()

        req.status = "cancelled"
        req.resolved_at = datetime.datetime.utcnow()
        req.put()
        return req.to_dict()


def _cancel_pending_requests_for_slot(slot_date: date, start_hour: int) -> None:
    """
    Cancel all pending ShiftRequests that reference this slot as source or target.
    Called internally after any destructive slot mutation.
    """
    now = datetime.datetime.utcnow()

    source_reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.source_shift_date == slot_date,
        ShiftRequest.source_shift_hour == start_hour,
    ).fetch()

    target_reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.target_shift_date == slot_date,
        ShiftRequest.target_shift_hour == start_hour,
    ).fetch()

    to_put = []
    for req in source_reqs + target_reqs:
        req.status = "cancelled"
        req.resolved_at = now
        to_put.append(req)

    if to_put:
        ndb.put_multi(to_put)


def _clear_slot(slot_date: date, start_hour: int) -> None:
    """Clear the primary assignment on a slot and reset up_for_drop."""
    slot = ShiftSlot.get_by_id(_slot_key_name(slot_date, start_hour))
    if slot:
        slot.editor_id = None
        slot.editor_name = None
        slot.up_for_drop = False
        slot.put()


def _assign_slot(
    slot_date: date, start_hour: int, editor_id: str, editor_name: str
) -> None:
    """Assign the primary editor on a slot (email as editor_id), creating it if needed."""
    key_name = _slot_key_name(slot_date, start_hour)
    slot = ShiftSlot.get_by_id(key_name)
    if slot is None:
        slot = ShiftSlot(id=key_name, date=slot_date, start_hour=start_hour)
    slot.editor_id = editor_id
    slot.editor_name = editor_name
    slot.up_for_drop = False
    slot.put()


# import datetime

# from google.cloud import ndb

# from db import client

# from db.copy_schedule import CopyEditorAdmin, ShiftRequest, ShiftSlot


# def _editor_dict(entity):
#     """Build a complete dict for a CopyEditorAdmin entity."""
#     return {
#         "uid": entity.key.id() if entity.key else None,
#         "name": entity.name,
#         "email": entity.email,
#         "phone": getattr(entity, "phone", None),
#         "category": getattr(entity, "category", None),
#     }


# def add_copy_editor(name, email, phone=None, category=None):
#     """Add a new copy editor to the database."""
#     with client.context():
#         entity = CopyEditorAdmin(
#             name=name,
#             email=email,
#             phone=phone or None,
#             category=category or None,
#         )
#         entity.put()
#         return _editor_dict(entity)


# def get_all_copy_editors():
#     """Returns all copy editors."""
#     with client.context():
#         editors = CopyEditorAdmin.query().fetch()
#         return [_editor_dict(e) for e in editors]


# def get_copy_editor_by_uid(uid):
#     """Lookup a copy editor by its unique UID (entity id)."""
#     with client.context():
#         ce = CopyEditorAdmin.get_by_id(uid)
#         return _editor_dict(ce) if ce else None


# def update_copy_editor(uid, name=None, email=None, phone=None, category=None):
#     """Update a copy editor by their UID. Returns updated dict or None if not found."""
#     with client.context():
#         entity = CopyEditorAdmin.get_by_id(uid)
#         if entity is None:
#             return None
#         if name is not None:
#             entity.name = name
#         if email is not None:
#             entity.email = email
#         entity.phone = phone
#         entity.category = category
#         entity.put()
#         return _editor_dict(entity)


# def delete_copy_editor(uid):
#     """Delete a single editor by UID.

#     Returns the deleted entity dict if deleted, False if not found.
#     """
#     with client.context():
#         entity = CopyEditorAdmin.get_by_id(uid)
#         if entity is None:
#             return False
#         d = _editor_dict(entity)
#         entity.key.delete()
#         return d

# def _shift_dict(entity):
#     """Build a complete dict for a ShiftSlot entity, always including every field."""
#     return {
#         "uid": entity.key.id() if entity.key else None,
#         "date": entity.date,
#         "start_hour": entity.start_hour,
#         "editor_id": getattr(entity, "editor_id", None),
#         "editor_name": getattr(entity, "editor_name", None),
#         "editor_id_2": getattr(entity, "editor_id_2", None),
#         "editor_name_2": getattr(entity, "editor_name_2", None),
#         "up_for_drop": getattr(entity, "up_for_drop", False),
#     }


# def add_shift(
#     date,
#     start_hour,
#     editor_id=None,
#     editor_name=None,
#     editor_id_2=None,
#     editor_name_2=None,
# ):
#     """Add a shift slot to the database.

#     Key is "{YYYY-MM-DD}_{HH}" to match the shared convention.
#     """
#     key_name = f"{date}_{start_hour}"
#     with client.context():
#         entity = ShiftSlot(
#             id=key_name,
#             date=date,
#             start_hour=start_hour,
#             editor_id=editor_id or None,
#             editor_name=editor_name or None,
#             editor_id_2=editor_id_2 or None,
#             editor_name_2=editor_name_2 or None,
#         )
#         entity.put()
#         return _shift_dict(entity)


# def get_all_shifts():
#     """Returns all shift slots."""
#     with client.context():
#         shifts = ShiftSlot.query().fetch()
#         return [_shift_dict(s) for s in shifts]


# def get_shift_by_uid(uid):
#     """Lookup a shift slot by its string key (e.g. '2025-02-03_14')."""
#     with client.context():
#         shift = ShiftSlot.get_by_id(uid)
#         return _shift_dict(shift) if shift else None


# def update_shift(
#     uid,
#     date=None,
#     start_hour=None,
#     editor_id=None,
#     editor_name=None,
#     editor_id_2=None,
#     editor_name_2=None,
# ):
#     """Update a shift slot by its string key. Returns updated dict or None if not found."""
#     with client.context():
#         entity = ShiftSlot.get_by_id(uid)
#         if entity is None:
#             return None
#         if date is not None:
#             entity.date = date
#         if start_hour is not None:
#             entity.start_hour = start_hour
#         entity.editor_id = editor_id
#         entity.editor_name = editor_name
#         entity.editor_id_2 = editor_id_2
#         entity.editor_name_2 = editor_name_2
#         entity.put()
#         return _shift_dict(entity)


# def delete_shift(uid):
#     """Delete a single shift slot by its string key.

#     Returns the deleted entity dict if deleted, False if not found.
#     """
#     with client.context():
#         entity = ShiftSlot.get_by_id(uid)
#         if entity is None:
#             return False
#         d = _shift_dict(entity)
#         entity.key.delete()
#         return d


# def _shift_request_dict(entity):
#     """Build a complete dict for a ShiftRequest entity, always including the key id."""
#     return {
#         "uid": entity.key.id() if entity.key else None,
#         "request_type": entity.request_type,
#         "status": entity.status,
#         "requester_id": entity.requester_id,
#         "requester_name": entity.requester_name,
#         "source_shift_date": entity.source_shift_date,
#         "source_shift_hour": entity.source_shift_hour,
#         "target_shift_date": getattr(entity, "target_shift_date", None),
#         "target_shift_hour": getattr(entity, "target_shift_hour", None),
#         "target_editor_id": getattr(entity, "target_editor_id", None),
#         "target_editor_name": getattr(entity, "target_editor_name", None),
#         "approver_type": entity.approver_type,
#         "approver_id": getattr(entity, "approver_id", None),
#         "created_at": getattr(entity, "created_at", None),
#         "resolved_at": getattr(entity, "resolved_at", None),
#         "slack_message_id": getattr(entity, "slack_message_id", None),
#     }


# def get_all_shift_requests():
#     """Returns all shift requests."""
#     with client.context():
#         requests = ShiftRequest.query().fetch()
#         return [_shift_request_dict(r) for r in requests]


# def update_shift_request_status(uid, status):
#     """Approve or deny a shift request by its integer UID.

#     Sets resolved_at timestamp when finalizing.
#     Returns updated dict or None if not found.
#     """
#     with client.context():
#         entity = ShiftRequest.get_by_id(uid)
#         if entity is None:
#             return None
#         entity.status = status
#         if status in ("approved", "denied", "cancelled"):
#             entity.resolved_at = datetime.datetime.utcnow()
#         entity.put()
#         return {"uid": entity.key.id(), "status": entity.status}
