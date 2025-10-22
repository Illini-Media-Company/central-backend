from datetime import datetime
from zoneinfo import ZoneInfo
from google.cloud import ndb

from . import client


class PhotoRequest(ndb.Model):
    """Datastore model for one photo request.

    Use the `uid` for all lookups, updates, and front-end calls.
    """

    # Unique identifier for this specific request
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    # Submitter information
    submitterEmail = ndb.StringProperty(required=True)
    submitterName = ndb.StringProperty(required=True)

    # Target destination & DI department
    destination = ndb.StringProperty(required=True)  # e.g., DI, Illio, WPGU, Other
    department = ndb.StringProperty(required=False)  # if destination is DI, which desk?

    # Request details
    memo = ndb.StringProperty(required=True)  # short headline / blurb
    specificDetails = ndb.StringProperty(required=True)
    referenceURL = ndb.StringProperty(required=False)
    dueDate = ndb.DateProperty(tzinfo=ZoneInfo("America/Chicago"), required=True)
    moreInfo = ndb.StringProperty(required=False)

    # Whether the photo is a courtesy
    isCourtesy = ndb.BooleanProperty(required=True)

    # Event information (if applicable)
    specificEvent = ndb.BooleanProperty(required=False)
    eventDateTime = ndb.DateTimeProperty(required=False)
    eventLocation = ndb.StringProperty(required=False)
    pressPass = ndb.BooleanProperty(required=False)
    pressPassRequester = ndb.StringProperty(required=False)

    # Assignment and completion
    photogEmail = ndb.StringProperty()
    photogName = ndb.StringProperty()
    claimTimestamp = ndb.DateTimeProperty()
    completedTimestamp = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    driveURL = ndb.StringProperty()

    # Timestamps
    submissionTimestamp = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))


def add_photo_request(
    submitterEmail,
    submitterName,
    destination,
    department,
    memo,
    specificDetails,
    referenceURL,
    dueDate,
    moreInfo,
    isCourtesy,
    specificEvent,
    eventLocation,
    pressPass,
    pressPassRequester,
    eventDateTime=None,
):
    """Create and store a new PhotoRequest.

    Returns: dict representation including `uid` (unique request identifier).
    """
    print("Adding new photo request to db...")
    with client.context():
        entity = PhotoRequest(
            submissionTimestamp=datetime.now(ZoneInfo("America/Chicago")),
            submitterEmail=submitterEmail,
            submitterName=submitterName,
            destination=destination,
            department=department,
            memo=memo,
            specificDetails=specificDetails,
            referenceURL=referenceURL,
            dueDate=dueDate,
            moreInfo=moreInfo,
            isCourtesy=isCourtesy,
            specificEvent=specificEvent,
            eventDateTime=eventDateTime,
            eventLocation=eventLocation,
            pressPass=pressPass,
            pressPassRequester=pressPassRequester,
        )
        entity.put()
        print("Photo request added.")
        return entity.to_dict()


def get_all_photo_requests():
    """Return all requests (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query().fetch().order(PhotoRequest.submissionTimestamp).fetch()
        )

    return [request.to_dict() for request in requests]


def get_unclaimed_photo_requests():
    """Return all unclaimed requests (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.claimTimestamp == None)
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_claimed_photo_requests():
    """Return all claimed requests (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.claimTimestamp != None)
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_completed_photo_requests():
    """Return all completed requests (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.completedTimestamp != None)
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_inprogress_photo_requests():
    """Return all requests that are claimed but not complete (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(
                PhotoRequest.claimTimestamp != None,
                PhotoRequest.completedTimestamp == None,
            )
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_claimed_photo_requests_for_user(email):
    """Return all requests that were claimed by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.photogEmail == email)
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_completed_photo_requests_for_user(email):
    """Return all requests that were completed by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(
                PhotoRequest.photogEmail == email,
                PhotoRequest.completedTimestamp != None,
            )
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_submitted_photo_requests_for_user(email):
    """Return all requests that were submitted by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.submitterEmail == email)
            .fetch()
            .order(PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_most_recent_photo_request():
    """Return the single most recent request by submissionTimestamp (or None)."""
    with client.context():
        pr = PhotoRequest.query().order(-PhotoRequest.submissionTimestamp).get()
        return pr.to_dict() if pr else None


def get_photo_request_by_uid(uid):
    """Lookup a PhotoRequest by its unique UID (entity id)."""
    with client.context():
        pr = PhotoRequest.get_by_id(uid)
        return pr.to_dict() if pr else None


def update_photo_request(uid, **fields):
    """Update a PhotoRequest by its UID.

    Only passed fields are changed. Unknown field names are ignored.
    Returns updated dict or None if not found.
    """
    with client.context():
        entity = PhotoRequest.get_by_id(uid)
        if entity is None:
            return None
        for key, value in fields.items():
            if hasattr(entity, key):
                if key == "eventDateTime":
                    value = datetime.strptime(value, "%Y-%m-%dT%H:%M")
                if key == "dueDate":
                    value = datetime.strptime(value, "%Y-%m-%d")
                setattr(entity, key, value)
        entity.put()
        return entity.to_dict()


def claim_photo_request(uid, photogName, photogEmail):
    """Streamlined helper to claim a photo request.

    Sets photogName, photogEmail, and claimTimestamp to now.
    Returns updated dict, or None if uid not found.
    """
    with client.context():
        entity = PhotoRequest.get_by_id(uid)
        if entity is None:
            return None
        entity.photogName = photogName
        entity.photogEmail = photogEmail
        entity.claimTimestamp = datetime.now(ZoneInfo("America/Chicago"))
        entity.put()
        return entity.to_dict()


def complete_photo_request(uid, driveURL):
    """Streamlined helper to complete a request with a Drive URL.

    Sets driveURL and completedTimestamp to now.
    Returns updated dict, or None if uid not found.
    """
    with client.context():
        entity = PhotoRequest.get_by_id(uid)
        if entity is None:
            return None
        entity.driveURL = driveURL
        entity.completedTimestamp = datetime.now(ZoneInfo("America/Chicago"))
        entity.put()
        return entity.to_dict()


def delete_photo_request(uid):
    """Delete a single PhotoRequest by UID.

    Returns True if deleted, False if not found.
    """
    with client.context():
        entity = PhotoRequest.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return True


def delete_all_photo_requests():
    """Deletes all PhotoRequest entities. Be careful."""
    with client.context():
        requests = PhotoRequest.query().fetch()
        for r in requests:
            r.key.delete()
