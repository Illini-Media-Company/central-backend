from google.cloud import ndb


class ShiftSlot(ndb.Model):
    """
    Represents a single 2-hour shift slot in the weekly calendar.

    Key name convention: "{YYYY-MM-DD}_{HH}" e.g. "2025-02-03_14" for Mon Feb 3, 2pm-4pm.
    Capacity is 1 under normal operation. Slot is empty when editor_id is None.
    """

    date = ndb.DateProperty(required=True)
    start_hour = ndb.IntegerProperty(required=True)  # 8, 10, 12, 14, 16, 18, 20, 22
    editor_id = ndb.StringProperty(default=None)  # email/id of assigned editor, or None
    editor_name = ndb.StringProperty(
        default=None
    )  # display name for calendar rendering

    # "Up for drop" — editor has marked this shift as available for another
    # editor to pick up. The shift stays assigned to the original editor until
    # someone claims it (or copy chief approves the drop if no one does).
    up_for_drop = ndb.BooleanProperty(default=False)


class ShiftRequest(ndb.Model):
    """
    Represents a pending drop or swap request that requires approval.
    Key: auto-generated.

    request_type:
      - "drop"         : editor wants to drop a shift; shift is marked up_for_drop
                         and stays assigned until someone picks it up or copy chief
                         approves the removal
      - "swap_direct"  : editor A and editor B exchange shifts
                         (needs editor B's approval)
      - "swap_add"     : editor A joins editor B's occupied slot, dropping their own
                         (needs copy chief approval)
      - "swap_empty"   : editor A moves into an empty slot, dropping their own
                         (needs copy chief approval)
      - "swap_drop"    : editor A wants to swap with editor B who has their shift
                         up for drop; instead of B dropping, they exchange slots
                         (needs editor B's approval)
      - "pickup"       : editor picks up a shift marked as up_for_drop
                         (immediate — no approval needed, but tracked for record)

    Lifecycle: pending -> approved / denied / cancelled
               (pickup requests are created as "approved" immediately)
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

    # The editor making the request
    requester_id = ndb.StringProperty(required=True)
    requester_name = ndb.StringProperty(required=True)

    # Source shift (the shift the requester currently holds — or for pickup,
    # the shift being picked up)
    source_shift_date = ndb.DateProperty(required=True)
    source_shift_hour = ndb.IntegerProperty(required=True)

    # Target shift (only for swap types, not for drops or pickups)
    target_shift_date = ndb.DateProperty(default=None)
    target_shift_hour = ndb.IntegerProperty(default=None)

    # The editor occupying the target shift (for swap_direct / swap_add)
    target_editor_id = ndb.StringProperty(default=None)
    target_editor_name = ndb.StringProperty(default=None)

    # Who must approve
    approver_type = ndb.StringProperty(
        required=True,
        choices=["editor", "copy_chief", "none"],
    )
    # If approver_type == "editor", this is that editor's id
    approver_id = ndb.StringProperty(default=None)

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    resolved_at = ndb.DateTimeProperty(default=None)

    # Slack message ID so we can update the approval message later
    slack_message_id = ndb.StringProperty(default=None)
