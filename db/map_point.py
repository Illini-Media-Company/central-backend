from google.cloud import ndb
from datetime import datetime, timedelta

from . import client


class MapPoint(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    x = ndb.FloatProperty()
    y = ndb.FloatProperty()
    url = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()


def add_point(x, y, url):
    with client.context():
        point = MapPoint(x=x, y=y, url=url, created_at=datetime.now())
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
