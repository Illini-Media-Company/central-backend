from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo

from . import client


# Information for a specific position
class PositionType(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    title = ndb.StringProperty()
    pay_status = ndb.StringProperty(
        choices=["unpaid", "hourly", "salary", "stipend"], default="unpaid"
    )
    brand = ndb.StringProperty(
        choices=["imc", "di", "wpgu", "illio", "chambana-eats", "ics"], default="imc"
    )
    supervisors = ndb.KeyProperty(kind="PositionType", repeated=True)
    direct_reports = ndb.KeyProperty(kind="PositionType", repeated=True)


####################################################################################################################################


# Create a new position type
def create_position_type(title, pay_status, brand, supervisors, direct_reports):
    if supervisors is None:
        supervisors = []
    if direct_reports is None:
        direct_reports = []

    position = PositionType(
        title=title,
        pay_status=pay_status,
        brand=brand,
        supervisors=supervisors,
        direct_reports=direct_reports,
    )
    position.put()
    return position
