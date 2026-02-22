from google.cloud import ndb
from . import client


class CopyEditorAdmin(ndb.Model):
    uid = ndb.ComputedProperty(lambda self: self.key.id() if self.key else None)
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty(required=True)


def add_copy_editor(name, email):
    """
    Docstring for add_copy_editor

    :param name: Description
    :param email: Description
    """
    print("Adding new copy editor to db...")

    with client.context():
        entity = CopyEditorAdmin(
            name=name,
            email=email,
        )
        entity.put()
        print("Copy editor added.")
        return entity.to_dict()


def get_all_copy_editors():
    """Returns all copy editors."""
    with client.context():
        requests = CopyEditorAdmin.query().fetch()

    return [request.to_dict() for request in requests]


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

    Returns the deleted entity if deleted, False if not found.
    """
    with client.context():
        entity = CopyEditorAdmin.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return entity.to_dict()


class CopyShift(ndb.Model):
    uid = ndb.ComputedProperty(lambda self: self.key.id() if self.key else None)
    day_of_week = ndb.IntegerProperty(required=True)
    shift_number = ndb.IntegerProperty(required=True)
    editor_email = ndb.StringProperty(required=False)


def add_shift(day, shift, email):
    """Add shift to database."""
    print("Adding new shift to db...")

    with client.context():
        entity = CopyShift(
            day_of_week=day,
            shift_number=shift,
            editor_email=email,
        )
        entity.put()
        print("Shift added.")
        return entity.to_dict()


def get_all_shifts():
    """Returns all shifts."""
    with client.context():
        requests = CopyShift.query().fetch()

    return [request.to_dict() for request in requests]


def get_shift_by_uid(uid):
    """Lookup a shift by its unique UID (entity id)."""
    with client.context():
        shift = CopyShift.get_by_id(uid)
        return shift.to_dict() if shift else None


def update_shift(uid, **fields):
    """Update a shift by its UID.

    Only passed fields are changed. Unknown field names are ignored.
    Returns updated dict or None if not found.
    """
    with client.context():
        entity = CopyShift.get_by_id(uid)
        if entity is None:
            return None
        for key, value in fields.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        entity.put()
        return entity.to_dict()


def delete_shift(uid):
    """Delete a single shift by UID.

    Returns the deleted entity if deleted, False if not found.
    """
    with client.context():
        entity = CopyShift.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return entity.to_dict()
