"""
Photo request database models and operations.

Handles storing and retrieving photo requests that staff submit.
Tracks the full lifecycle: submission -> claim -> completion.

Created on Oct. 15, 2025 by Jon Hogg
Last modified Nov. 8, 2025
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from google.cloud import ndb

from util.helpers.email_to_slackid import email_to_slackid

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
    submitterSlackId = ndb.StringProperty(required=True)
    submitSlackChannel = ndb.StringProperty()
    submitSlackTs = ndb.StringProperty()

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

    # Photographer that claimed the request
    photogEmail = ndb.StringProperty()
    photogName = ndb.StringProperty()
    photogSlackId = ndb.StringProperty()
    claimTimestamp = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    claimSlackChannel = ndb.StringProperty()
    claimSlackTs = ndb.StringProperty()

    completedTimestamp = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    driveURL = ndb.StringProperty()

    # Slack metadata for updating the original channel post
    slackChannel = ndb.StringProperty()
    slackTs = ndb.StringProperty()

    # Simple workflow state
    status = ndb.StringProperty(
        choices=["submitted", "claimed", "completed"], default="submitted"
    )

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
    """
    Creates a new photo request in the database.

    Args:
        submitterEmail: Email of person submitting the request
        submitterName: Name of submitter
        destination: Where the photo is going (DI, Illio, WPGU, etc.)
        department: If DI, which desk (news, sports, etc.)
        memo: Short headline or description
        specificDetails: More detailed info about the request
        referenceURL: Optional link to related story/content
        dueDate: When the photos are needed (date object)
        moreInfo: Any additional notes
        isCourtesy: Whether this is a courtesy photo
        specificEvent: If this is for a specific event
        eventLocation: Where the event is
        pressPass: Whether a press pass is needed
        pressPassRequester: Who should request the press pass
        eventDateTime: When the event is (if applicable)

    Returns:
        Dict with all the request data including the uid
    """
    print("Adding new photo request to db...")
    with client.context():
        entity = PhotoRequest(
            submissionTimestamp=datetime.now(ZoneInfo("America/Chicago")),
            submitterEmail=submitterEmail,
            submitterSlackId=email_to_slackid(submitterEmail),
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
    """Returns all photo requests, newest first."""
    with client.context():
        requests = PhotoRequest.query().order(-PhotoRequest.submissionTimestamp).fetch()

    return [request.to_dict() for request in requests]


def get_unclaimed_photo_requests():
    """Return all unclaimed requests (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.claimTimestamp == None)
            .order(-PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_claimed_photo_requests():
    """Return all claimed requests (ordered by submission date)."""
    with client.context():
        requests = PhotoRequest.query().order(-PhotoRequest.submissionTimestamp).fetch()

    return [
        request.to_dict() for request in requests if request.claimTimestamp is not None
    ]


def get_completed_photo_requests():
    """Return all completed requests (ordered by submission date)."""
    with client.context():
        requests = PhotoRequest.query().order(-PhotoRequest.submissionTimestamp).fetch()

    return [
        request.to_dict()
        for request in requests
        if request.completedTimestamp is not None
    ]


def get_inprogress_photo_requests():
    """Return all requests that are claimed but not complete (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query()
            .filter(PhotoRequest.completedTimestamp == None)
            .order(-PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [
        request.to_dict() for request in requests if request.claimTimestamp is not None
    ]


def get_claimed_photo_requests_for_user(email):
    """Return all requests that were claimed by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.photogEmail == email)
            .order(-PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [request.to_dict() for request in requests]


def get_completed_photo_requests_for_user(email):
    """Return all requests that were completed by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.photogEmail == email)
            .order(-PhotoRequest.submissionTimestamp)
            .fetch()
        )

    return [
        request.to_dict()
        for request in requests
        if request.completedTimestamp is not None
    ]


def get_submitted_photo_requests_for_user(email):
    """Return all requests that were submitted by a specified email (ordered by submission date)."""
    with client.context():
        requests = (
            PhotoRequest.query(PhotoRequest.submitterEmail == email)
            .order(-PhotoRequest.submissionTimestamp)
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
        entity.photogSlackId = email_to_slackid(photogEmail)
        entity.claimTimestamp = datetime.now(ZoneInfo("America/Chicago"))
        entity.status = "claimed"
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
        entity.status = "completed"
        entity.put()
        return entity.to_dict()


def get_id_from_slack_claim_ts(ch, thread_ts):
    """
    Finds a photo request by its Slack claim channel and thread timestamp.

    Args:
        ch: Slack channel ID where the claim happened
        thread_ts: Slack thread timestamp of the claim message

    Returns:
        Dict of the request if found, None otherwise
    """
    with client.context():
        req = PhotoRequest.query(
            PhotoRequest.claimSlackChannel == ch, PhotoRequest.claimSlackTs == thread_ts
        ).get()

        if req:
            return req.to_dict()
        return None


def delete_photo_request(uid):
    """Delete a single PhotoRequest by UID.

    Returns the deleted entity if deleted, False if not found.
    """
    with client.context():
        entity = PhotoRequest.get_by_id(uid)
        if entity is None:
            return False
        entity.key.delete()
        return entity.to_dict()


def delete_all_photo_requests():
    """Deletes all PhotoRequest entities. Be careful."""
    with client.context():
        requests = PhotoRequest.query().fetch()
        for r in requests:
            r.key.delete()
