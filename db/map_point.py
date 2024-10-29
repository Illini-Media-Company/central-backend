from google.cloud import ndb
from datetime import datetime, timedelta

from . import client


class MapPoint(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    lat = ndb.FloatProperty()
    long = ndb.FloatProperty()
    url = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()


def add_point(lat, long, url):
    with client.context():
        point = MapPoint(lat=lat, long=long, url=url, created_at=datetime.now())
        point.put()
    return point.to_dict()


def remove_point(uid):
    with client.context():
        point = MapPoint.get_by_id(uid)
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
