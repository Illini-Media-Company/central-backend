from flask_login import UserMixin
from google.cloud import ndb

from . import client


class User(ndb.Model):
    name = ndb.StringProperty()
    email = ndb.StringProperty()


class LoggedInUser(UserMixin):
    def __init__(self, db_user):
        self.id = db_user.key.id()
        self.name = db_user.name
        self.email = db_user.email


def add_user(id, name, email):
    with client.context():
        user = User(id=id, name=name, email=email)
        user.put()
    return LoggedInUser(user)


def get_user(id=None):
    if id is None:
        return None
    with client.context():
        user = User.get_by_id(id)
    if user is None:
        return None
    return LoggedInUser(user)
