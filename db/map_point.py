from google.cloud import ndb
from datetime import datetime, timedelta, timezone
import random

from . import client


class MapPoint(ndb.Model):
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
    point_type = ndb.StringProperty()


def add_point(title, lat, long, url, start_date, end_date, image, address, point_type):
    # check if this is a duplicate location
    with client.context():
        existing = MapPoint.query(MapPoint.lat == lat, MapPoint.long == long).get()

    if existing:
        # Apply small random offset until it's lat-long is unique
        # This helps avoid overlapping points on the actual map display
        while True:
            lat_jitter = lat + random.uniform(-0.0001, 0.0001)
            long_jitter = long + random.uniform(-0.0001, 0.0001)

            with client.context():
                duplicate = MapPoint.query(
                    MapPoint.lat == lat_jitter, MapPoint.long == long_jitter
                ).get()

            if not duplicate:
                lat, long = lat_jitter, long_jitter
                break

    with client.context():
        point = MapPoint(
            title=title,
            lat=lat,
            long=long,
            url=url,
            created_at=datetime.now(),
            start_date=start_date,
            end_date=end_date,
            image=image,
            address=address,
            point_type=point_type,
        )
        point.put()

    return point.to_dict()


def remove_point(uid):
    with client.context():
        point = MapPoint.get_by_id(uid)
        print("Removing point on date", point.url)

        if point is not None:
            point.key.delete()
            return True
        else:
            return False


def get_all_points():
    with client.context():
        points = [point.to_dict() for point in MapPoint.query().fetch()]
    return points


def get_recent_points(count):
    with client.context():
        points = [
            point.to_dict()
            for point in MapPoint.query().order(-MapPoint.created_at).fetch(limit=count)
        ]
    return points


# Sorted by Start Date
def get_next_points(count):
    with client.context():
        points = [
            point.to_dict()
            for point in MapPoint.query().order(MapPoint.start_date).fetch(limit=count)
        ]
    return points


def get_future_points():
    now = datetime.now()

    with client.context():
        query = (
            MapPoint.query()
            .filter(MapPoint.end_date > now)  # inequality filter
            .order(MapPoint.end_date)  # first order must match inequality
            .order(MapPoint.start_date)  # now sort by start date
        )

        points = [point.to_dict() for point in query.fetch()]

    return points


def center_val():
    points = get_future_points()

    if len(points) == 0:
        return [40.109337703305975, -88.22721514717438]

    lat_center = 0
    long_center = 0
    count = len(points)

    for point in points:
        lat_center += point["lat"]
        long_center += point["long"]

    lat_center = lat_center / count
    long_center = long_center / count

    return [lat_center, long_center]
