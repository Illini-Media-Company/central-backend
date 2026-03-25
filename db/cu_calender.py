from google.cloud import ndb
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from util.cu_calendar import delete_images_from_gcs
from . import client


class CalendarObject(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    lat = ndb.FloatProperty()
    long = ndb.FloatProperty()
    title = ndb.StringProperty()
    url = ndb.StringProperty()
    created_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    start_date = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    end_date = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    images = ndb.StringProperty(repeated=True)
    address = ndb.StringProperty()
    event_type = ndb.StringProperty()
    description = ndb.StringProperty()
    company_name = ndb.StringProperty()
    submitter_name = ndb.StringProperty(default="")
    submitter_email = ndb.StringProperty(default="")
    is_accepted = ndb.BooleanProperty()
    highlight = ndb.BooleanProperty(default=False)


class CalendarSource(ndb.Model):
    """Stores Google Calendar URLs and company names for re-checking/syncing."""

    gcal_id = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    gcal_url = ndb.StringProperty(required=True)
    company_name = ndb.StringProperty(default="")
    created_at = ndb.DateTimeProperty()


# Adds a new event along with 
def add_event(
    title,
    lat,
    long,
    url,
    start_date,
    end_date,
    images,
    address,
    event_type,
    description,
    company_name,
    submitter_name="",
    submitter_email="",
    is_accepted=False,
    highlight=False,
):
    with client.context():
        new_event = CalendarObject(
            title=title,
            lat=lat,
            long=long,
            url=url,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            start_date=start_date,
            end_date=end_date,
            images=images or [],
            address=address,
            event_type=event_type,
            description=description,
            company_name=company_name,
            submitter_name=(submitter_name or "").strip(),
            submitter_email=(submitter_email or "").strip(),
            is_accepted=is_accepted,
            highlight=highlight,
        )
        new_event.put()
        return new_event.to_dict()


# delete an event by uid
def remove_event(uid):
    with client.context():
        event = CalendarObject.get_by_id(int(uid))
        if event is not None:
            print("Removing event:", event.title)
            if event.images:
                print("Deleting associated images from GCS...")
                delete_images_from_gcs(event.images)

            event.key.delete()
            return True
        else:
            return False


# return all events
def get_all_events():
    with client.context():
        events = [event.to_dict() for event in CalendarObject.query().fetch()]
    return events


# get count newest events
def get_recent_events(count):
    with client.context():
        events = [
            event.to_dict()
            for event in CalendarObject.query()
            .order(-CalendarObject.created_at)
            .fetch(limit=count)
        ]
    return events


# change an event by uid, and set is_accepted to false so that it needs to be re-approved after changes are made
def change_event(
    uid,
    title,
    lat,
    long,
    url,
    start_date,
    end_date,
    images,
    address,
    event_type,
    description,
    company_name,
    submitter_name=None,
    submitter_email=None,
):
    with client.context():
        point = CalendarObject.get_by_id(int(uid))
        if point is not None:
            point.title = title
            point.lat = lat
            point.long = long
            point.url = url
            point.start_date = start_date
            point.end_date = end_date
            point.images = images
            point.address = address
            point.event_type = event_type
            point.description = description
            point.company_name = company_name
            if submitter_name is not None:
                point.submitter_name = (submitter_name or "").strip()
            if submitter_email is not None:
                point.submitter_email = (submitter_email or "").strip()
            point.is_accepted = False
            point.highlight = False
            point.put()
            return True
        else:
            return False


# get only accepted events that are in the future, sorted by start date
def get_future_public_events():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with client.context():
        query = (
            CalendarObject.query(CalendarObject.is_accepted == True)
            .filter(CalendarObject.end_date > now)
            .order(CalendarObject.end_date)
            .order(CalendarObject.start_date)
        )
        events = [event.to_dict() for event in query.fetch()]
    return events


# for map centering
def center_val():
    events = get_future_public_events()
    if len(events) == 0:
        return [40.109337703305975, -88.22721514717438]
    lat_center = 0
    long_center = 0
    count = len(events)
    for event in events:
        lat_center += event["lat"]
        long_center += event["long"]
    lat_center = lat_center / count
    long_center = long_center / count
    return [lat_center, long_center]


# remove any events that have passed
def delete_expired_events():
    with client.context():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        query = CalendarObject.query(CalendarObject.end_date < now)
        keys_to_delete = [event.key for event in query.fetch()]
        if keys_to_delete:
            ndb.delete_multi(keys_to_delete)


# get all events pending approval
def get_pending_events():
    with client.context():
        query = CalendarObject.query(CalendarObject.is_accepted == False)
        return [event.to_dict() for event in query.fetch()]


# accept an event
def accept_event(uid, lat, long):
    with client.context():
        point = CalendarObject.get_by_id(int(uid))
        if point is not None:
            point.lat = lat
            point.long = long
            point.is_accepted = True
            point.put()
            return True
        else:
            return False


# get an event by uid
def get_event_by_id(uid):
    with client.context():
        event = CalendarObject.get_by_id(int(uid))
        return event.to_dict() if event else None


def highlight_event(uid):
    with client.context():
        event = CalendarObject.get_by_id(int(uid))
        if event is not None:
            event.highlight = True
            event.is_accepted = True
            event.put()
            return True
        else:
            return False


# check if an event already exists
def event_exists(gcal_url, title, start_date):
    with client.context():
        existing = CalendarObject.query(
            CalendarObject.url == gcal_url,
            CalendarObject.title == title,
            CalendarObject.start_date == start_date,
        ).get()
        return existing is not None


# CalendarSource CRUD operations (stores gcal_url + company_name for re-checking)


def add_calendar_source(gcal_url, company_name=""):
    """Create a new CalendarSource record."""
    with client.context():
        source = CalendarSource(
            gcal_url=gcal_url.strip(),
            company_name=(company_name or "").strip(),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        source.put()
        return source.to_dict()


def get_all_calendar_sources():
    """Get all calendar sources, ordered by created_at descending."""
    with client.context():
        sources = [
            s.to_dict()
            for s in CalendarSource.query().order(-CalendarSource.created_at).fetch()
        ]
        return sources


def get_calendar_source_by_id(uid):
    """Get a calendar source by uid."""
    with client.context():
        source = CalendarSource.get_by_id(int(uid))
        return source.to_dict() if source else None


def update_calendar_source(uid, gcal_url=None, company_name=None):
    """Update a calendar source by uid."""
    with client.context():
        source = CalendarSource.get_by_id(int(uid))
        if source is None:
            return None
        if gcal_url is not None:
            source.gcal_url = gcal_url.strip()
        if company_name is not None:
            source.company_name = company_name.strip()
        source.put()
        return source.to_dict()


def remove_calendar_source(uid):
    """Delete a calendar source by uid."""
    with client.context():
        source = CalendarSource.get_by_id(int(uid))
        if source is None:
            return False
        source.key.delete()
        return True
