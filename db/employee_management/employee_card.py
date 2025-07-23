from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo

from . import client


# Information for an employee
class EmployeeCard(ndb.Model):
    employee_id = ndb.IntegerProperty(required=True)
    last_name = ndb.StringProperty()
    first_name = ndb.StringProperty()


# Keeps track of the next available employee ID number
class Counter(ndb.Model):
    name = ndb.StringProperty(required=True)
    value = ndb.IntegerProperty(default=100000)


# Get the next available employee ID number
@ndb.transactional()
def get_next_employee_id():
    counter_key = ndb.Key(Counter, "employee_id")
    counter = counter_key.get()
    if counter is None:
        counter = Counter(key=counter_key, name="employee_id", value=100000)
    else:
        counter.value += 1
    counter.put()
    return counter.value
