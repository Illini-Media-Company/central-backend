from google.cloud import ndb
from zoneinfo import ZoneInfo
from . import client

#ndb.dataproperty(tzinfo=ZoneInfo("America/Chicago")) used for anytime we get the time so i need this for every date/time property 
# search through the db for employee agreement by their email 
# agreement id - contains user, agreement url, 
#do time instead of bool so we can check if exists 
#delete agreement when employee leaves company
#based off of email - slack id 


class EmployeeAgreement(ndb.Model):
    user_id = ndb.StringProperty()
    user_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    hiring_id = ndb.StringProperty()
    hriring_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    manager_id = ndb.StringProperty()
    manager_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    cheif_id = ndb.StringProperty()
    chief_signed = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    agreement_url = ndb.StringProperty()
#check if the date is set because that would help with the date
    
    

def add_employee_agreement(user_id, hiring_id, manager_id, chief_id, agreement_url):
    with client.context():
        agreement = EmployeeAgreement(
            agreement_url=agreement_url,
            user_id=user_id,
            hiring_id=hiring_id,
            manager_id=manager_id,
            cheif_id=chief_id,
            user_signed=None,
            hriring_signed=None,
            manager_signed=None,
            chief_signed=None,
        )
        agreement.put()
    return agreement.to_dict()

def get_employee_agreement_by_user(user_id):
    with client.context():
        agreement = EmployeeAgreement.query(EmployeeAgreement.user_id == user_id).get()
        if agreement:
            return agreement.to_dict()
        else:
            return None 
        
#og person
#their editor
#manager of their section
#cheif 
