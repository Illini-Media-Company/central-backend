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
    Represents a single 2-hour shift slot in the weekly calendar.

    Key name convention: "{YYYY-MM-DD}_{HH}" e.g. "2025-02-03_14" for Mon Feb 3, 2pm-4pm.

    Double-booking (editor_id_2) is supported for overflow/emergency coverage.
    Under normal operation only editor_id is populated.
    """

    date = ndb.DateProperty(required=True)
    start_hour = ndb.IntegerProperty(required=True)  # 8, 10, 12, 14, 16, 18, 20, 22

    # Primary assigned editor — None means the slot is empty.
    editor_id = ndb.StringProperty(default=None)
    editor_name = ndb.StringProperty(default=None)

    # Secondary assigned editor — populated only for double-booked slots.
    editor_id_2 = ndb.StringProperty(default=None)
    editor_name_2 = ndb.StringProperty(default=None)

    # Editor has marked this shift as available for someone else to pick up.
    # Shift stays assigned to the original editor until claimed or copy chief
    # approves the removal.
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

    request_type:
      "drop"        — editor wants to drop a shift; marked up_for_drop and stays
                      assigned until someone picks it up or copy chief approves removal.
      "swap_direct" — editor A and editor B exchange shifts (needs editor B's approval).
      "swap_add"    — editor A joins editor B's occupied slot, dropping their own
                      (needs copy chief approval).
      "swap_empty"  — editor A moves into an empty slot, dropping their own
                      (needs copy chief approval).
      "swap_drop"   — editor A swaps with editor B who has their shift up for drop;
                      instead of B just dropping, they exchange slots
                      (needs editor B's approval).
      "pickup"      — editor claims a shift marked up_for_drop; immediate, no approval
                      needed, but tracked for audit.

    Lifecycle:
      pending -> approved | denied | cancelled
      (pickup requests are created directly as "approved")
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

    # Editor making the request.
    requester_id = ndb.StringProperty(required=True)
    requester_name = ndb.StringProperty(required=True)

    # The shift the requester currently holds (or, for pickup, the shift being claimed).
    source_shift_date = ndb.DateProperty(required=True)
    source_shift_hour = ndb.IntegerProperty(required=True)

    # Destination shift — populated for all swap types; None for drop/pickup.
    target_shift_date = ndb.DateProperty(default=None)
    target_shift_hour = ndb.IntegerProperty(default=None)

    # Editor currently occupying the target shift — populated for swap_direct,
    # swap_add, and swap_drop.
    target_editor_id = ndb.StringProperty(default=None)
    target_editor_name = ndb.StringProperty(default=None)

    # Who must approve this request.
    approver_type = ndb.StringProperty(
        required=True,
        choices=["editor", "copy_chief", "none"],
    )
    # Populated when approver_type == "editor".
    approver_id = ndb.StringProperty(default=None)

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    resolved_at = ndb.DateTimeProperty(default=None)

    # Slack message ID so the approval message can be updated in-place.
    slack_message_id = ndb.StringProperty(default=None)

    def to_dict(self):
        return {
            "uid": self.key.id() if self.key else None,
            "request_type": self.request_type,
            "status": self.status,
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
