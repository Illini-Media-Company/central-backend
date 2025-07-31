from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo

from . import client


# Information for an employee
class EmployeeCard(ndb.Model):
    employee_id = ndb.IntegerProperty(required=True)
    last_name = ndb.StringProperty()
    first_name = ndb.StringProperty()
    full_name = ndb.ComputedProperty(
        lambda self: f"{self.first_name} {self.last_name}".strip()
    )
    imc_email = ndb.StringProperty()
    phone = ndb.StringProperty()
    personal_email = ndb.StringProperty()
    hire_date = ndb.DateProperty()
    departure_date = ndb.DateProperty()
    departure_reason = ndb.StringProperty()

    status = ndb.StringProperty(
        choices=["active", "inactive", "onboarding", "offboarding"], default="active"
    )

    cur_positions = ndb.KeyProperty(kind="PositionAssignment", repeated=True)
    past_positions = ndb.KeyProperty(kind="PositionAssignment", repeated=True)


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


####################################################################################################################################


# Create a new employee card
def create_employee(
    last_name,
    first_name,
    imc_email,
    phone,
    personal_email,
    hire_date,
    departure_date=None,
    departure_reason=None,
):
    new_id = get_next_employee_id()

    employee = EmployeeCard(
        id=new_id,
        employee_id=new_id,
        last_name=last_name,
        first_name=first_name,
        imc_email=imc_email,
        phone=phone,
        personal_email=personal_email,
        hire_date=hire_date,
        departure_date=departure_date,
        departure_reason=departure_reason,
    )
    employee.put()
    return employee


####################################################################################################################################


# List all employees
def get_all_employees():
    employees = sorted(
        [employee.to_dict() for employee in EmployeeCard.query().fetch()],
        key=lambda x: x.get("last_name", "").lower(),
    )

    return employees
