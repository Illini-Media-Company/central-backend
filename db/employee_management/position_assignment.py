from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo

from . import client
from .employee_card import EmployeeCard
from .position_type import PositionType


# Information for a specific employee's assignment to a position
class PositionAssignment(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    employee = ndb.KeyProperty(kind=EmployeeCard, required=True)
    position_type = ndb.KeyProperty(kind=PositionType, required=True)

    start_date = ndb.DateProperty()
    end_date = ndb.DateProperty()


####################################################################################################################################


# Create a new position assignment for an employee (existing employee ID and position type ID)
def create_position_assignment(
    employee_id, position_type_id, start_date, end_date=None
):
    employee_key = ndb.Key(EmployeeCard, employee_id)
    position_type_key = ndb.Key(PositionType, position_type_id)

    assignment = PositionAssignment(
        employee=employee_key,
        position_type=position_type_key,
        start_date=start_date,
        end_date=end_date,
    )
    assignment.put()

    employee_key.get().cur_positions.append(assignment.key)
    employee_key.get().put()

    return assignment


# Close a position assignment for an employee
#   Set the end_date and move it from cur_positions to past_positions
def close_position_assignment(assignment_uid, end_date):
    assignment_key = ndb.Key(PositionAssignment, assignment_uid)
    assignment = assignment_key.get()

    if assignment:
        assignment.end_date = end_date
        assignment.put()

        employee = assignment.employee.get()
        if assignment.key in employee.cur_positions:
            employee.cur_positions.remove(assignment.key)
            employee.past_positions.append(assignment.key)
            employee.put()

        return True
    else:
        return False
