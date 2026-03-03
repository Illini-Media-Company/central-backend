from google.cloud import ndb
from datetime import datetime, timezone
import random

from . import client


class CalendarObject(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    lat = ndb.FloatProperty()
    long = ndb.FloatProperty()
    title = ndb.StringProperty()
    url = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()
    start_date = ndb.DateTimeProperty()
    end_date = ndb.DateTimeProperty()
    image = ndb.StringProperty()
    address = ndb.StringProperty()
    event_type = ndb.StringProperty()
    description = ndb.StringProperty()
    company_name = ndb.StringProperty()
    is_accepted = ndb.BooleanProperty()


#Adds a new event along with jitter for duplicate lat-long values
def add_event(title, lat, long, url, start_date, end_date, image, address, event_type, description, company_name):
    with client.context():
        existing = CalendarObject.query(CalendarObject.lat == lat, CalendarObject.long == long).get()

        if existing:
            # Apply small random offset until its lat-long is unique
            # This helps avoid overlapping points on the actual map display
            while True:
                lat_jitter = lat + random.uniform(-0.0001, 0.0001)
                long_jitter = long + random.uniform(-0.0001, 0.0001)

                duplicate = CalendarObject.query(
                    CalendarObject.lat == lat_jitter, CalendarObject.long == long_jitter
                ).get()

                if not duplicate:
                    lat, long = lat_jitter, long_jitter
                    break

        new_event = CalendarObject(
            title=title,
            lat=lat,
            long=long,
            url=url,
            created_at=datetime.now(timezone.utc),
            start_date=start_date,
            end_date=end_date,
            image=image,
            address=address,
            event_type=event_type,
            description=description,
            company_name=company_name,
            is_accepted=False,  
        )
        new_event.put()

        return new_event.to_dict()

#delete an event by uid
def remove_event(uid):
    with client.context():
        event = CalendarObject.get_by_id(int(uid))

        if event is not None:
            print("Removing event:", event.title)
            event.key.delete()
            return True
        else:
            return False

#return all events
def get_all_events():
    with client.context():
        events = [event.to_dict() for event in CalendarObject.query().fetch()]
    return events    

# get count newest events
def get_recent_events(count):
    with client.context():
        events = [
            event.to_dict()
            for event in CalendarObject.query().order(-CalendarObject.created_at).fetch(limit=count)
        ]
    return events


#change an event by uid, and set is_accepted to false so that it needs to be re-approved after changes are made
def change_event(uid, title, lat, long, url, start_date, end_date, image, address, event_type, description, company_name):
    with client.context():
        point = CalendarObject.get_by_id(int(uid))

        if point is not None:
            point.title = title
            point.lat = lat
            point.long = long
            point.url = url
            point.start_date = start_date
            point.end_date = end_date
            point.image = image
            point.address = address
            point.event_type = event_type
            point.description = description
            point.company_name = company_name
            point.is_accepted = False  
            point.put()
            return True
        else:
            return False


# get only accepted events that are in the future, sorted by start date
def get_future_public_events():
    now = datetime.now(timezone.utc)

    with client.context():
        query = (
            CalendarObject.query(CalendarObject.is_accepted == True)
            .filter(CalendarObject.end_date > now) 
            .order(CalendarObject.end_date) 
            .order(CalendarObject.start_date)
        )

        events = [event.to_dict() for event in query.fetch()]

    return events
    
#for map centering 
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

#remove any events that have passed 
def delete_expired_events():
    with client.context():
        now = datetime.now(timezone.utc)
        query = CalendarObject.query(CalendarObject.end_date < now)
        
        keys_to_delete = [event.key for event in query.fetch()]
        if keys_to_delete:
            ndb.delete_multi(keys_to_delete)

#get all events pending approval 
def get_pending_events():
    with client.context():
        query = CalendarObject.query(CalendarObject.is_accepted == False)
        return [event.to_dict() for event in query.fetch()]

#accept an event
def accept_event(uid):
    with client.context():
        point = CalendarObject.get_by_id(int(uid))

        if point is not None:
            point.is_accepted = True
            point.put()
            return True
        else:
            return False

#get an event by uid
def get_event_by_id(uid):
    with client.context():
        event = CalendarObject.get_by_id(int(uid))
        return event.to_dict() if event else None