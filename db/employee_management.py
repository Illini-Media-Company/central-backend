"""
This file defines the EmployeeCard, PositionCard and EmployeePositionRelation
classes used for the Employee Management System. All database calls relevant
to the EMS must be located inside of this file. Classes should not be accessed
anywhere else in the codebase without the use of helper functions.

Created by Jacob Slabosz on Jan. 4, 2026
Last modified Jan. 13, 2026
"""

from google.cloud import ndb
from .user import User
from datetime import datetime, date
from zoneinfo import ZoneInfo
from flask_login import current_user

from constants import (
    IMC_BRANDS,
    PAY_TYPES,
    EMPLOYEE_STATUS_OPTIONS,
    DEPART_CATEGORIES,
    DEPART_REASON_VOL,
    DEPART_REASON_INVOL,
    DEPART_REASON_ADMIN,
)

from . import client


class EmployeeCard(ndb.Model):
    """
    Describes an individual employee. Stores all information relevant to
    the employee in general, not specific to any one position (this is instead
    stored in EmployeePositionRelation). Stores all relevant administrative,
    HR and payroll information for an employee.

    Attributes:
        `uid` (`int`): The unique ID for this employee
        `user_key` (`ndb.KeyProperty`): The User class object for the employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `full_name` (`str`): The employee's full name (automatically computed)
        `imc_email` (`str`): The employee's IMC email address
        `personal_email` (`str`): The employee's personal (non-IMC) email address
        `phone_number` (`str`): The employee's personal phone number
        `permanent_address_1` (`str`): The employee's permanent street address (number & street)
        `permanent_address_2` (`str`): The employee's permanent street address (suite, apartment, etc.)
        `permanent_city` (`str`): The employee's permanent city
        `permanent_state` (`str`): The employee's permanent state
        `permanent_zip` (`str`): The employee's permanent ZIP code
        `birth_date` (`date`): The employee's date of birth
        `payroll_number` (`int`): The employee's payroll number (if applicable)
        `initial_hire_date` (`date`): The date that the employee was first hired
        `status` (`str`): The employee's current status
        `created_at` (`datetime`): When this employee was created
        `updated_at` (`datetime`): When this employee was last edited
        `updated_by` (`str`): User who last updated the employee
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    user_key = ndb.KeyProperty(kind="User")
    last_name = ndb.StringProperty()
    first_name = ndb.StringProperty()
    full_name = ndb.ComputedProperty(
        lambda self: f"{self.first_name} {self.last_name}".strip()
    )

    imc_email = ndb.StringProperty()
    personal_email = ndb.StringProperty()
    phone_number = ndb.StringProperty()

    permanent_address_1 = ndb.StringProperty()
    permanent_address_2 = ndb.StringProperty()
    permanent_city = ndb.StringProperty()
    permanent_state = ndb.StringProperty()
    permanent_zip = ndb.StringProperty()

    birth_date = ndb.DateProperty()

    payroll_number = ndb.IntegerProperty()

    initial_hire_date = ndb.DateProperty()
    status = ndb.StringProperty(choices=EMPLOYEE_STATUS_OPTIONS, default="active")

    created_at = ndb.DateTimeProperty(
        auto_now_add=True, tzinfo=ZoneInfo("America/Chicago")
    )
    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
    updated_by = ndb.StringProperty()


class PositionCard(ndb.Model):
    """
    Describes a position. Only stores general information applicable to any and
    all employees who currently or will hold this position. Does not store
    information specific to any one employee.

    Attributes:
        `uid` (`int`): The unique ID for this position
        `title` (`str`): The title of the position
        `job_description` (`str`): A link to the description for this position
        `brand` (`str`): What brand this position falls under
        `pay_status` (`str`): How this position is paid
        `pay_rate` (`float`): The amount this position is paid per hour/stipend/year
        `supervisors` (`list`): What position(s) this position directly reports to
        `direct_reports` (`list`): What position(s) directly report to this position
        `created_at` (`datetime`): When this position was created
        `updated_at` (`datetime`): When this position was last edited
        `updated_by` (`str`): User who last updated the employee
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    title = ndb.StringProperty()
    job_description = ndb.StringProperty()
    brand = ndb.StringProperty(choices=IMC_BRANDS, default="imc")

    pay_status = ndb.StringProperty(choices=PAY_TYPES, default="unpaid")
    pay_rate = ndb.FloatProperty(default=0.0)

    supervisors = ndb.KeyProperty(kind="PositionCard", repeated=True)
    direct_reports = ndb.KeyProperty(kind="PositionCard", repeated=True)

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    updated_by = ndb.StringProperty()


class EmployeePositionRelation(ndb.Model):
    """
    Describes the relationship between an EmployeeCard and a PositionCard class.
    Ties one user to one position and holds information specific to that person's
    employment that is not generalized for the position. There can exist multiple
    EmployeePositionRelation entries for one EmployeeCard, to represent the
    different positions that an employee has held over time. There can exist multiple
    EmployeePositionRelation entries for one PositionCard, to represent the
    different employees that have held that position over time.

    Attributes:
        `uid` (`int`): The unique ID for this position relationship
        `position` (`ndb.KeyProperty`): The position that is held by the employee
        `employee` (`ndb.KeyProperty`): The employee that holds the position
        `start_date` (`date`): The date that the employee started in the position
        `end_date` (`date`): The date that the employee finished in the position
        `departure_category` (`str`): General category for why the employee is no longer in this position
        `departure_reason` (`str`): Specific reason for why the employee is no longer in this position
        `departure_notes` (`str`): Notes for why the employee is no longer in this position
        `created_at` (`datetime`): When this relation was created
        `updated_at` (`datetime`): When this relation was last edited
        `updated_by` (`str`): User who last updated the relation
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    position = ndb.KeyProperty(kind="PositionCard", required=True)
    employee = ndb.KeyProperty(kind="EmployeeCard", required=True)

    start_date = ndb.DateProperty()
    end_date = ndb.DateProperty()

    departure_category = ndb.StringProperty(
        choices=DEPART_CATEGORIES, default="administrative"
    )
    departure_reason = ndb.StringProperty(
        choices=DEPART_REASON_VOL + DEPART_REASON_INVOL + DEPART_REASON_ADMIN,
        default="other/unknown",
    )
    departure_notes = ndb.StringProperty()

    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    updated_by = ndb.StringProperty()


################################################################################
### EMPLOYEE CARD FUNCTIONS ####################################################
################################################################################


def create_employee_card(**kwargs: dict) -> dict | int | None:
    """
    Creates a new EmployeeCard object. All fields are optional.

    Arguments:
        `user_key` (`ndb.KeyProperty`): The key of the User associated with this employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `imc_email` (`str`): The employee's IMC email address
        `personal_email` (`str`): The employee's personal (non-IMC) email address
        `phone_number` (`str`): The employee's personal phone number
        `permanent_address_1` (`str`): The employee's permanent street address (number & street)
        `permanent_address_2` (`str`): The employee's permanent street address (suite, apartment, etc.)
        `permanent_city` (`str`): The employee's permanent city
        `permanent_state` (`str`): The employee's permanent state
        `permanent_zip` (`str`): The employee's permanent ZIP code
        `birth_date` (`date`): The employee's date of birth
        `payroll_number` (`int`): The employee's payroll number (if applicable)
        `initial_hire_date` (`date`): The date that the employee was first hired
        `status` (`str`): The employee's current status

    Returns:
        `dict`: The created `EmployeeCard` as a dictionary, `None` if an employee already
                exists, or `-1` on other error
    """
    with client.context():
        if "imc_email" in kwargs:
            existing = EmployeeCard.query(
                EmployeeCard.imc_email == kwargs["imc_email"]
            ).get()
            if existing:
                return None  # Employee with this IMC email already exists

        try:
            employee = EmployeeCard(**kwargs)
            employee.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_by = current_user.email if current_user else "system"
            employee.put()
            return employee.to_dict()
        except Exception as e:
            print(f"Error creating EmployeeCard: {e}")
            return -1  # Return -1 if employee creation fails


def modify_employee_card(uid: int, **kwargs: dict) -> dict | None:
    """
    Modifies an existing EmployeeCard object. `uid` is required, all other
    fields are optional.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to modify
        `user_key` (`ndb.KeyProperty`): The key of the User associated with this employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `imc_email` (`str`): The employee's IMC email address
        `personal_email` (`str`): The employee's personal (non-IMC) email address
        `phone_number` (`str`): The employee's personal phone number
        `permanent_address_1` (`str`): The employee's permanent street address (number & street)
        `permanent_address_2` (`str`): The employee's permanent street address (suite, apartment, etc.)
        `permanent_city` (`str`): The employee's permanent city
        `permanent_state` (`str`): The employee's permanent state
        `permanent_zip` (`str`): The employee's permanent ZIP code
        `birth_date` (`date`): The employee's date of birth
        `payroll_number` (`int`): The employee's payroll number (if applicable)
        `initial_hire_date` (`date`): The date that the employee was first hired
        `status` (`str`): The employee's current status

    Returns:
        `dict`: The modified `EmployeeCard` as a dictionary, or `None` if not found
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return None

        for key, value in kwargs.items():
            if hasattr(employee, key):
                setattr(employee, key, value)

        employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
        employee.updated_by = current_user.email if current_user else "system"
        employee.put()
        return employee.to_dict()


def get_employee_card_by_id(uid: int) -> dict | None:
    """
    Retrieves an EmployeeCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to retrieve
    Returns:
        `dict`: The `EmployeeCard` as a dictionary, or `None` if not found
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        return employee.to_dict() if employee else None


def get_all_employee_cards() -> list:
    """
    Retrieves all EmployeeCard entries in the database.

    Returns:
        `list`: A list of all `EmployeeCard` entries as dictionaries
    """
    with client.context():
        employees = EmployeeCard.query().fetch()
        return [employee.to_dict() for employee in employees]


################################################################################


# NEED TO COMPLETE
def link_employee_to_user(employee_key, user_key):
    """
    Docstring for link_employee_to_user

    :param employee_key: Description
    :param user_key: Description
    :returns: Description
    """
    with client.context():
        # Link the User to the EmployeeCard
        employee = employee_key.get()
        if employee:
            employee.user_key = user_key
            employee.put()

            # Link the EmployeeCard to the User

            return True
        return False
