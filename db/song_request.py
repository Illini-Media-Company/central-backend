from google.cloud import ndb
import datetime
from db import client 

class SongRequest(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    song_name = ndb.StringProperty(required=True)
    artist_name = ndb.StringProperty(required=True)

    submitter_name = ndb.StringProperty()
    submitter_email = ndb.StringProperty()
    is_imc_employee = ndb.BooleanProperty(default=False)
    submitter_slack_id = ndb.StringProperty()

    timestamp = ndb.DateTimeProperty(auto_now_add=True)
    status = ndb.StringProperty(default='pending')  # pending, accepted, declined

    reviewer_name = ndb.StringProperty()
    rejection_reason = ndb.TextProperty()

    slack_ts = ndb.StringProperty()


def create_song_request(song_name, artist_name, submitter_name, submitter_email, is_imc_employee, submitter_slack_id):
    with client.context():
        song_request = SongRequest(
            song_name=song_name,
            artist_name=artist_name,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            is_imc_employee=is_imc_employee,
            submitter_slack_id=submitter_slack_id
        )
        song_request.put()
        return song_request

def get_all_song_requests():
    with client.context():
        return SongRequest.query().order(-SongRequest.timestamp).fetch()

def update_request_status(request_id, new_status, reviewer_name=None, rejection_reason=None):
    with client.context():
        song_request = SongRequest.get_by_id(int(request_id))
        if song_request:
            song_request.status = new_status
            song_request.reviewer_name = reviewer_name
            song_request.rejection_reason = rejection_reason
            song_request.put()
            return song_request
        return None

def update_slack_ts(request_id, ts):
    with client.context():
        song_request = SongRequest.get_by_id(int(request_id))
        if song_request:
            song_request.slack_ts = ts
            song_request.put()
            return song_request
        return None

def delete_all_song_requests():
    with client.context():
        keys = SongRequest.query().fetch(keys_only=True)
        ndb.delete_multi(keys)
        return len(keys)
    
def delete_old_song_requests(days_old=60):
    with client.context():
        now_utc_naive = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        cutoff_date = now_utc_naive - datetime.timedelta(days=days_old)
        keys = SongRequest.query(SongRequest.timestamp < cutoff_date).fetch(keys_only=True)
        
        if keys:
            ndb.delete_multi(keys)
            
        return len(keys)