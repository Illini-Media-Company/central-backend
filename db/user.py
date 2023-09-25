from flask_login import UserMixin
from google.cloud import ndb

from . import client


class User(ndb.Model):
    sub = ndb.StringProperty()
    name = ndb.StringProperty()
    email = ndb.StringProperty()


class LoggedInUser(UserMixin):
    def __init__(self, db_user):
        self.id = db_user.sub
        self.name = db_user.name
        self.email = db_user.email


def add_user(sub, name, email):
    with client.context():
        user = User(sub=sub, name=name, email=email)
        user.put()
    return LoggedInUser(user)


def get_all_users():
    with client.context():
        users = [user.to_dict() for user in User.query().fetch()]
    return users


def get_user(sub=None, email=None):
    if sub is None:
        return None
    with client.context():
        user = User.query().filter(User.sub == sub).get()
    if user is None:
        return None
    return LoggedInUser(user)
