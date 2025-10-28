from google.cloud import ndb
from zoneinfo import ZoneInfo
from . import client

#class for each employee agreement
class EmployeeAgreement(ndb.Model):
    user_id = ndb.StringProperty()
    user_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    editor_id = ndb.StringProperty()
    editor_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    manager_id = ndb.StringProperty()
    manager_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    chief_id = ndb.StringProperty()
    chief_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    agreement_url = ndb.StringProperty()

    

#add a new employee agreement to db, all signatures are set to none 
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
    return agreement.to_dict()

#get employee agreement by user id
def get_employee_agreement_by_user(user_id):
    with client.context():
        agreement = EmployeeAgreement.query(EmployeeAgreement.user_id == user_id).get()
        if agreement:
            return agreement.to_dict()
        else:
            return None 

# Return the actual opject so .get() can be used to update the properties
def get_agreement_object_by_user(user_id):
    with client.context():
        return EmployeeAgreement.query(EmployeeAgreement.user_id == user_id).get()



#return all pending agreements for editor
def get_pending_agreements_for_editor(editor_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.editor_id == editor_id,
                EmployeeAgreement.editor_signed == None,
                EmployeeAgreement.user_signed != None,
            )
        ).fetch()
        return [agreement.to_dict() for agreement in agreements]

#return all pending agreements for manager
def get_pending_agreements_for_manager(manager_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.manager_id == manager_id,
                EmployeeAgreement.manager_signed == None,
                EmployeeAgreement.editor_signed != None,
            )
        ).fetch()
        return [agreement.to_dict() for agreement in agreements]

#return all pending agreements for chief
def get_pending_agreements_for_chief(chief_id):
    with client.context():
        agreements = EmployeeAgreement.query(
            ndb.AND(
                EmployeeAgreement.chief_id == chief_id,
                EmployeeAgreement.chief_signed == None,
                EmployeeAgreement.manager_signed != None,
            )
        ).fetch()
        return [agreement.to_dict() for agreement in agreements]
        
#og person
#their editor
#manager of their section
#cheif 
        
#check which type of user
#taht tells us what user to pull
#pull employee agreement by editor, manager, cheif ETC. 
        
