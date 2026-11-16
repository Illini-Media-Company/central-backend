"""
This file defines the Equipment and CheckoutEntry classes used for the
equipment tracker (the in-house replacement for AssetTiger). All database calls
relevant to the equipment tracker must be located inside of this file. Classes
should not be accessed anywhere else in the codebase without the use of helper
functions.

Created by Gus Nophaket on Nov. 16, 2026
Last modified Nov. 16, 2026
"""

from zoneinfo import ZoneInfo

from google.cloud import ndb

from constants import EQUIPMENT_STATUSES

from . import client

CHICAGO_TZ = ZoneInfo("America/Chicago")


def _validate_nonnegative(prop, value):
    if value is not None and value < 0:
        raise ValueError(f"{prop._name} cannot be negative")
    return value


class CheckoutEntry(ndb.Model):
    """
    One checkout of an Equipment item. Stored inside Equipment.history, not as
    its own Datastore kind. The returned_* fields stay empty until the item is
    returned.

    Attributes:
        `borrower_name` (`str`): Name of the person who has the item
        `borrower_email` (`str`): IMC email of the person who has the item
        `checked_out_at` (`datetime`): When the item was checked out
        `checked_out_by` (`str`): Email of the staff member who processed the checkout
        `returned_at` (`datetime`): When the item was returned (None while checked out)
        `returned_by` (`str`): Email of the staff member who processed the return
    """

    borrower_name = ndb.StringProperty(required=True)
    borrower_email = ndb.StringProperty(required=True)
    checked_out_at = ndb.DateTimeProperty(required=True, tzinfo=CHICAGO_TZ)
    checked_out_by = ndb.StringProperty(required=True)
    returned_at = ndb.DateTimeProperty(tzinfo=CHICAGO_TZ)
    returned_by = ndb.StringProperty()


class Equipment(ndb.Model):
    """
    One barcoded item or kit. The key id is the barcode ID printed on the label
    (e.g. "IMC-00123"), so two items can never share a barcode ID.

    The current borrower (if status is "checked_out") or the most recent
    borrower (if "available") is the last entry in history.

    Attributes:
        `barcode_id` (`str`): The barcode ID (mirrors the key id)
        `name` (`str`): Item or kit name
        `description` (`str`): Optional details, such as model or serial number
        `is_kit` (`bool`): Whether this record is a kit
        `kit_contents` (`list[str]`): Items in the kit (empty if not a kit)
        `value` (`float`): Total value (sum of contents for a kit)
        `replacement_cost` (`float`): Cost to replace, if different from value
        `purchase_date` (`date`): When it was bought
        `purchase_location` (`str`): Store or vendor
        `purchase_url` (`str`): Optional purchase website
        `status` (`str`): One of EQUIPMENT_STATUSES
        `history` (`list[CheckoutEntry]`): Checkouts, oldest first
        `created_at` (`datetime`): When this record was created
        `updated_at` (`datetime`): When this record was last edited
        `updated_by` (`str`): Email of the staff member who made the last change
    """

    barcode_id = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()

    is_kit = ndb.BooleanProperty(default=False)
    kit_contents = ndb.StringProperty(repeated=True)

    value = ndb.FloatProperty(validator=_validate_nonnegative)
    replacement_cost = ndb.FloatProperty(validator=_validate_nonnegative)

    purchase_date = ndb.DateProperty()
    purchase_location = ndb.StringProperty()
    purchase_url = ndb.StringProperty()

    status = ndb.StringProperty(choices=EQUIPMENT_STATUSES, default="available")
    # Stored as embedded entities: history is never queried, only read with
    # the item, so it doesn't need indexes
    history = ndb.LocalStructuredProperty(CheckoutEntry, repeated=True)

    created_at = ndb.DateTimeProperty(auto_now_add=True, tzinfo=CHICAGO_TZ)
    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=CHICAGO_TZ)
    updated_by = ndb.StringProperty()
