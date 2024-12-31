from google.cloud import ndb
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.background import BackgroundScheduler

from . import client

scheduler = BackgroundScheduler()
scheduler.start()

class MapPoint(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    lat = ndb.FloatProperty()
    long = ndb.FloatProperty()
    url = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()
    start_date = ndb.DateTimeProperty()
    end_date = ndb.DateTimeProperty()

def add_point(lat, long, url, start_date, end_date):
    with client.context():
        point = MapPoint(lat=lat, long=long, url=url, created_at=datetime.now(), start_date=start_date, end_date=end_date)
        point.put()

    scheduler.add_job(remove_point, DateTrigger(run_date=end_date), args=[point.uid])
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

#Sorted by Start Date
def get_next_points(count):
    with client.context():
        points = [
            point.to_dict()
            for point in MapPoint.query().order(MapPoint.start_date).fetch(limit=count)
        ]
    return points

def center_val():
    with client.context():
        points = [point.to_dict() for point in MapPoint.query().fetch()]

    lat_center = 0
    long_center = 0
    count = len(points)

    for point in points:
        lat_center += point["lat"]
        long_center += point["long"]

    lat_center = lat_center / count
    long_center = long_center / count

    return [lat_center, long_center]