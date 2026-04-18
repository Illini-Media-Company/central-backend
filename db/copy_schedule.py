"""
Contains all NDB copy scheduler model definitions.
"""

import datetime
from google.cloud import ndb


class CopyEditorAdmin(ndb.Model):
    """
    Represents a copy editor known to the system.
    Key: auto-generated integer id.
    """

    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty(required=True)
    phone = ndb.StringProperty(default=None)
    category = ndb.StringProperty(default=None)

    def to_dict(self):
        return {
            "uid": self.key.id() if self.key else None,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "category": self.category,
        }


class ShiftSlot(ndb.Model):
    """
    Staff copy editor shift slots.
    Key: "{YYYY-MM-DD}_{H}" e.g. "2025-02-03_14"
    Regular hours: 8am–12am (2-hour slots).
    Break week hours: 10am, 2pm, 6pm (4-hour slots).
    Capacity: 2 editors (editor_id + editor_id_2).
    """

    date = ndb.DateProperty(required=True)
    start_hour = ndb.IntegerProperty(required=True)

    editor_id = ndb.StringProperty(default=None)
    editor_name = ndb.StringProperty(default=None)
    editor_id_2 = ndb.StringProperty(default=None)
    editor_name_2 = ndb.StringProperty(default=None)

    up_for_drop = ndb.BooleanProperty(default=False)

    def to_dict(self):
        return {
            "uid": self.key.id() if self.key else None,
            "date": self.date,
            "start_hour": self.start_hour,
            "editor_id": self.editor_id,
            "editor_name": self.editor_name,
            "editor_id_2": self.editor_id_2,
            "editor_name_2": self.editor_name_2,
            "up_for_drop": self.up_for_drop,
        }


class SeniorShiftSlot(ndb.Model):
    """
    Senior copy editor shift slots.
    Key: "{YYYY-MM-DD}_{H}" — same convention as ShiftSlot.
    A given key can exist in BOTH ShiftSlot and SeniorShiftSlot simultaneously,
    representing concurrent staff and senior coverage of the same time window.
    Regular hours: 10am–10pm (2-hour slots, senior restriction).
    Break week hours: 10am, 2pm, 6pm (4-hour slots).
    Capacity: 2 editors (editor_id + editor_id_2).
    """

    date = ndb.DateProperty(required=True)
    start_hour = ndb.IntegerProperty(required=True)

    editor_id = ndb.StringProperty(default=None)
    editor_name = ndb.StringProperty(default=None)
    editor_id_2 = ndb.StringProperty(default=None)
    editor_name_2 = ndb.StringProperty(default=None)

    up_for_drop = ndb.BooleanProperty(default=False)

    def to_dict(self):
        return {
            "uid": self.key.id() if self.key else None,
            "date": self.date,
            "start_hour": self.start_hour,
            "editor_id": self.editor_id,
            "editor_name": self.editor_name,
            "editor_id_2": self.editor_id_2,
            "editor_name_2": self.editor_name_2,
            "up_for_drop": self.up_for_drop,
        }


class ShiftRequest(ndb.Model):
    """
    Represents a pending drop or swap request that may require approval.
    Key: auto-generated integer id.

    slot_type distinguishes whether the request operates on ShiftSlot (staff)
    or SeniorShiftSlot (senior). Defaults to "staff" for backward compatibility.
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

    # "staff" uses ShiftSlot, "senior" uses SeniorShiftSlot.
    slot_type = ndb.StringProperty(default="staff", choices=["staff", "senior"])

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

    def to_dict(self):
        return {
            "uid": self.key.id() if self.key else None,
            "request_type": self.request_type,
            "status": self.status,
            "slot_type": self.slot_type,
            "requester_id": self.requester_id,
            "requester_name": self.requester_name,
            "source_shift_date": self.source_shift_date,
            "source_shift_hour": self.source_shift_hour,
            "target_shift_date": self.target_shift_date,
            "target_shift_hour": self.target_shift_hour,
            "target_editor_id": self.target_editor_id,
            "target_editor_name": self.target_editor_name,
            "approver_type": self.approver_type,
            "approver_id": self.approver_id,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "slack_message_id": self.slack_message_id,
        }


class BreakWeek(ndb.Model):
    """
    Marks a specific week as a break week with a condensed 3-slot schedule.
    Key: ISO date string of the Sunday starting that week (e.g. "2025-12-22").
    """

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    created_by = ndb.StringProperty(default=None)

    def to_dict(self):
        return {
            "week_start": self.key.id() if self.key else None,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }
