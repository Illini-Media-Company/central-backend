"""
This file defines the EmployeeCard, PositionCard and EmployeePositionRelation
classes used for the Employee Management System. All database calls relevant
to the EMS must be located inside of this file. Classes should not be accessed
anywhere else in the codebase without the use of helper functions.

Created by Jacob Slabosz on Jan. 4, 2026
Last modified Jan. 23, 2026
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
    EMPLOYEE_GRAD_YEARS,
    EMPLOYEE_PRONOUNS,
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
        `user_uid` (`int`): The UID of the User class object for the employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `full_name` (`str`): The employee's full name (automatically computed)
        `pronouns` (`str`): The employee's pronouns
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
        `major` (`str`): The employee's major
        `major_2` (`str`): The employee's (optional) second major
        `major_3` (`str`): The employee's (optional) third major
        `minor` (`str`): The employee's minor
        `minor_2` (`str`): The employee's (optional) second minor
        `minor_3` (`str`): The employee's (optional) third minor
        `graduation` (`str`): The employee's expected graduation term
        `created_at` (`datetime`): When this employee was created
        `updated_at` (`datetime`): When this employee was last edited
        `updated_by` (`str`): User who last updated the employee
    """

    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    user_uid = ndb.IntegerProperty()
    last_name = ndb.StringProperty()
    first_name = ndb.StringProperty()
    full_name = ndb.ComputedProperty(
        lambda self: f"{self.first_name} {self.last_name}".strip()
    )
    pronouns = ndb.StringProperty(choices=EMPLOYEE_PRONOUNS)

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

    major = ndb.StringProperty()
    major_2 = ndb.StringProperty()
    major_3 = ndb.StringProperty()
    minor = ndb.StringProperty()
    minor_2 = ndb.StringProperty()
    minor_3 = ndb.StringProperty()
    graduation = ndb.StringProperty(choices=EMPLOYEE_GRAD_YEARS)

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
        `supervisors` (`list[int]`): UIDs of position(s) this position directly reports to
        `direct_reports` (`list[int]`): UIDs of position(s) directly report to this position
        `archived` (`bool`): Whether this position is archived (no longer in use)
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

    supervisors = ndb.IntegerProperty(repeated=True)
    direct_reports = ndb.IntegerProperty(repeated=True)

    archived = ndb.BooleanProperty(default=False)

    created_at = ndb.DateTimeProperty(
        auto_now_add=True, tzinfo=ZoneInfo("America/Chicago")
    )
    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
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
        `user_uid` (`int`): The UID of the User associated with this employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `pronouns` (`str`): The employee's pronouns
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
        `major` (`str`): The employee's major
        `major_2` (`str`): The employee's (optional) second major
        `major_3` (`str`): The employee's (optional) third major
        `minor` (`str`): The employee's minor
        `minor_2` (`str`): The employee's (optional) second minor
        `minor_3` (`str`): The employee's (optional) third minor
        `graduation` (`str`): The employee's expected graduation term

    Returns:
        `dict`: The created `EmployeeCard` as a dictionary, `None` if an employee already
                exists with the given `imc_email`, or `-1` on other error
    """
    with client.context():
        if "imc_email" in kwargs:
            existing = EmployeeCard.query(
                EmployeeCard.imc_email == kwargs["imc_email"]
            ).get()
            if existing:
                return None  # Employee with this IMC email already exists

        try:
            if "user_uid" in kwargs:
                user = User.get_by_id(kwargs["user_uid"])
                if not user:
                    return -1  # User with this UID does not exist

            employee = EmployeeCard(**kwargs)
            employee.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_by = current_user.email if current_user else "System"
            employee.put()

            temp = employee.uid
            tie_employee_to_user(temp)
            employee = EmployeeCard.get_by_id(temp)

            return employee.to_dict()
        except Exception as e:
            print(f"Error creating EmployeeCard: {e}")
            return -1  # Return -1 if employee creation fails


def modify_employee_card(uid: int, **kwargs: dict) -> dict | None | int:
    """
    Modifies an existing EmployeeCard object. `uid` is required, all other
    fields are optional.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to modify
        `user_uid` (`int`): The UID of the User associated with this employee
        `last_name` (`str`): The employee's last name
        `first_name` (`str`): The employee's first name
        `pronouns` (`str`): The employee's pronouns
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
        `major` (`str`): The employee's major
        `major_2` (`str`): The employee's (optional) second major
        `major_3` (`str`): The employee's (optional) third major
        `minor` (`str`): The employee's minor
        `minor_2` (`str`): The employee's (optional) second minor
        `minor_3` (`str`): The employee's (optional) third minor
        `graduation` (`str`): The employee's expected graduation term

    Returns:
        `dict`: The modified `EmployeeCard` as a dictionary, `None` if not found,
                `-1` if the provided `user_uid` does not correspond to an existing User,
                or `-2` if another employee already exists with the given `imc_email`
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return None

        if "user_uid" in kwargs:
            user = User.get_by_id(kwargs["user_uid"])
            if not user:
                return -1  # User with this UID does not exist

        if "imc_email" in kwargs:
            existing = EmployeeCard.query(
                EmployeeCard.imc_email == kwargs["imc_email"]
            ).get()

            is_duplicate = any(item.key != employee.key for item in [existing] if item)

            if is_duplicate:
                return -2  # Employee with this IMC email already exists

        for key, value in kwargs.items():
            if hasattr(employee, key):
                setattr(employee, key, value)

        employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
        employee.updated_by = current_user.email if current_user else "System"
        employee.put()

        # Re-tie the employee to the user in case the email changed
        temp = employee.uid
        tie_employee_to_user(temp)
        employee = EmployeeCard.get_by_id(temp)

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
        employees = (
            EmployeeCard.query()
            .order(EmployeeCard.last_name, EmployeeCard.first_name)
            .fetch()
        )
        return [employee.to_dict() for employee in employees]


def delete_employee_card(uid: int) -> bool | None:
    """
    Deletes an EmployeeCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to delete

    Returns:
        `bool`: `True` if deletion was successful, `False` if not found, `None` on error
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return False  # Employee not found

        try:
            employee.key.delete()
            return True
        except Exception as e:
            print(f"Error deleting EmployeeCard: {e}")
            return None  # Return None if deletion fails


def tie_employee_to_user(uid: int) -> bool | None:
    """
    Links an EmployeeCard to a User by their UIDs. Must be called within a
    client context.

    Arguments:
        `uid` (`int`): The UID of the EmployeeCard

    Returns:
        `bool`: `True` if linking was successful, `False` if either entity not found,
                `None` on error
    """
    employee = EmployeeCard.get_by_id(uid)
    user = User.query(User.email == employee.imc_email).get() if employee else None

    if not employee or not user:
        return False  # Either Employee or User not found

    try:
        employee.user_uid = user.key.id()
        employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
        employee.updated_by = current_user.email if current_user else "System"
        employee.put()
        return True
    except Exception as e:
        print(f"Error linking EmployeeCard to User: {e}")
        return None  # Return None if linking fails


################################################################################


################################################################################
### POSITION CARD FUNCTIONS ####################################################
################################################################################


def create_position_card(**kwargs: dict) -> dict | int | None:
    """
    Creates a new PositionCard object. All fields are optional.

    Arguments:
        `title` (`str`): The title of the position
        `job_description` (`str`): A link to the description for this position
        `brand` (`str`): What brand this position falls under
        `pay_status` (`str`): How this position is paid
        `pay_rate` (`float`): The amount this position is paid per hour/stipend/year
        `supervisors` (`list[int]`): UIDs of the position(s) this position directly reports to

    Returns:
        `dict`: The created `PositionCard` as a dictionary, `None` if a position already
                exists with the given `brand` and `title`, or `-1` on other error
    """
    with client.context():
        if "brand" in kwargs and "title" in kwargs:
            existing = PositionCard.query(
                ndb.AND(
                    PositionCard.brand == kwargs["brand"],
                    PositionCard.title == kwargs["title"],
                )
            ).get()
            if existing:
                return None  # Position with this brand and title already exists

        try:
            # Convert supervisor and direct report UIDs to keys
            if "supervisors" in kwargs:
                kwargs["supervisors"] = [int(uid) for uid in kwargs["supervisors"]]

            position = PositionCard(**kwargs)
            position.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()

            # Add this position to direct reports of its supervisors
            for supervisor_uid in position.supervisors:
                supervisor = PositionCard.get_by_id(supervisor_uid)
                if supervisor:
                    if position.uid not in supervisor.direct_reports:
                        supervisor.direct_reports = supervisor.direct_reports or []
                        supervisor.direct_reports.append(position.uid)
                        supervisor.updated_at = datetime.now(
                            tz=ZoneInfo("America/Chicago")
                        )
                        supervisor.updated_by = "System"
                        supervisor.put()

            return position.to_dict()
        except Exception as e:
            print(f"Error creating PositionCard: {e}")
            return -1  # Return -1 if position creation fails


def modify_position_card(uid: int, **kwargs: dict) -> dict | None:
    """
    Modifies an existing PositionCard object. `uid` is required, all other
    fields are optional.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to modify
        `title` (`str`): The title of the position
        `job_description` (`str`): A link to the description for this position
        `brand` (`str`): What brand this position falls under
        `pay_status` (`str`): How this position is paid
        `pay_rate` (`float`): The amount this position is paid per hour/stipend/year
        `supervisors` (`list[int]`): UIDs of the position(s) this position directly reports to

    Returns:
        `dict`: The modified `PositionCard` as a dictionary, `None` if not found,
                `-1` if there exists another position with the same `brand` and `title`,
                or `-2` if updating supervisors fails
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return None

        # Check if a position already exists with the given brand and title
        if "brand" in kwargs and "title" in kwargs:
            existing = PositionCard.query(
                ndb.AND(
                    PositionCard.brand == kwargs["brand"],
                    PositionCard.title == kwargs["title"],
                )
            ).get()

            is_duplicate = any(item.key != position.key for item in [existing] if item)

            if is_duplicate:
                return -1  # Position with this brand and title already exists

        try:
            # Update the supervisor(s)
            if "supervisors" in kwargs:
                old_sups = set(position.supervisors or [])
                new_sups = set(int(uid) for uid in kwargs["supervisors"] or [])

                removed = old_sups - new_sups
                added = new_sups - old_sups

                for sup_uid in removed:
                    supervisor = PositionCard.get_by_id(sup_uid)
                    if supervisor and position.uid in supervisor.direct_reports:
                        supervisor.direct_reports.remove(position.uid)
                        supervisor.updated_at = datetime.now(
                            tz=ZoneInfo("America/Chicago")
                        )
                        supervisor.updated_by = "System"
                        supervisor.put()

                for sup_uid in added:
                    supervisor = PositionCard.get_by_id(sup_uid)
                    if supervisor:
                        if position.uid not in supervisor.direct_reports:
                            supervisor.direct_reports = supervisor.direct_reports or []
                            supervisor.direct_reports.append(position.uid)
                            supervisor.updated_at = datetime.now(
                                tz=ZoneInfo("America/Chicago")
                            )
                            supervisor.updated_by = "System"
                            supervisor.put()
        except Exception as e:
            print(f"Error updating supervisors for PositionCard: {e}")
            return -2  # Return -2 if updating supervisors fails

        for key, value in kwargs.items():
            if hasattr(position, key):
                setattr(position, key, value)

        position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
        position.updated_by = current_user.email if current_user else "System"
        position.put()
        return position.to_dict()


def get_all_position_cards() -> list:
    """
    Retrieves all PositionCard entries in the database.

    Returns:
        `list`: A list of all `PositionCard` entries as dictionaries
    """
    with client.context():
        positions = (
            PositionCard.query().order(PositionCard.brand, PositionCard.title).fetch()
        )
        return [position.to_dict() for position in positions]


def get_position_card_by_id(uid: int) -> dict | None:
    """
    Retrieves a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to retrieve
    Returns:
        `dict`: The `PositionCard` as a dictionary, or `None` if not found
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        return position.to_dict() if position else None


def delete_position_card(uid: int) -> bool | None:
    """
    Deletes a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to delete

    Returns:
        `bool`: `True` if deletion was successful, `False` if not found, `None` on error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return False  # Position not found

        try:
            # Remove this position from supervisors' direct reports
            for supervisor_uid in position.supervisors:
                supervisor = PositionCard.get_by_id(supervisor_uid)
                if supervisor and position.uid in supervisor.direct_reports:
                    supervisor.direct_reports.remove(position.uid)
                    supervisor.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
                    supervisor.updated_by = "System"
                    supervisor.put()

            # Remove this position from direct reports' supervisors
            for report_uid in position.direct_reports:
                report = PositionCard.get_by_id(report_uid)
                if report and position.uid in report.supervisors:
                    report.supervisors.remove(position.uid)
                    report.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
                    report.updated_by = "System"
                    report.put()

            position.key.delete()
            return True
        except Exception as e:
            print(f"Error deleting PositionCard: {e}")
            return None  # Return None if deletion fails


def archive_position_card(uid: int) -> bool | None:
    """
    Archives a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to archive

    Returns:
        `bool`: `True` if archiving was successful, `False` if not found, `None` on error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return False  # Position not found

        try:
            position.archived = True
            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()
            return True
        except Exception as e:
            print(f"Error archiving PositionCard: {e}")
            return None  # Return None if archiving fails


def restore_position_card(uid: int) -> bool | None:
    """
    Restores an archived PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to restore

    Returns:
        `bool`: `True` if restoring was successful, `False` if not found, `None` on error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return False  # Position not found

        try:
            position.archived = False
            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()
            return True
        except Exception as e:
            print(f"Error restoring PositionCard: {e}")
            return None  # Return None if restoring fails


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
