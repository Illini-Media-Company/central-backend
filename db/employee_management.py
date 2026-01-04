# This file defines the EmployeeCard, PositionCard and EmployeePositionRelation
# classes used for the Employee Management System. All database calls relevant
# to the EMS must be located inside of this file. Classes should not be accessed
# anywhere else in the codebase without the use of helper functions.
#
# Created by Jacob Slabosz on Jan. 4, 2026
# Last modified Jan. 4, 2026

from google.cloud import ndb
from .user import User

from constants import (
    IMC_BRANDS,
    PAY_TYPES,
    DEPART_CATEGORIES,
    DEPART_REASON_VOL,
    DEPART_REASON_INVOL,
    DEPART_REASON_ADMIN,
)


# Describes an individual employee. Stores all information relevant to
# the employee in general, not specific to any one position (this is instead
# stored in EmployeePositionRelation). Stores all relevant administrative,
# HR and payroll information for an employee.
class EmployeeCard(ndb.Model):
    # The unique ID for this employee
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    # The User class object for the employee
    user_key = ndb.KeyProperty(kind=User, required=True)

    # The employee's last name
    last_name = ndb.StringProperty()

    # The employee's first name
    first_name = ndb.StringProperty()

    # The employee's full name (automatically computed)
    full_name = ndb.ComputedProperty(
        lambda self: f"{self.first_name} {self.last_name}".strip()
    )

    # The employee's personal (non-IMC) email address
    personal_email = ndb.StringProperty()

    # The employee's personal phone number
    phone_number = ndb.StringProperty()

    # The employee's permanent street address (number & street)
    permanent_address = ndb.StringProperty()

    # The employee's permanent city
    permanent_city = ndb.StringProperty()

    # The employee's permanent state
    permanent_state = ndb.StringProperty()

    # The employee's permanent ZIP code
    permanent_zip = ndb.StringProperty()

    # The employee's date of birth
    birth_date = ndb.DateProperty()

    # The employee's payroll number (if applicable)
    payroll_number = ndb.IntegerProperty()

    # The date that the employee was first hired
    initial_hire_date = ndb.DateProperty()

    # The employee's current status
    status = ndb.StringProperty(
        choices=["active", "inactive", "onboarding", "offboarding"], default="active"
    )

    # When this employee was created
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    # When this employee was last edited
    updated_at = ndb.DateTimeProperty(auto_now=True)


# Describes a position. Only stores general information applicable to any and
# all employees who currently or will hold this position.
class PositionCard(ndb.Model):
    # The unique ID for this position
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    # The title of the position
    title = ndb.StringProperty()

    # How this position is paid
    pay_status = ndb.StringProperty(choices=PAY_TYPES, default="unpaid")

    # The amount this position is paid per hour/stipend/year
    pay_rate = ndb.FloatProperty(default=0.0)

    # What brand this position falls under
    brand = ndb.StringProperty(choices=IMC_BRANDS, default="imc")

    # What position(s) this position directly reports to
    supervisors = ndb.KeyProperty(kind="PositionCard", repeated=True)

    # What position(s) directly report to this position
    direct_reports = ndb.KeyProperty(kind="PositionCard", repeated=True)

    # A link to the description for this position
    job_description = ndb.StringProperty()

    # When this position was created
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    # When this position was last edited
    updated_at = ndb.DateTimeProperty(auto_now=True)


# Describes a relation between an EmployeeCard class and a PositionCard class.
# Ties one user to one position and holds information specific to that person's
# employment that is not generalized for the position.
class EmployeePositionRelation(ndb.Model):
    # The unique ID for this position relationship
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    # The position that is held by the employee
    position = ndb.KeyProperty(kind="PositionCard", required=True)

    # The employee that holds the position
    employee = ndb.KeyProperty(kind="EmployeeCard", required=True)

    # The date that the employee started in the position
    start_date = ndb.DateProperty()

    # The date that the employee finished in the position
    end_date = ndb.DateProperty()

    # General category for why the employee is no longer in this position
    departure_category = ndb.StringProperty(
        choices=DEPART_CATEGORIES, default="administrative"
    )

    # Specific reason for why the employee is no longer in this position
    departure_reason = ndb.StringProperty(
        choices=DEPART_REASON_VOL + DEPART_REASON_INVOL + DEPART_REASON_ADMIN,
        default="other/unknown",
    )

    # Notes for why the employee is no longer in this position
    departure_notes = ndb.StringProperty()

    # When this relation was created
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    # When this relation was last edited
    updated_at = ndb.DateTimeProperty(auto_now=True)
