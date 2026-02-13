"""
This file defines the EmployeeCard, PositionCard and EmployeePositionRelation
classes used for the Employee Management System. All database calls relevant
to the EMS must be located inside of this file. Classes should not be accessed
anywhere else in the codebase without the use of helper functions.

Created by Jacob Slabosz on Jan. 4, 2026
Last modified Feb. 13, 2026
"""

from google.cloud import ndb
from google.cloud.ndb import exceptions as ndb_exceptions
from db.user import User
from datetime import datetime
from zoneinfo import ZoneInfo
from flask_login import current_user

from util.google_admin import (
    update_group_membership,
    check_group_exists,
)
from util.slackbots.general import can_bot_access_channel, _lookup_user_id_by_email
from util.employee_management import *

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


# Decorator so that we can use functions nested and avoid context errors
def ensure_context(func):
    def wrapper(*args, **kwargs):
        try:
            ctx = ndb.get_context(False)
            if ctx is not None:
                return func(*args, **kwargs)
            raise ndb_exceptions.ContextError()
        except (ndb_exceptions.ContextError, RuntimeError):
            with client.context():
                return func(*args, **kwargs)

    return wrapper


class IMCBrandMapping(ndb.Model):
    name = ndb.StringProperty(required=True)
    slack_channel_id = ndb.StringProperty(required=True)


class AppSettings(ndb.Model):
    brands = ndb.LocalStructuredProperty(IMCBrandMapping, repeated=True)

    @classmethod
    @ensure_context
    def get_settings(cls):
        """ """
        return cls.get_or_insert("global_settings")

    @ensure_context
    def get_brand_list(self) -> list[str]:
        """
        Returns just the brand names.
        """
        return [b.name for b in self.brands]

    @ensure_context
    def get_channel_by_brand(self, brand_name: str) -> str | None:
        """
        Looks up the channel ID for a specific brand.
        """
        for b in self.brands:
            if b.name == brand_name:
                return b.slack_channel_id
        return None


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
        `onboarding_form_done` (`bool`): Whether the employee has filled out the onboarding form
        `onboarding_update_channel` (`str`): The Slack `channel_id` to send updates to
        `onboarding_update_ts` (`str`): The Slack message `ts` of the original message
        `onboarding_complete` (`bool`): Whether the employee has completed onboarding
        `slack_id` ('str'): The employee's Slack ID (Only updated by the system)
        `created_at` (`datetime`): When this employee was created
        `updated_at` (`datetime`): When this employee was last edited
        `updated_by` (`str`): Email of the user who last updated the employee
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
    status = ndb.StringProperty(choices=EMPLOYEE_STATUS_OPTIONS, default="Onboarding")

    major = ndb.StringProperty()
    major_2 = ndb.StringProperty()
    major_3 = ndb.StringProperty()
    minor = ndb.StringProperty()
    minor_2 = ndb.StringProperty()
    minor_3 = ndb.StringProperty()
    graduation = ndb.StringProperty(choices=EMPLOYEE_GRAD_YEARS)

    # To set the status of the onboarding form
    onboarding_form_done = ndb.BooleanProperty(default=False)
    onboarding_update_channel = ndb.StringProperty()
    onboarding_update_ts = ndb.StringProperty()
    onboarding_complete = ndb.BooleanProperty(default=False)

    slack_id = ndb.StringProperty()

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
        `google_group` (`str`): The email for the Google Group that all employees will be added to
        `slack_channels` (`list[str]`): The IDs of the Slack channels that all employees will be added to
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
    brand = ndb.StringProperty(choices=IMC_BRANDS, default="IMC")

    pay_status = ndb.StringProperty(choices=PAY_TYPES, default="Unpaid")
    pay_rate = ndb.FloatProperty(default=0.0)

    supervisors = ndb.IntegerProperty(repeated=True)
    direct_reports = ndb.IntegerProperty(repeated=True)

    google_group = ndb.StringProperty()
    slack_channels = ndb.StringProperty(repeated=True)

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
        `position_id` (`int`): The UID of the position that is held by the employee
        `employee_id` (`int`): The UID of the employee that holds the position
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

    position_id = ndb.IntegerProperty()
    employee_id = ndb.IntegerProperty()

    start_date = ndb.DateProperty()
    end_date = ndb.DateProperty()

    departure_category = ndb.StringProperty(choices=DEPART_CATEGORIES)
    departure_reason = ndb.StringProperty(
        choices=DEPART_REASON_VOL + DEPART_REASON_INVOL + DEPART_REASON_ADMIN
    )
    departure_notes = ndb.StringProperty()

    created_at = ndb.DateTimeProperty(
        auto_now_add=True, tzinfo=ZoneInfo("America/Chicago")
    )
    updated_at = ndb.DateTimeProperty(auto_now=True, tzinfo=ZoneInfo("America/Chicago"))
    updated_by = ndb.StringProperty()


# Set initial default settings
settings = AppSettings.get_settings()
if not settings.brands:
    initial_map = [
        IMCBrandMapping(name="IMC", slack_channel_id="C08D4RYCL13"),
        IMCBrandMapping(name="The Daily Illini", slack_channel_id="C04TB2QH65C"),
        IMCBrandMapping(name="WPGU", slack_channel_id="C0ACRA54EEA"),
        IMCBrandMapping(name="Illio", slack_channel_id="C0ACX015BM2"),
        IMCBrandMapping(name="Chambana Eats", slack_channel_id="C0AED1B6UH5"),
        IMCBrandMapping(name="Illini Content Studio", slack_channel_id="C0AER1Z12FP"),
    ]
    settings.brands = initial_map
    settings.put()


@ensure_context
def get_imc_brand_names() -> list[str]:
    """
    Public helper to get brand names from settings.
    """
    settings = AppSettings.get_settings()
    return settings.get_brand_list()


@ensure_context
def get_slack_channel_id(brand_name: str) -> str | None:
    """
    Public helper to get a specific channel ID by brand name from settings.

    Arguments:
        `brand_name` (`str`): The name of the brand as it appears in settings
    Returns:
        `str`: The `channel_id`, else `None`
    """
    settings = AppSettings.get_settings()
    return settings.get_channel_by_brand(brand_name)


################################################################################
### EMPLOYEE CARD FUNCTIONS ####################################################
################################################################################


def create_employee_onboarding_card(
    first_name: str, last_name: str, onboarding_update_channel: str
) -> dict | int:
    """
    Creates a minimal EmployeeCard for the onboarding workflow.
    This inserts a new employee record with onboarding defaults
    (`status`="Onboarding", `onboarding_form_done`=`False`)

    Arguments:
        `first_name` (`str`): The first name of the employee to onboard
        `last_name` (`str`): The last name of the employee to onboard
        `onboarding_update_channel` (`str`): The Slack `channel_id` to send updates to

    Returns:
        `dict`: The created EmployeeCard as a dictionary

    Raises:
        `EEXCEPT`: An error occurred
    """
    with client.context():
        try:
            employee = EmployeeCard(
                first_name=first_name,
                last_name=last_name,
                status="Onboarding",
                onboarding_form_done=False,
                onboarding_update_channel=onboarding_update_channel,
            )
            employee.initial_hire_date = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_by = current_user.email if current_user else "System"
            employee.put()
            return employee.to_dict()
        except Exception as e:
            print(f"Error creating onboarding EmployeeCard: {e}")
            return EEXCEPT


def update_employee_onboarding_card(uid: int, ts: str) -> dict | int:
    """
    Updates an EmployeeCard to include the Slack ts.

    Arguments:
        `uid` (`int`): The UID of the EmployeeCard
        `ts` (`str`): The Slack ts for the initial onboarding message
    Returns:
        `dict`: The modified EmployeeCard
    Raises:
        `EEMPDNE`: Employee not found
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return EEMPDNE  # Employee not found
        try:
            employee.onboarding_update_ts = ts
            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_by = "System"

            employee.put()

        except Exception as e:
            print(f"Error modifying EmployeeCard: {e}")
            return EEXCEPT  # Employee modification failed


def create_employee_card(**kwargs: dict) -> dict | int:
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
        `dict`: The created `EmployeeCard` as a dictionary

    Raises:
        `EEXISTS`: If an employee already exists with the given `imc_email`
        `EUSERDNE`: If the associated User does not exist
        `EMISSING`: If required fields are missing (`imc_email`)
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        if "imc_email" in kwargs:
            existing = EmployeeCard.query(
                EmployeeCard.imc_email == kwargs["imc_email"]
            ).get()
            if existing:
                return EEXISTS  # Employee with this IMC email already exists
        else:
            return EMISSING  # Missing required field
        try:
            if "user_uid" in kwargs:
                user = User.get_by_id(kwargs["user_uid"])
                if not user:
                    return EUSERDNE
            employee = EmployeeCard(**kwargs)
            employee.slack_id = _lookup_user_id_by_email(employee.imc_email)
            employee.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee.updated_by = current_user.email if current_user else "System"
            employee.put()
            temp = employee.uid
            tie_employee_to_user(employee_uid=temp)
            employee = EmployeeCard.get_by_id(temp)

            return employee.to_dict()
        except Exception as e:
            print(f"Error creating EmployeeCard: {e}")
            return EEXCEPT  # Employee creation failed


def modify_employee_card(uid: int, **kwargs: dict) -> dict | None | int:
    """
    Modifies an existing EmployeeCard object. `uid` is required, all other
    fields are optional. Sets the current time as `updated_at`. Sets
    `updated_by` to the current user's email if modified by an authenticated
    user, to "New Hire" if modified by non-authenticated user, otherwise
    "System".

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
        `slack_id` ('str'): The employee's Slack ID (Only updated by the system)

    Returns:
        `dict`: The modified `EmployeeCard` as a dictionary

    Raises:
        `EEMPDNE`: If not found,
        `EUSERDNE`: If the provided `user_uid` does not correspond to an existing User
        `EEXISTS`: If another employee already exists with the given `imc_email`
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return EEMPDNE  # Employee not found

        try:
            if "user_uid" in kwargs:
                user = User.get_by_id(kwargs["user_uid"])
                if not user:
                    return EUSERDNE  # User with this UID does not exist

            if "imc_email" in kwargs:
                existing = EmployeeCard.query(
                    EmployeeCard.imc_email == kwargs["imc_email"]
                ).get()

                if existing and existing.key != employee.key:
                    return EEXISTS  # Employee with this IMC email already exists

                # Update the employee's Slack ID if it wasn't directly given (only if their email changed)
                if kwargs["imc_email"] != employee.imc_email:
                    if not "slack_id" in kwargs:
                        employee.slack_id = _lookup_user_id_by_email(
                            kwargs["imc_email"]
                        )

            for key, value in kwargs.items():
                if hasattr(employee, key):
                    setattr(employee, key, value)

            employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            if current_user and current_user.is_authenticated:
                employee.updated_by = current_user.email
            elif current_user:
                employee.updated_by = "New Hire"
            else:
                employee.updated_by = "System"
            employee.put()

            # Re-tie the employee to the user in case the email changed
            temp = employee.uid
            tie_employee_to_user(employee_uid=temp)
            employee = EmployeeCard.get_by_id(temp)

            return employee.to_dict()
        except Exception as e:
            print(f"Error modifying EmployeeCard: {e}")
            return EEXCEPT  # Employee modification failed


def get_employee_card_by_id(uid: int) -> dict | int:
    """
    Retrieves an EmployeeCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to retrieve

    Returns:
        `dict`: The `EmployeeCard` as a dictionary

    Raises:
        `EEMPDNE`: If EmployeeCard not found
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        return employee.to_dict() if employee else EEMPDNE


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


def delete_employee_card(uid: int) -> bool | int:
    """
    Deletes an EmployeeCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeeCard to delete

    Returns:
        `bool`: `True` if deletion was successful

    Raises:
        `EEMPDNE`: If employee not found
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        employee = EmployeeCard.get_by_id(uid)
        if not employee:
            return EEMPDNE  # Employee not found

        try:
            # Delete all relations involving this employee
            relations = get_relations_by_employee(employee.uid)
            for relation in relations:
                relation_entity = EmployeePositionRelation.get_by_id(relation["uid"])
                if relation_entity:
                    relation_entity.key.delete()

            employee.key.delete()
            return True
        except Exception as e:
            print(f"Error deleting EmployeeCard: {e}")
            return EEXCEPT  # Deletion failed


@ensure_context
def tie_employee_to_user(employee_uid: int = None, user_uid: int = None) -> bool | int:
    """
    Links an EmployeeCard to a User. Only one argument should be provided

    Arguments:
        `employee_uid` (`int`): The UID of the EmployeeCard
        `user_uid` (`int`): The UID of the User

    Returns:
        `bool`: `True` if linking was successful

    Raises:
        `EUSERDNE`: User does not exist
        `EEMPDNE`: Employee does not exist
        `EEXCEPT`: Other fatal error
    """
    if employee_uid:
        employee = EmployeeCard.get_by_id(employee_uid)
        user = User.query(User.email == employee.imc_email).get() if employee else None
    elif user_uid:
        user = User.get_by_id(user_uid)
        employee = (
            EmployeeCard.query(EmployeeCard.imc_email == user.email).get()
            if user
            else None
        )

    if not employee:
        return EEMPDNE  # Employee does not exist
    if not user:
        return EUSERDNE  # User does not exist

    try:
        employee.user_uid = user.key.id()
        employee.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
        if current_user and current_user.is_authenticated:
            employee.updated_by = current_user.email
        else:
            employee.updated_by = "System"
        employee.put()
        return True
    except Exception as e:
        print(f"Error linking EmployeeCard to User: {e}")
        return EEXCEPT  # If linking fails


################################################################################


################################################################################
### POSITION CARD FUNCTIONS ####################################################
################################################################################


def create_position_card(**kwargs: dict) -> dict | int:
    """
    Creates a new PositionCard object. All fields are optional.

    Arguments:
        `title` (`str`): The title of the position
        `job_description` (`str`): A link to the description for this position
        `brand` (`str`): What brand this position falls under
        `pay_status` (`str`): How this position is paid
        `pay_rate` (`float`): The amount this position is paid per hour/stipend/year
        `supervisors` (`list[int]`): UIDs of the position(s) this position directly reports to
        `google_group` (`str`): The email for the Google Group that all employees will be added to
        `slack_channels` (`list[str]`): The IDs of the Slack channels that all employees will be added to

    Returns:
        `dict`: The created `PositionCard` as a dictionary

    Raises:
        `EEXISTS`: If a position already exists with the given `brand` and `title`
        `EGROUPDNE`: If the Google Group is not valid
        `ESLACKDNE`: If one of the Slack channels does not exist or the bot cannot access
        `EEXCEPT`: Other fatal error
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
                return EEXISTS  # Position with this brand and title already exists

        # Check if this is a valid Google Group
        if "google_group" in kwargs:
            valid = check_group_exists(kwargs["google_group"])
            if not valid:
                return EGROUPDNE

        # Check if the Slack channels are valid
        if "slack_channels" in kwargs:
            channels = kwargs["slack_channels"]
            for channel in channels:
                valid = can_bot_access_channel(channel)
                if not valid:
                    return ESLACKDNE

        try:
            # Convert supervisor and direct report UIDs to ints
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
            return EEXCEPT  # Position creation failed


def modify_position_card(uid: int, **kwargs: dict) -> dict | int:
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
        `google_group` (`str`): The email for the Google Group that all employees will be added to
        `slack_channels` (`list[str]`): The IDs of the Slack channels that all employees will be added to

    Returns:
        `dict`: The modified `PositionCard` as a dictionary

    Raises:
        `EPOSDNE`: Position not found
        `EEXISTS`: If there exists another position with the same `brand` and `title`
        `EGROUPDNE`: If the Google Group does not exist or is invalid
        `ESLACKDNE`: If one of the Slack channels does not exist or the bot cannot access
        `ESUPREP`: If updating supervisors fails
        `EGROUP`: If updating Google Groups fails
        `ESLACK`: If updating Slack channels fails
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return EPOSDNE  # Position not found

        try:
            # Check if a position already exists with the given brand and title
            if "brand" in kwargs and "title" in kwargs:
                existing = PositionCard.query(
                    ndb.AND(
                        PositionCard.brand == kwargs["brand"],
                        PositionCard.title == kwargs["title"],
                    )
                ).get()

                if existing and existing.key != position.key:
                    return EEXISTS  # Position with this brand and title already exists

            # Check if this is a valid Google Group
            if "google_group" in kwargs:
                valid = check_group_exists(kwargs["google_group"])
                if not valid:
                    return EGROUPDNE

            # Check if the Slack channels are valid
            if "slack_channels" in kwargs:
                # Format into a list instead of comma-separated
                slack_channels_raw = kwargs["slack_channels"].strip()
                slack_channels = [
                    item.strip()
                    for item in slack_channels_raw.split(",")
                    if item.strip()
                ]

                kwargs["slack_channels"] = slack_channels
                channels = kwargs["slack_channels"]
                for channel in channels:
                    valid = can_bot_access_channel(channel)
                    if not valid:
                        return ESLACKDNE

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
                                supervisor.direct_reports = (
                                    supervisor.direct_reports or []
                                )
                                supervisor.direct_reports.append(position.uid)
                                supervisor.updated_at = datetime.now(
                                    tz=ZoneInfo("America/Chicago")
                                )
                                supervisor.updated_by = "System"
                                supervisor.put()
            except Exception as e:
                print(f"Error updating supervisors for PositionCard: {e}")
                return ESUPREP  # Updating supervisors failed

            # Ignore direct report updates
            if "direct_reports" in kwargs:
                del kwargs["direct_reports"]

            # Get each employee currently in this position to update their Google Group membership
            should_update_groups = (
                "google_group" in kwargs
                and kwargs["google_group"] != position.google_group
            )

            should_update_slack = (
                "slack_channels" in kwargs
                and kwargs["slack_channels"] != position.slack_channels
            )

            if should_update_groups or should_update_slack:
                rels = get_relations_by_position_current(position.uid)
                employees = []
                employee_old_groups = {}
                employee_old_slack = {}

                for rel in rels:
                    emp = EmployeeCard.get_by_id(rel["employee_id"])
                    if emp:
                        employees.append(emp)
                        if should_update_groups:
                            employee_old_groups[emp.uid] = get_groups_for_employee(
                                emp.uid
                            )
                        if should_update_slack:
                            employee_old_slack[
                                emp.uid
                            ] = get_slack_channels_for_employee(emp.uid)

            # Modify the position fields
            for key, value in kwargs.items():
                # if hasattr(position, key):
                setattr(position, key, value)

            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()

            # Update Google Group membership for all employees in this position
            if should_update_groups:
                for emp in employees:
                    old_groups = employee_old_groups.get(emp.uid, set())
                    new_groups = get_groups_for_employee(emp.uid, override_pos=position)

                    if set(old_groups) != set(new_groups):
                        success, _ = update_group_membership(
                            emp.imc_email, old_groups, new_groups
                        )
                        if not success:
                            return EGROUP  # Updating Google Groups failed

            # Update Slack channels for all employees in this position
            if should_update_slack:
                for emp in employees:
                    old_channels = employee_old_slack.get(emp.uid, [])
                    new_channels = get_slack_channels_for_employee(
                        emp.uid, override_pos=position
                    )

                    if set(old_channels) != set(new_channels):
                        if emp.slack_id:
                            success, _ = update_slack_channels(
                                user_id=emp.slack_id,
                                old_channels=old_channels,
                                new_channels=new_channels,
                            )
                            if not success:
                                return ESLACK  # Updating Slack channels failed

            return position.to_dict()
        except Exception as e:
            print(f"Error modifying PositionCard: {e}")
            return EEXCEPT  # Position modification failed


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


def get_all_active_position_cards() -> list:
    """
    Retrieves all active (non-archived) PositionCard entries in the database.

    Returns:
        `list`: A list of all active `PositionCard` entries as dictionaries
    """
    with client.context():
        positions = (
            PositionCard.query(PositionCard.archived == False)
            .order(PositionCard.brand, PositionCard.title)
            .fetch()
        )
        return [position.to_dict() for position in positions]


def get_position_card_by_id(uid: int) -> dict | int:
    """
    Retrieves a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to retrieve

    Returns:
        `dict`: The `PositionCard` as a dictionary

    Raises:
        `EPOSDNE`: If PositionCard not found
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        return position.to_dict() if position else EPOSDNE


def delete_position_card(uid: int) -> bool | int:
    """
    Deletes a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to delete

    Returns:
        `bool`: `True` if deletion was successful

    Raises:
        `EPOSDNE`: PositionCard not found
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return EPOSDNE  # Position not found

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

            # Delete all relations involving this position
            relations = get_relations_by_position(position.uid)
            for relation in relations:
                relation_entity = EmployeePositionRelation.get_by_id(relation["uid"])
                if relation_entity:
                    relation_entity.key.delete()

            position.key.delete()
            return True
        except Exception as e:
            print(f"Error deleting PositionCard: {e}")
            return EEXCEPT  # Deletion failed


def archive_position_card(uid: int) -> bool | int:
    """
    Archives a PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to archive

    Returns:
        `bool`: `True` if archiving was successful

    Raises:
        `EPOSDNE`: PositionCard not found
        `EEXISTS`: Position has active relations, cannot archive
        `None`: Other fatal error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return EPOSDNE  # Position not found

        rels = get_relations_by_position_current(position.uid)
        if rels:
            return EEXISTS  # Position has active relations, cannot archive

        try:
            position.archived = True
            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()
            return True
        except Exception as e:
            print(f"Error archiving PositionCard: {e}")
            return EEXCEPT  # Archiving failed


def restore_position_card(uid: int) -> bool | int:
    """
    Restores an archived PositionCard by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the PositionCard to restore

    Returns:
        `bool`: `True` if restoring was successful

    Raises:
        `EPOSDNE`: PositionCard not found
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        position = PositionCard.get_by_id(uid)
        if not position:
            return EPOSDNE  # Position not found

        try:
            position.archived = False
            position.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            position.updated_by = current_user.email if current_user else "System"
            position.put()
            return True
        except Exception as e:
            print(f"Error restoring PositionCard: {e}")
            return EEXCEPT  # Restoring failed


################################################################################


################################################################################
### RELATION FUNCTIONS #########################################################
################################################################################


def create_relation(**kwargs: dict) -> dict | int:
    """
    Creates a new EmployeePositionRelation object. `position_id` and `employee_id` are required.
        All other fields are optional. Adds the associated user to the Google Group for the position.

    Arguments:
        `position_id` (`int`): The UID of the position that is held by the employee
        `employee_id` (`int`): The UID of the employee that holds the position
        `start_date` (`date`): The date that the employee started in the position
        `end_date` (`date`): The date that the employee finished in the position
        `departure_category` (`str`): General category for why the employee is no longer in this position
        `departure_reason` (`str`): Specific reason for why the employee is no longer in this position
        `departure_notes` (`str`): Notes for why the employee is no longer in this position
        `created_at` (`datetime`): When this relation was created
        `updated_at` (`datetime`): When this relation was last edited
        `updated_by` (`str`): User who last updated the relation

    Returns:
        `dict`: The created `EmployeePositionRelation` as a dictionary

    Raises:
        `EEXISTS`: If a relation already exists with the given `position_id` and `employee_id`
        `EMISSING`: If missing required fields
        `EPOSDNE`: If the PositionCard does not exist
        `EEMPDNE`: If the EmployeeCard does not exist
        `EGROUP`: If Google Groups update fails
        `ESLACK`: If updating Slack channels fails
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        if not ("position_id" in kwargs and "employee_id" in kwargs):
            return EMISSING  # Position_id and employee_id are required

        # Validate position and employee existence
        try:
            position = PositionCard.get_by_id(kwargs["position_id"])
            if not position:
                return EPOSDNE  # Position with this UID does not exist

            employee = EmployeeCard.get_by_id(kwargs["employee_id"])
            if not employee:
                return EEMPDNE  # Employee with this UID does not exist
        except Exception as e:
            print(f"Error validating position or employee: {e}")
            return EEXCEPT  # Validation failed

        # Check for existing relation
        try:
            existing = EmployeePositionRelation.query(
                ndb.AND(
                    EmployeePositionRelation.position_id == kwargs["position_id"],
                    EmployeePositionRelation.employee_id == kwargs["employee_id"],
                )
            ).get()
            if existing:
                return EEXISTS  # Position with this brand and title already exists
        except Exception as e:
            print(f"Error checking existing EmployeePositionRelation: {e}")
            return EEXCEPT  # Checking existing relation failed

        try:
            old_groups = get_groups_for_employee(employee.uid)
            old_channels = get_slack_channels_for_employee(employee.uid)
            relation = EmployeePositionRelation(**kwargs)

            relation.created_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            relation.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            relation.updated_by = current_user.email if current_user else "System"
            relation.put()

            # Update Google Groups if necessary
            new_groups = get_groups_for_employee(employee.uid)
            if set(old_groups) != set(new_groups):
                success, error = update_group_membership(
                    user_email=employee.imc_email,
                    old_groups=old_groups,
                    new_groups=new_groups,
                )
                if not success:
                    return EGROUP  # Updating Google Groups failed

            # Update Slack channels if necessary
            new_channels = get_slack_channels_for_employee(employee.uid)
            if set(old_channels) != set(new_channels):
                if employee.slack_id:
                    success, error = update_slack_channels(
                        user_id=employee.slack_id,
                        old_channels=old_channels,
                        new_channels=new_channels,
                    )
                    if not success:
                        return ESLACK

            return relation.to_dict()
        except Exception as e:
            print(f"Error creating EmployeePositionRelation: {e}")
            return EEXCEPT  # Relation creation fails


def modify_relation(uid: int, **kwargs: dict) -> dict | int:
    """
    Modifies an existing EmployeePositionRelation object. `uid` is required, all other
    fields are optional. Modification cannot update the employee or the position.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeePositionRelation to modify
        `position_id` (`int`): The UID of the position that is held by the employee
        `employee_id` (`int`): The UID of the employee that holds the position
        `start_date` (`date`): The date that the employee started in the position
        `end_date` (`date`): The date that the employee finished in the position
        `departure_category` (`str`): General category for why the employee is no longer in this position
        `departure_reason` (`str`): Specific reason for why the employee is no longer in this position
        `departure_notes` (`str`): Notes for why the employee is no longer in this position
    Returns:
        `dict`: The modified `EmployeePositionRelation` as a dictionary

    Raises:
        `ERELDNE`: EmployeePositionRelation not found
        `EEMPDNE`: Associated EmployeeCard not found
        `EGROUP`: If Google Groups update fails
        `ESLACK`: If updating Slack channels fails
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        relation = EmployeePositionRelation.get_by_id(uid)
        if not relation:
            return ERELDNE  # Relation not found

        employee = EmployeeCard.get_by_id(relation.employee_id)
        if not employee:
            return EEMPDNE  # Employee not found

        try:
            if "position_id" in kwargs:
                del kwargs["position_id"]  # Prevent changing position_id
            if "employee_id" in kwargs:
                del kwargs["employee_id"]  # Prevent changing employee_id

            old_groups = get_groups_for_employee(employee.uid)
            old_channels = get_slack_channels_for_employee(employee.uid)

            for key, value in kwargs.items():
                if hasattr(relation, key):
                    setattr(relation, key, value)

            relation.updated_at = datetime.now(tz=ZoneInfo("America/Chicago"))
            relation.updated_by = current_user.email if current_user else "System"
            relation.put()

            # Update Google groups if necessary
            new_groups = get_groups_for_employee(employee.uid, override_rel=relation)
            if set(old_groups) != set(new_groups):
                success, error = update_group_membership(
                    user_email=employee.imc_email,
                    old_groups=old_groups,
                    new_groups=new_groups,
                )
                if not success:
                    return EGROUP  # Updating Google Groups failed

            # Update Slack channels if necessary
            new_channels = get_slack_channels_for_employee(
                employee.uid, override_rel=relation
            )
            if set(old_channels) != set(new_channels):
                if employee.slack_id:
                    success, error = update_slack_channels(
                        user_id=employee.slack_id,
                        old_channels=old_channels,
                        new_channels=new_channels,
                    )
                    if not success:
                        return ESLACK

            return relation.to_dict()
        except Exception as e:
            print(f"Error modifying EmployeePositionRelation: {e}")
            return EEXCEPT  # Relation modification failed


def get_all_relations() -> list:
    """
    Retrieves all EmployeePositionRelation entries in the database.

    Returns:
        `list`: A list of all `EmployeePositionRelation` entries as dictionaries
    """
    with client.context():
        relations = (
            EmployeePositionRelation.query()
            .order(-EmployeePositionRelation.start_date)
            .fetch()
        )
        return [relation.to_dict() for relation in relations]


def get_relation_by_id(uid: int) -> dict | int:
    """
    Retrieves an EmployeePositionRelation by its unique ID.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeePositionRelation to retrieve
    Returns:
        `dict`: The `EmployeePositionRelation` as a dictionary

    Raises:
        `ERELDNE`: EmployeePositionRelation not found
    """
    with client.context():
        relation = EmployeePositionRelation.get_by_id(uid)
        return relation.to_dict() if relation else ERELDNE


@ensure_context
def get_relations_by_employee(employee_id: int) -> list:
    """
    Retrieves all EmployeePositionRelation entries for a given employee.

    Arguments:
        `employee_id` (`int`): The UID of the employee

    Returns:
        `list`: A list of all `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.employee_id == employee_id
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [relation.to_dict() for relation in relations]


@ensure_context
def get_relations_by_employee_current(employee_id: int) -> list:
    """
    Retrieves all current EmployeePositionRelation entries for a given employee.

    Arguments:
        `employee_id` (`int`): The UID of the employee

    Returns:
        `list`: A list of all current `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.employee_id == employee_id,
            EmployeePositionRelation.end_date == None,
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [relation.to_dict() for relation in relations]


@ensure_context
def get_relations_by_employee_past(employee_id: int) -> list:
    """
    Retrieves all past EmployeePositionRelation entries for a given employee.

    Arguments:
        `employee_id` (`int`): The UID of the employee

    Returns:
        `list`: A list of all past `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.employee_id == employee_id
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [
        relation.to_dict() for relation in relations if relation.end_date is not None
    ]


@ensure_context
def get_relations_by_position(position_id: int) -> list:
    """
    Retrieves all EmployeePositionRelation entries for a given position.

    Arguments:
        `position_id` (`int`): The UID of the position

    Returns:
        `list`: A list of all `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.position_id == position_id
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [relation.to_dict() for relation in relations]


@ensure_context
def get_relations_by_position_current(position_id: int) -> list:
    """
    Retrieves all current EmployeePositionRelation entries for a given position.

    Arguments:
        `position_id` (`int`): The UID of the position
    Returns:
        `list`: A list of all current `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.position_id == position_id,
            EmployeePositionRelation.end_date == None,
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [relation.to_dict() for relation in relations]


@ensure_context
def get_relations_by_position_past(position_id: int) -> list:
    """
    Retrieves all past EmployeePositionRelation entries for a given position.

    Arguments:
        `position_id` (`int`): The UID of the position

    Returns:
        `list`: A list of all past `EmployeePositionRelation` entries as dictionaries
    """
    relations = (
        EmployeePositionRelation.query(
            EmployeePositionRelation.position_id == position_id
        )
        .order(-EmployeePositionRelation.start_date)
        .fetch()
    )
    return [
        relation.to_dict() for relation in relations if relation.end_date is not None
    ]


def delete_relation(uid: int) -> bool | int:
    """
    Deletes an EmployeePositionRelation by its unique ID. Removes the associated user
    from the Google Groups tied to the position if necessary.

    Arguments:
        `uid` (`int`): The unique ID of the EmployeePositionRelation to delete

    Returns:
        `bool`: `True` if deletion was successful

    Raises:
        `ERELDNE`: EmployeePositionRelation not found
        `EEMPDNE`: If the associated EmployeeCard does not exist
        `EGROUP`: If Google Groups update fails
        `ESLACK`: If updating Slack channels fails
        `EEXCEPT`: Other fatal error
    """
    with client.context():
        relation = EmployeePositionRelation.get_by_id(uid)
        if not relation:
            return ERELDNE  # Relation not found

        employee = EmployeeCard.get_by_id(relation.employee_id)
        if not employee:
            return EEMPDNE  # Employee not found

        try:
            old_groups = get_groups_for_employee(employee.uid)
            old_channels = get_slack_channels_for_employee(employee.uid)
            relation.key.delete()

            # Update Google Groups if necessary
            new_groups = get_groups_for_employee(employee.uid)
            if set(old_groups) != set(new_groups):
                success, error = update_group_membership(
                    user_email=employee.imc_email,
                    old_groups=old_groups,
                    new_groups=new_groups,
                )
                if not success:
                    return EGROUP  # Updating Google Groups failed

            # Update Slack channels if necessary
            new_channels = get_slack_channels_for_employee(employee.uid)
            if set(old_channels) != set(new_channels):
                if employee.slack_id:
                    success, error = update_slack_channels(
                        user_id=employee.slack_id,
                        old_channels=old_channels,
                        new_channels=new_channels,
                    )
                    if not success:
                        return ESLACK

            return True
        except Exception as e:
            print(f"Error deleting EmployeePositionRelation: {e}")
            return EEXCEPT  # Deletion failed


################################################################################


################################################################################
### HELPER FUNCTIONS ###########################################################
################################################################################


def get_groups_for_employee(
    employee_uid: int,
    override_rel: EmployeePositionRelation = None,
    override_pos: PositionCard = None,
) -> list:
    """
    Retrieves all Google Groups associated with the positions held by a given employee.

    Arguments:
        `employee_uid` (`int`): The UID of the employee
        `override_rel` (`EmployeePositionRelation`, optional): An EmployeePositionRelation object to override the data for one of the employee's relations.
        `override_pos` (`PositionCard`, optional): A PositionCard object to override the data for one of the employee's positions.

    Returns:
        `list`: A list of Google Group email addresses
    """
    groups = set()

    # This might return stale data for the relation we just saved
    relations = get_relations_by_employee_current(employee_uid)

    for rel_dict in relations:
        # Check if this specific relation was the one that might have just been modified
        if override_rel and rel_dict["uid"] == override_rel.uid:
            if override_rel.end_date is not None:
                # Skip this stale dictionary
                continue

            pos_id = override_rel.position_id
        else:
            pos_id = rel_dict["position_id"]

        if override_pos and pos_id == override_pos.uid:
            if override_pos.google_group:
                groups.add(override_pos.google_group)

        else:
            position = PositionCard.get_by_id(pos_id)
            if position and position.google_group:
                groups.add(position.google_group)

    return list(groups)


def get_slack_channels_for_employee(
    employee_uid: int,
    override_rel: EmployeePositionRelation = None,
    override_pos: PositionCard = None,
) -> list:
    """
    Retrieves all Slack channel IDs associated with the positions held by a given employee.

    Returns:
        `list`: A list of unique Slack channel IDs
    """
    channels = set()

    # Get the current relations for the employee
    relations = get_relations_by_employee_current(employee_uid)

    for rel_dict in relations:
        # 1. Handle Relation Overrides (check if the relation was just ended)
        if override_rel and rel_dict["uid"] == override_rel.uid:
            if override_rel.end_date is not None:
                continue  # Relation ended; skip adding these channels

            pos_id = override_rel.position_id
        else:
            pos_id = rel_dict["position_id"]

        # 2. Handle Position Overrides
        if override_pos and pos_id == override_pos.uid:
            if override_pos.slack_channels:
                channels.update(override_pos.slack_channels)
        else:
            position = PositionCard.get_by_id(pos_id)
            if position and position.slack_channels:
                channels.update(position.slack_channels)

    return list(channels)
