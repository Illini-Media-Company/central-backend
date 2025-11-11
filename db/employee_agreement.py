from google.cloud import ndb
from zoneinfo import ZoneInfo
from . import client


# class for each employee agreement
class EmployeeAgreement(ndb.Model):
    user_id = ndb.StringProperty()  # Slack ID for the employee
    user_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    editor_id = ndb.StringProperty()  # Slack ID for the editor
    editor_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    manager_id = ndb.StringProperty()  # Slack ID for the managing editor
    manager_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    chief_id = ndb.StringProperty()  # Slack ID for the Editor-in-Chief
    chief_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    agreement_url = ndb.StringProperty()


# add a new employee agreement to db, all signatures are set to none
def add_employee_agreement(user_id, editor_id, manager_id, chief_id, agreement_url):
    with client.context():
        agreement = EmployeeAgreement(
            agreement_url=agreement_url,
            user_id=user_id,
            editor_id=editor_id,
            manager_id=manager_id,
            chief_id=chief_id,
            user_signed=None,
            editor_signed=None,
            manager_signed=None,
            chief_signed=None,
        )
        agreement.put()
    print(agreement.to_dict())

    return agreement.to_dict()


# get employee agreement by user id
def get_employee_agreements_by_user(user_id):
    with client.context():
        agreements = EmployeeAgreement.query(EmployeeAgreement.user_id == user_id).fetch()
        return [agreement.to_dict() for agreement in agreements]
    


# Return the actual opject so .get() can be used to update the properties
def get_agreement_objects_by_user(user_id):
    with client.context():
        return EmployeeAgreement.query(EmployeeAgreement.user_id == user_id).fetch()


# return all pending agreements for editor
def get_pending_agreements_for_editor(editor_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.editor_id == editor_id,
                EmployeeAgreement.editor_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.user_signed is not None
        ]


# return all pending agreements for manager
def get_pending_agreements_for_manager(manager_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.manager_id == manager_id,
                EmployeeAgreement.manager_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.editor_signed is not None
        ]


# return all pending agreements for chief
def get_pending_agreements_for_chief(chief_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.chief_id == chief_id,
                EmployeeAgreement.chief_signed == None,
            )
        ).fetch()
        return [
            agreement.to_dict()
            for agreement in agreements
            if agreement.manager_signed is not None
        ]
