"""
This file defines the Equipment and CheckoutEntry classes used for the
equipment tracker (the in-house replacement for AssetTiger). All database calls
relevant to the equipment tracker must be located inside of this file. Classes
should not be accessed anywhere else in the codebase without the use of helper
functions.

Created by Gus Nophaket on Nov. 16, 2026
Last modified Nov. 16, 2026
"""

import contextlib
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from google.cloud import ndb

from constants import (
    EQUIPMENT_BARCODE_DIGITS,
    EQUIPMENT_BARCODE_PREFIX,
    EQUIPMENT_STATUSES,
)

from . import client

CHICAGO_TZ = ZoneInfo("America/Chicago")

# Fields that can be set on create and changed with update_equipment.
# barcode_id, status and history are deliberately not editable: status and
# history only change through check_out/return/retire/restore.
EDITABLE_FIELDS = {
    "name",
    "description",
    "is_kit",
    "kit_contents",
    "value",
    "replacement_cost",
    "purchase_date",
    "purchase_location",
    "purchase_url",
}

# How many random barcode IDs to try before giving up
_MAX_GENERATE_ATTEMPTS = 20


################################################################################
#################################### ERRORS ####################################
################################################################################


class EquipmentError(Exception):
    """Base class for equipment tracker errors."""


class EquipmentNotFound(EquipmentError):
    def __init__(self, barcode_id):
        self.barcode_id = barcode_id
        super().__init__(f"No equipment with barcode ID {barcode_id}.")


class DuplicateBarcodeId(EquipmentError):
    def __init__(self, barcode_id):
        self.barcode_id = barcode_id
        super().__init__(f"Barcode ID {barcode_id} is already in use.")


class AlreadyCheckedOut(EquipmentError):
    """Raised when checking out (or retiring) an item someone already has."""

    def __init__(self, barcode_id, borrower_name, borrower_email):
        self.barcode_id = barcode_id
        self.borrower_name = borrower_name
        self.borrower_email = borrower_email
        super().__init__(
            f"{barcode_id} is checked out to {borrower_name} ({borrower_email})."
        )


class NotCheckedOut(EquipmentError):
    def __init__(self, barcode_id):
        self.barcode_id = barcode_id
        super().__init__(f"{barcode_id} is not checked out.")


class EquipmentRetired(EquipmentError):
    def __init__(self, barcode_id):
        self.barcode_id = barcode_id
        super().__init__(f"{barcode_id} is retired and can't be checked out.")


################################################################################
#################################### MODELS ####################################
################################################################################


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

    def to_dict(self):
        return {
            "borrower_name": self.borrower_name,
            "borrower_email": self.borrower_email,
            "checked_out_at": self.checked_out_at,
            "checked_out_by": self.checked_out_by,
            "returned_at": self.returned_at,
            "returned_by": self.returned_by,
        }


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

    @property
    def last_entry(self):
        """The newest CheckoutEntry, or None if never checked out."""
        return self.history[-1] if self.history else None

    def to_dict(self):
        """
        Plain dict of the item for routes. Dates stay native date/datetime
        objects; the route converts them to ISO strings when building the
        response. `borrower`, `checked_out_at` and `returned_at` come from the
        newest history entry: the current borrower if status is
        "checked_out", otherwise the most recent one (None if never checked
        out).
        """
        last = self.last_entry
        return {
            "barcode_id": self.barcode_id,
            "name": self.name,
            "description": self.description,
            "is_kit": self.is_kit,
            "kit_contents": list(self.kit_contents),
            "value": self.value,
            "replacement_cost": self.replacement_cost,
            "purchase_date": self.purchase_date,
            "purchase_location": self.purchase_location,
            "purchase_url": self.purchase_url,
            "status": self.status,
            "borrower": (
                {"name": last.borrower_name, "email": last.borrower_email}
                if last
                else None
            ),
            "checked_out_at": last.checked_out_at if last else None,
            "returned_at": last.returned_at if last else None,
            "history": [entry.to_dict() for entry in self.history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
        }


################################################################################
################################### HELPERS ####################################
################################################################################


def _db_context():
    """Open an ndb context unless the caller already has one."""
    if ndb.get_context(False) is not None:
        return contextlib.nullcontext()
    return client.context()


def normalize_barcode_id(barcode_id):
    """Trim whitespace from a scanned or typed barcode ID. Case is kept."""
    barcode_id = (barcode_id or "").strip()
    if not barcode_id:
        raise ValueError("Barcode ID cannot be empty.")
    return barcode_id


def _require(value, field):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required.")
    return value


def _check_fields(fields):
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Fields can't be set this way: {', '.join(sorted(unknown))}")


def _random_barcode_id():
    number = secrets.randbelow(10**EQUIPMENT_BARCODE_DIGITS)
    return f"{EQUIPMENT_BARCODE_PREFIX}{number:0{EQUIPMENT_BARCODE_DIGITS}d}"


def _get_or_raise(barcode_id):
    item = Equipment.get_by_id(barcode_id)
    if item is None:
        raise EquipmentNotFound(barcode_id)
    return item


################################################################################
#################################### CREATE ####################################
################################################################################


@ndb.transactional()
def _insert_if_absent(barcode_id, updated_by, fields):
    if Equipment.get_by_id(barcode_id) is not None:
        return None
    item = Equipment(id=barcode_id, updated_by=updated_by, **fields)
    item.put()
    return item


def create_equipment(updated_by, barcode_id=None, **fields):
    """
    Adds a new item. Pass `barcode_id` for an item that already has a label
    (e.g. during migration); leave it out to generate a random unused
    IMC-xxxxx ID for a brand-new item.

    Arguments:
        `updated_by` (`str`): Email of the staff member adding the item
        `barcode_id` (`str`, optional): Existing label's barcode ID
        `**fields`: Any of EDITABLE_FIELDS (`name` is required)

    Returns:
        `Equipment`: The created item

    Raises:
        `DuplicateBarcodeId`: The given barcode ID is already in use
        `ValueError`: Missing name or a field that can't be set
    """
    updated_by = _require(updated_by, "updated_by")
    _check_fields(fields)
    fields["name"] = _require(fields.get("name"), "name")

    with _db_context():
        if barcode_id is not None:
            barcode_id = normalize_barcode_id(barcode_id)
            item = _insert_if_absent(barcode_id, updated_by, fields)
            if item is None:
                raise DuplicateBarcodeId(barcode_id)
            return item

        for _ in range(_MAX_GENERATE_ATTEMPTS):
            item = _insert_if_absent(_random_barcode_id(), updated_by, fields)
            if item is not None:
                return item
        raise EquipmentError("Couldn't generate an unused barcode ID. Try again.")


################################################################################
##################################### READ #####################################
################################################################################


def get_equipment(barcode_id):
    """Returns the Equipment with this barcode ID (retired included), or None."""
    barcode_id = normalize_barcode_id(barcode_id)
    with _db_context():
        return Equipment.get_by_id(barcode_id)


def list_equipment(include_retired=False):
    """
    Returns all equipment sorted by name. Retired items are left out unless
    `include_retired` is True. Filters in Python so no composite index is
    needed; fine for an inventory of a few thousand items.
    """
    with _db_context():
        items = Equipment.query().fetch()
    if not include_retired:
        items = [item for item in items if item.status != "retired"]
    return sorted(items, key=lambda item: (item.name or "").lower())


################################################################################
#################################### UPDATE ####################################
################################################################################


@ndb.transactional()
def _update(barcode_id, updated_by, fields):
    item = _get_or_raise(barcode_id)
    for field, value in fields.items():
        setattr(item, field, value)
    item.updated_by = updated_by
    item.put()
    return item


def update_equipment(barcode_id, updated_by, **fields):
    """
    Edits an item's details. Only EDITABLE_FIELDS can change; the barcode ID,
    status and history can't. Runs in a transaction so it can't overwrite a
    checkout that happens at the same time.

    Raises:
        `EquipmentNotFound`: No item with this barcode ID
        `ValueError`: A field that can't be edited, or an empty name
    """
    barcode_id = normalize_barcode_id(barcode_id)
    updated_by = _require(updated_by, "updated_by")
    _check_fields(fields)
    if "name" in fields:
        fields["name"] = _require(fields["name"], "name")
    with _db_context():
        return _update(barcode_id, updated_by, fields)


################################################################################
############################## CHECK OUT / RETURN ##############################
################################################################################


@ndb.transactional()
def _check_out(barcode_id, borrower_name, borrower_email, processed_by):
    item = _get_or_raise(barcode_id)
    if item.status == "retired":
        raise EquipmentRetired(barcode_id)
    if item.status == "checked_out":
        last = item.last_entry
        raise AlreadyCheckedOut(barcode_id, last.borrower_name, last.borrower_email)

    item.history.append(
        CheckoutEntry(
            borrower_name=borrower_name,
            borrower_email=borrower_email,
            checked_out_at=datetime.now(CHICAGO_TZ),
            checked_out_by=processed_by,
        )
    )
    item.status = "checked_out"
    item.updated_by = processed_by
    item.put()
    return item


def check_out_equipment(barcode_id, borrower_name, borrower_email, processed_by):
    """
    Checks an item out to a borrower: adds a history entry and sets status to
    "checked_out" in one transaction, so two people can't check out the same
    item at once. Send the confirmation email after this returns, not before.

    Raises:
        `EquipmentNotFound`: No item with this barcode ID
        `AlreadyCheckedOut`: Someone already has it (includes who)
        `EquipmentRetired`: The item is retired
        `ValueError`: Missing borrower or processed_by
    """
    barcode_id = normalize_barcode_id(barcode_id)
    borrower_name = _require(borrower_name, "borrower_name")
    borrower_email = _require(borrower_email, "borrower_email")
    processed_by = _require(processed_by, "processed_by")
    with _db_context():
        return _check_out(barcode_id, borrower_name, borrower_email, processed_by)


@ndb.transactional()
def _return(barcode_id, processed_by):
    item = _get_or_raise(barcode_id)
    if item.status != "checked_out":
        raise NotCheckedOut(barcode_id)

    last = item.last_entry
    last.returned_at = datetime.now(CHICAGO_TZ)
    last.returned_by = processed_by
    item.status = "available"
    item.updated_by = processed_by
    item.put()
    return item


def return_equipment(barcode_id, processed_by):
    """
    Marks an item returned: fills in returned_at/returned_by on the newest
    history entry and sets status to "available" in one transaction.

    Raises:
        `EquipmentNotFound`: No item with this barcode ID
        `NotCheckedOut`: The item isn't checked out
        `ValueError`: Missing processed_by
    """
    barcode_id = normalize_barcode_id(barcode_id)
    processed_by = _require(processed_by, "processed_by")
    with _db_context():
        return _return(barcode_id, processed_by)


################################################################################
############################### RETIRE / RESTORE ###############################
################################################################################


@ndb.transactional()
def _set_retired(barcode_id, retired, updated_by):
    item = _get_or_raise(barcode_id)
    if retired and item.status == "checked_out":
        last = item.last_entry
        raise AlreadyCheckedOut(barcode_id, last.borrower_name, last.borrower_email)

    target = "retired" if retired else "available"
    current = "available" if retired else "retired"
    if item.status == current:
        item.status = target
        item.updated_by = updated_by
        item.put()
    return item


def retire_equipment(barcode_id, updated_by):
    """
    Retires an item (lost, broken, sold): hides it from the list but keeps its
    history and barcode ID. Does nothing if already retired.

    Raises:
        `EquipmentNotFound`: No item with this barcode ID
        `AlreadyCheckedOut`: Someone has it; return it first
    """
    barcode_id = normalize_barcode_id(barcode_id)
    updated_by = _require(updated_by, "updated_by")
    with _db_context():
        return _set_retired(barcode_id, True, updated_by)


def restore_equipment(barcode_id, updated_by):
    """
    Brings a retired item back as "available". Does nothing if it isn't
    retired.

    Raises:
        `EquipmentNotFound`: No item with this barcode ID
    """
    barcode_id = normalize_barcode_id(barcode_id)
    updated_by = _require(updated_by, "updated_by")
    with _db_context():
        return _set_retired(barcode_id, False, updated_by)
