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
    user_signed = ndb.BooleanProperty()
    hiring_id = ndb.StringProperty()
    hriring_signed = ndb.BooleanProperty()
    cheif_id = ndb.StringProperty()
    chief_signed = ndb.BooleanProperty()
    signed_at = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    agreement_url = ndb.StringProperty()

#check if the date is set because that would help with the date
    
    

def add_employee_agreement(user_id, hiring_id, chief_id, agreement_url):
    with client.context():
        agreement = EmployeeAgreement(
            user_id=user_id,
            user_signed=False,
            hiring_id=hiring_id,
            hriring_signed=False,
            cheif_id=chief_id,
            chief_signed=False,
            agreement_url=agreement_url
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
