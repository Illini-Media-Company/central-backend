"""
copy_scheduler_admin.py

Service functions for the admin dashboard.

Admin operations bypass normal business-logic guards (past-shift checks,
pending-request cancellation, approval flows). Every mutation is a direct
Datastore write. Functions return a result dict with either the affected
entity data or an {"error": "..."} entry on failure.

All shift functions accept a `slot_class` parameter (ShiftSlot or SeniorShiftSlot)
so staff and senior grids share the same logic.
"""

import datetime
from datetime import date
from google.cloud import ndb

from db.copy_schedule import CopyEditorAdmin, ShiftSlot, SeniorShiftSlot, ShiftRequest
from db import client
from util.copy_schedule import (
    SHIFT_START_HOURS,
    SENIOR_COPY_EDITOR_HOURS,
    get_week_bounds,
    _slot_key_name,
)


def add_copy_editor(
    name: str, email: str, phone: str = None, category: str = None
) -> dict:
    with client.context():
        entity = CopyEditorAdmin(
            name=name, email=email, phone=phone or None, category=category or None
        )
        entity.put()
        return entity.to_dict()


def get_all_copy_editors() -> list[dict]:
    with client.context():
        editors = CopyEditorAdmin.query().order(CopyEditorAdmin.name).fetch()
        return [e.to_dict() for e in editors]


def get_copy_editor_by_uid(uid) -> dict | None:
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        return entity.to_dict() if entity else None


def update_copy_editor(
    uid, name: str = None, email: str = None, phone: str = None, category: str = None
) -> dict | None:
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
    group_map: {"Copy Editor": [{"email": "...", "displayName": "..."}], ...}
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


def get_editor_with_shifts(
    uid, reference_date: date = None, slot_class=ShiftSlot
) -> dict | None:
    """
    Return an editor dict with a "shifts" key containing all their
    shift slots for the current (or given) week for the given slot_class.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return None
        sunday, saturday = get_week_bounds(reference_date)
        shifts = (
            slot_class.query(
                slot_class.editor_id == entity.email,
                slot_class.date >= sunday,
                slot_class.date <= saturday,
            )
            .order(slot_class.date, slot_class.start_hour)
            .fetch()
        )
        result = entity.to_dict()
        result["shifts"] = [s.to_dict() for s in shifts]
        return result


def get_all_editors_with_shifts(
    reference_date: date = None, slot_class=ShiftSlot
) -> list[dict]:
    """
    Return all editors, each with a "shifts" key for the current (or given) week.
    """
    with client.context():
        sunday, saturday = get_week_bounds(reference_date)
        editors = CopyEditorAdmin.query().order(CopyEditorAdmin.name).fetch()
        all_shifts = slot_class.query(
            slot_class.date >= sunday,
            slot_class.date <= saturday,
        ).fetch()

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


def _valid_hours_for_class(slot_class) -> list[int]:
    return (
        SENIOR_COPY_EDITOR_HOURS if slot_class is SeniorShiftSlot else SHIFT_START_HOURS
    )


def get_all_shifts(slot_class=ShiftSlot) -> list[dict]:
    with client.context():
        shifts = (
            slot_class.query().order(slot_class.date, slot_class.start_hour).fetch()
        )
        return [s.to_dict() for s in shifts]


def get_shifts_for_week(
    reference_date: date = None, slot_class=ShiftSlot
) -> list[dict]:
    with client.context():
        sunday, saturday = get_week_bounds(reference_date)
        shifts = (
            slot_class.query(
                slot_class.date >= sunday,
                slot_class.date <= saturday,
            )
            .order(slot_class.date, slot_class.start_hour)
            .fetch()
        )
        return [s.to_dict() for s in shifts]


def get_shift_by_uid(uid: str, slot_class=ShiftSlot) -> dict | None:
    with client.context():
        shift = slot_class.get_by_id(uid)
        return shift.to_dict() if shift else None


def add_shift(
    date: date,
    start_hour: int,
    editor_id: str = None,
    editor_name: str = None,
    editor_id_2: str = None,
    editor_name_2: str = None,
    slot_class=ShiftSlot,
) -> dict:
    """
    Create a shift slot directly. editor_id / editor_id_2 must be email addresses.
    Returns {"error": ...} if the slot already exists or the hour is invalid.
    """
    valid_hours = _valid_hours_for_class(slot_class)
    if start_hour not in valid_hours:
        return {
            "error": f"Invalid start_hour {start_hour} for {slot_class.__name__}. Must be one of {valid_hours}."
        }
    with client.context():
        key_name = _slot_key_name(date, start_hour)
        if slot_class.get_by_id(key_name) is not None:
            return {
                "error": f"Slot {key_name} already exists in {slot_class.__name__}."
            }
        entity = slot_class(
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
    slot_class=ShiftSlot,
) -> dict | None:
    """
    Update a shift slot by its string key. Cancels any pending requests
    for this slot since the assignment changed.
    Returns updated dict, or None if not found.
    """
    with client.context():
        entity = slot_class.get_by_id(uid)
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
        _cancel_pending_requests_for_slot(entity.date, entity.start_hour, slot_class)
        return entity.to_dict()


def delete_shift(uid: str, slot_class=ShiftSlot) -> dict | None:
    """
    Delete a single shift slot. Also cancels any pending requests referencing it.
    Returns the deleted entity dict, or None if not found.
    """
    with client.context():
        entity = slot_class.get_by_id(uid)
        if entity is None:
            return None
        d = entity.to_dict()
        slot_date = entity.date
        slot_hour = entity.start_hour
        entity.key.delete()
        _cancel_pending_requests_for_slot(slot_date, slot_hour, slot_class)
        return d


def get_all_shift_requests(status: str = None, slot_type: str = None) -> list[dict]:
    """
    Return all shift requests, optionally filtered by status and/or slot_type.
    Sorted by created_at descending (newest first).
    """
    with client.context():
        q = ShiftRequest.query()
        if status is not None:
            q = q.filter(ShiftRequest.status == status)
        if slot_type is not None:
            q = q.filter(ShiftRequest.slot_type == slot_type)
        requests = q.order(-ShiftRequest.created_at).fetch()
        return [r.to_dict() for r in requests]


def get_pending_shift_requests(slot_type: str = None) -> list[dict]:
    return get_all_shift_requests(status="pending", slot_type=slot_type)


def _slot_class_for_request(req: ShiftRequest):
    return (
        SeniorShiftSlot if getattr(req, "slot_type", "staff") == "senior" else ShiftSlot
    )


def approve_shift_request(uid) -> dict:
    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        sc = _slot_class_for_request(req)
        req.status = "approved"
        req.resolved_at = datetime.datetime.utcnow()

        if req.request_type == "drop":
            _clear_slot(req.source_shift_date, req.source_shift_hour, sc)

        elif req.request_type in ("swap_direct", "swap_drop"):
            source = sc.get_by_id(
                _slot_key_name(req.source_shift_date, req.source_shift_hour)
            )
            target = sc.get_by_id(
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
                _cancel_pending_requests_for_slot(
                    req.target_shift_date, req.target_shift_hour, sc
                )

        elif req.request_type in ("swap_add", "swap_empty"):
            _clear_slot(req.source_shift_date, req.source_shift_hour, sc)
            target_slot = sc.get_by_id(
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
                    sc,
                )

        req.put()
        return req.to_dict()


def deny_shift_request(uid) -> dict:
    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        sc = _slot_class_for_request(req)
        if req.request_type == "drop":
            slot = sc.get_by_id(
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
    with client.context():
        req = ShiftRequest.get_by_id(int(uid))
        if req is None:
            return {"error": f"Request {uid} not found."}
        if req.status != "pending":
            return {"error": f"Request {uid} is already {req.status}."}

        sc = _slot_class_for_request(req)
        if req.request_type == "drop":
            slot = sc.get_by_id(
                _slot_key_name(req.source_shift_date, req.source_shift_hour)
            )
            if slot:
                slot.up_for_drop = False
                slot.put()

        req.status = "cancelled"
        req.resolved_at = datetime.datetime.utcnow()
        req.put()
        return req.to_dict()


def _cancel_pending_requests_for_slot(
    slot_date: date, start_hour: int, slot_class=ShiftSlot
) -> None:
    now = datetime.datetime.utcnow()
    slot_type = "senior" if slot_class is SeniorShiftSlot else "staff"

    source_reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.slot_type == slot_type,
        ShiftRequest.source_shift_date == slot_date,
        ShiftRequest.source_shift_hour == start_hour,
    ).fetch()

    target_reqs = ShiftRequest.query(
        ShiftRequest.status == "pending",
        ShiftRequest.slot_type == slot_type,
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


def _clear_slot(slot_date: date, start_hour: int, slot_class=ShiftSlot) -> None:
    slot = slot_class.get_by_id(_slot_key_name(slot_date, start_hour))
    if slot:
        slot.editor_id = None
        slot.editor_name = None
        slot.up_for_drop = False
        slot.put()


def _assign_slot(
    slot_date: date,
    start_hour: int,
    editor_id: str,
    editor_name: str,
    slot_class=ShiftSlot,
) -> None:
    key_name = _slot_key_name(slot_date, start_hour)
    slot = slot_class.get_by_id(key_name)
    if slot is None:
        slot = slot_class(id=key_name, date=slot_date, start_hour=start_hour)
    slot.editor_id = editor_id
    slot.editor_name = editor_name
    slot.up_for_drop = False
    slot.put()
