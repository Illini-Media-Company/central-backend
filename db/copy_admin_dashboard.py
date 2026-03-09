import datetime

from google.cloud import ndb

from . import client


class CopyEditorAdmin(ndb.Model):
    uid = ndb.ComputedProperty(lambda self: self.key.id() if self.key else None)
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty(required=True)
    phone = ndb.StringProperty(default=None)
    category = ndb.StringProperty(default=None)


def add_copy_editor(name, email, phone=None, category=None):
    """Add a new copy editor to the database."""
    with client.context():
        entity = CopyEditorAdmin(
            name=name,
            email=email,
            phone=phone or None,
            category=category or None,
        )
        entity.put()
        return entity.to_dict()


def get_all_copy_editors():
    """Returns all copy editors."""
    with client.context():
        editors = CopyEditorAdmin.query().fetch()
    return [e.to_dict() for e in editors]


def get_copy_editor_by_uid(uid):
    """Lookup a copy editor by its unique UID (entity id)."""
    with client.context():
        ce = CopyEditorAdmin.get_by_id(uid)
        return ce.to_dict() if ce else None


def update_copy_editor(uid, **fields):
    """Update a copy editor by their UID.

    Only passed fields are changed. Unknown field names are ignored.
    Returns updated dict or None if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return None
        for key, value in fields.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        entity.put()
        return entity.to_dict()


def delete_copy_editor(uid):
    """Delete a single editor by UID.

    Returns the deleted entity dict if deleted, False if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return entity.to_dict()


class ShiftSlot(ndb.Model):
    """
    Represents a single 2-hour shift slot in the weekly calendar.

    Key name convention: "{YYYY-MM-DD}_{HH}" e.g. "2025-02-03_14" for Mon Feb 3, 2pm-4pm.
    Capacity is 1 under normal operation. Slot is empty when editor_id is None.
    """

    uid = ndb.ComputedProperty(lambda self: self.key.id() if self.key else None)
    date = ndb.DateProperty(required=True)
    start_hour = ndb.IntegerProperty(required=True)  # 8, 10, 12, 14, 16, 18, 20, 22
    editor_id = ndb.StringProperty(default=None)  # email/id of assigned editor, or None
    editor_name = ndb.StringProperty(
        default=None
    )  # display name for calendar rendering
    up_for_drop = ndb.BooleanProperty(default=False)
    editor_id_2 = ndb.StringProperty(default=None)
    editor_name_2 = ndb.StringProperty(default=None)


def add_shift(
    date,
    start_hour,
    editor_id=None,
    editor_name=None,
    editor_id_2=None,
    editor_name_2=None,
):
    """Add a shift slot to the database.

    Key is "{YYYY-MM-DD}_{HH}" to match the shared convention.
    """
    key_name = f"{date}_{start_hour:02d}"
    with client.context():
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


def get_all_shifts():
    """Returns all shift slots."""
    with client.context():
        shifts = ShiftSlot.query().fetch()
    return [s.to_dict() for s in shifts]


def get_shift_by_uid(uid):
    """Lookup a shift slot by its string key (e.g. '2025-02-03_14')."""
    with client.context():
        shift = ShiftSlot.get_by_id(uid)
        return shift.to_dict() if shift else None


def update_shift(uid, **fields):
    """Update a shift slot by its string key.

    Only passed fields are changed. Unknown field names are ignored.
    Returns updated dict or None if not found.
    """
    with client.context():
        entity = ShiftSlot.get_by_id(uid)
        if entity is None:
            return None
        for key, value in fields.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        entity.put()
        return entity.to_dict()


def delete_shift(uid):
    """Delete a single shift slot by its string key.

    Returns the deleted entity dict if deleted, False if not found.
    """
    with client.context():
        entity = ShiftSlot.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return entity.to_dict()


class ShiftRequest(ndb.Model):
    """
    Represents a pending drop or swap request that requires approval.
    Key: auto-generated.
    """

    request_type = ndb.StringProperty(
        required=True,
        choices=[
            "drop",
            "swap_direct",
            "swap_add",
            "swap_empty",
            "swap_drop",
            "pickup",
        ],
    )
    status = ndb.StringProperty(
        required=True,
        default="pending",
        choices=["pending", "approved", "denied", "cancelled"],
    )

    requester_id = ndb.StringProperty(required=True)
    requester_name = ndb.StringProperty(required=True)

    source_shift_date = ndb.DateProperty(required=True)
    source_shift_hour = ndb.IntegerProperty(required=True)

    target_shift_date = ndb.DateProperty(default=None)
    target_shift_hour = ndb.IntegerProperty(default=None)

    target_editor_id = ndb.StringProperty(default=None)
    target_editor_name = ndb.StringProperty(default=None)

    approver_type = ndb.StringProperty(
        required=True,
        choices=["editor", "copy_chief", "none"],
    )
    approver_id = ndb.StringProperty(default=None)

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    resolved_at = ndb.DateTimeProperty(default=None)

    slack_message_id = ndb.StringProperty(default=None)


def get_all_shift_requests():
    """Returns all shift requests."""
    with client.context():
        requests = ShiftRequest.query().fetch()
    return [r.to_dict() for r in requests]


def update_shift_request_status(uid, status):
    """Approve or deny a shift request by its integer UID.

    Sets resolved_at timestamp when finalizing.
    Returns updated dict or None if not found.
    """
    with client.context():
        entity = ShiftRequest.get_by_id(uid)
        if entity is None:
            return None
        entity.status = status
        if status in ("approved", "denied", "cancelled"):
            entity.resolved_at = datetime.datetime.utcnow()
        entity.put()
        return entity.to_dict()
