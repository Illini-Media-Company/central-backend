from google.cloud import ndb
from zoneinfo import ZoneInfo
from datetime import datetime
from . import client


# class for each employee agreement
class EmployeeAgreement(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )

    agreement_url = ndb.StringProperty()  # Link to the actual agreement
    agreement_name = ndb.StringProperty()  # What the agreement is for
    create_time = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    slack_ch = (
        ndb.StringProperty()
    )  # The Slack channel_id the original message was sent to
    slack_ts = ndb.StringProperty()  # The Slack timestamp for the original message

    user_email = ndb.StringProperty()
    user_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))

    editor_email = ndb.StringProperty()
    editor_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))

    manager_email = ndb.StringProperty()
    manager_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))

    chief_email = ndb.StringProperty()
    chief_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))


def add_employee_agreement(
    user_email: str,
    editor_email: str,
    manager_email: str,
    chief_email: str,
    agreement_url: str,
    agreement_name: str,
):
    """
    Add a new EmployeeAgreement object to the database. Sets all signature timestamps to None.

    :param user_email: @illinimedia.com email of the employee
    :type user_email: str
    :param editor_email: @illinimedia.com email of the editor
    :type editor_email: str
    :param manager_email: @illinimedia.com email of the manager
    :type manager_email: str
    :param chief_email: @illinimedia.com email of the Editor-in-Chief
    :type chief_email: str
    :param agreement_url: URL for employee to view the agreement
    :type agreement_url: str
    :param agreement_name: A short name for the agreement
    :type agreement_name: str

    :returns: The created object as a dictionary
    :rtype: dict
    """

    with client.context():
        agreement = EmployeeAgreement(
            agreement_url=agreement_url,
            agreement_name=agreement_name,
            create_time=datetime.now(tz=ZoneInfo("America/Chicago")),
            user_email=user_email,
            editor_email=editor_email,
            manager_email=manager_email,
            chief_email=chief_email,
            user_signed=None,
            editor_signed=None,
            manager_signed=None,
            chief_signed=None,
        )
        agreement.put()

    print(f"[agreement] New agreement created for {user_email}.")
    return agreement.to_dict()


def sign_update_agreement(uid: int, signer_email: str):
    """
    Sign an employee agreement specified by UID. Enforces signing order; i.e., a manager cannot sign before an editor, etc.

    :param uid: The UID of the agreement
    :type uid: int
    :param signer_email: The email address of the person signing the agreement
    :type signer_email: str

    :returns: True if signed, False otherwise. Email of the employee on the agreement. Email of the person to sign next.
    :rtype: tuple(bool, str, str)
    """
    print(f"[agreement] signing agreement {uid} by user {signer_email}...")

    with client.context():
        # Find the agreement
        agreement = EmployeeAgreement.get_by_id(uid)
        if not agreement:
            print(f"[agreement] Found no agreement with UID {uid}")
            return False, None, None

        # Check where the signer falls in the hierarchy
        if agreement.user_email == signer_email and agreement.user_signed is None:
            agreement.user_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee = agreement.user_email
            next_signer = agreement.editor_email

            agreement.put()
            print("[agreement] Signed as employee.")
            return True, employee, next_signer
        elif agreement.editor_email == signer_email and agreement.editor_signed is None:
            agreement.editor_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee = agreement.user_email
            next_signer = agreement.manager_email

            agreement.put()
            print("[agreement] Signed as editor.")
            return True, employee, next_signer
        elif (
            agreement.manager_email == signer_email and agreement.manager_signed is None
        ):
            agreement.manager_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee = agreement.user_email
            next_signer = agreement.chief_email

            agreement.put()
            print("[agreement] Signed as manager.")
            return True, employee, next_signer
        elif agreement.chief_email == signer_email and agreement.chief_signed is None:
            agreement.chief_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
            employee = agreement.user_email

            agreement.put()
            print("[agreement] Signed as Editor-in-Chief.")
            return True, employee, None

        print("[agreement] Failed to sign agreement.")
        return False, None, None


def get_agreement_by_id(uid: int):
    """
    Fetch an agreement from its UID.

    :param uid: The UID of the agreement
    :type uid: int

    :returns: an EmployeeAgreement object as a dictionary; None if not found
    :rtype: dict | None
    """
    with client.context():
        agreement = EmployeeAgreement.get_by_id(uid)

        if agreement:
            return agreement.to_dict()

        return None


def update_slack_info(uid: int, ch: str, ts: str):
    """
    Store the Slack channel and timestamp to the EmployeeAgreement object in the database.

    :param uid: The UID of the agreement
    :type uid: int
    :param ch: The Slack channel_id that the original message was sent to
    :type ch: str
    :param ts: The Slack timestamp of the original message's send event
    :type ts: str

    :returns: True if successful, False otherwise
    :rtype: bool
    """

    with client.context():
        agreement = EmployeeAgreement.get_by_id(uid)

        if not agreement:
            return False
        else:
            agreement.slack_ch = ch
            agreement.slack_ts = ts
            agreement.put()

            return True


def remove_agreement(uid: int):
    """
    Delete an employee agreement from the database.

    :param uid: The UID of the agreement
    :type uid: int

    :returns: True if successful, False otherwise
    :rtype: bool
    """
    with client.context():
        agreement = EmployeeAgreement.get_by_id(uid)

        if agreement is not None:
            agreement.key.delete()
            return True
        else:
            return False


def get_agreement_name(uid: int):
    """
    Get the name of an agreement from a UID.

    :param uid: The UID of the agreement
    :type uid: int

    :returns: The name of the agreement, None if not found
    :rtype: str | None
    """
    with client.context():
        agreement = EmployeeAgreement.get_by_id(uid)

        if agreement is not None:
            return agreement.agreement_name
        else:
            return None


def get_pending_agreements_for_user(email: str):
    """
    Get all agreements where `user_email` is `email` and the user has not yet signed.

    :param email: @illinimedia.com email of the user
    :type email: str

    :returns: All agreements not yet signed by the user
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            EmployeeAgreement.user_email == email
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.user_signed is None
        ]


def get_pending_agreements_for_editor(email: str):
    """
    Get all agreements where `editor_email` is `email` and the editor has not yet signed,
    given that the user has already signed.

    :param email: @illinimedia.com email of the editor
    :type email: str

    :returns: All agreements not yet signed by the editor
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.editor_email == email,
                EmployeeAgreement.editor_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.user_signed is not None
        ]


def get_pending_agreements_for_manager(email: str):
    """
    Get all agreements where `manager_email` is `email` and the manager has not yet signed,
    given that the editor has already signed.

    :param email: @illinimedia.com email of the manager
    :type email: str

    :returns: All agreements not yet signed by the manager
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.manager_email == email,
                EmployeeAgreement.manager_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.editor_signed is not None
        ]


def get_pending_agreements_for_chief(email: str):
    """
    Get all agreements where `chief_email` is `email` and the Editor-in-Chief has not yet signed,
    given that the manager has already signed.

    :param email: @illinimedia.com email of the Editor-in-Chief
    :type email: str

    :returns: All agreements not yet signed by the Editor-in-Chief
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.chief_email == email,
                EmployeeAgreement.chief_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.manager_signed is not None
        ]


def get_past_agreements_for_user(email: str):
    """
    Get all agreements where `user_email` is `email` and the user has already signed.

    :param email: @illinimedia.com email of the user
    :type email: str

    :returns: All agreements already signed by the user
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            EmployeeAgreement.user_email == email
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.user_signed is not None
        ]


def get_incomplete_agreements():
    """
    Get all agreements that are not yet complete.

    :returns: All incomplete agreements
    :rtype: list[dict]
    """
    with client.context():
        agreements = EmployeeAgreement.query(
            EmployeeAgreement.chief_signed == None
        ).fetch()

    return [agreement.to_dict() for agreement in agreements]
