from flask_login import UserMixin
from google.cloud import ndb

from . import client


class User(ndb.Model):
    sub = ndb.StringProperty()
    name = ndb.StringProperty()
    email = ndb.StringProperty()
    groups = ndb.JsonProperty()


class LoggedInUser(UserMixin):
    def __init__(self, db_user):
        self.id = db_user.email
        self.sub = db_user.sub
        self.name = db_user.name
        self.email = db_user.email
        self.groups = db_user.groups


def add_user(sub, name, email, groups):
    with client.context():
        user = User.query().filter(User.email == email).get()
        if user is not None:
            user.sub = sub
            user.name = name
            user.email = email
            user.groups = groups
        else:
            user = User(sub=sub, name=name, email=email, groups=groups)
        user.put()
    return LoggedInUser(user)


def update_user_groups(logged_in_user, groups):
    logged_in_user.groups = groups
    with client.context():
        user = User.query().filter(User.email == logged_in_user.email).get()
        if user is not None:
            user.groups = groups
            user.put()


def get_all_users():
    with client.context():
        users = [user.to_dict() for user in User.query().fetch()]
    return users


def get_user(email):
    if email is None:
        return None
    with client.context():
        user = User.query().filter(User.email == email).get()
    if user is None:
        return None
    return LoggedInUser(user)
