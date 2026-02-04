# Stores information about a user.

# Created
# Last modified Oct. 5, 2025

from flask_login import UserMixin
from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo

from . import client


class User(ndb.Model):
    #
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    #
    sub = ndb.StringProperty()
    # Full name
    name = ndb.StringProperty()
    # IMC email address
    email = ndb.StringProperty()
    # Google profile photo link
    picture = ndb.StringProperty()
    # Google Groups the user is in
    groups = ndb.JsonProperty()
    # Time the user last copy edited a story (DI)
    last_edited = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    # Time the user last logged into the IMC console
    last_login = ndb.DateTimeProperty(tzinfo=ZoneInfo("America/Chicago"))
    # ID's of favorite tools to display on the index page
    fav_tools = ndb.IntegerProperty(repeated=True)
    # EmployeeCard object associated with the user (if any)
    employee_card_key = ndb.KeyProperty(kind="EmployeeCard")


class LoginUser(UserMixin):
    def __init__(self, db_user):
        self.id = db_user.email
        self.sub = db_user.sub
        self.name = db_user.name
        self.email = db_user.email
        self.picture = db_user.picture
        self.groups = db_user.groups
        self.fav_tools = db_user.fav_tools
        self.last_edited = db_user.last_edited


def add_user(
    sub, name, email, picture=None, groups=[], last_edited=None, last_login=None
):
    with client.context():
        user = User.query().filter(User.email == email).get()
        if user is not None:
            user.sub = sub
            user.name = name
            user.email = email
            user.picture = picture
            user.groups = groups
            user.last_edited = last_edited
            user.last_login = last_login
        else:
            user = User(
                sub=sub,
                name=name,
                email=email,
                picture=picture,
                groups=groups,
                fav_tools=[],
                last_edited=last_edited,
                last_login=last_login,
            )
        user.put()
    return LoginUser(user)


# Update either a user's name, email or picture that already exists in the database
def update_user(name, email, picture, last_login=None):
    with client.context():
        user = User.query().filter(User.email == email).get()
        if user is not None:
            if name is not None:
                user.name = name
            if email is not None:
                user.email = email
            if picture is not None:
                user.picture = picture
            user.last_login = last_login or datetime.now(ZoneInfo("America/Chicago"))
            user.put()
    return LoginUser(user)


def get_user(email):
    if email is None:
        return None
    with client.context():
        user = User.query().filter(User.email == email).get()
    if user is None:
        return None
    return LoginUser(user)


def get_all_users():
    with client.context():
        users = [user.to_dict() for user in User.query().fetch()]
    return users


def get_user_name(email: str):
    """
    Get the name of a user from their email.
    :param email: @illinimedia.com email of a user
    :type email: str
    :returns: A name; None if not found
    :rtype: str | None
    """
    with client.context():
        user = User.query().filter(User.email == email).get()

        if user:
            return user.name
        else:
            return None


def update_user_groups(email, groups):
    with client.context():
        user = User.query().filter(User.email == email).get()
        if user is not None:
            user.groups = groups
            user.put()


def update_user_last_edited(email, last_edited):
    last_edited = last_edited.astimezone(tz=None).replace(tzinfo=None)
    with client.context():
        user = User.query().filter(User.email == email).get()
        if user is not None:
            user.last_edited = last_edited
            user.put()


def add_user_favorite_tool(email, tool_uid):
    """Adds a new favorite tool for a user specified by email. Returns True on success."""
    with client.context():
        user = User.query().filter(User.email == email).get()

        if user is not None:
            user.fav_tools.append(int(tool_uid))
            user.put()
            return True
        else:
            return False


def remove_user_favorite_tool(email, tool_uid):
    """Removes a tool from a user's favorites. Returns True on success."""
    with client.context():
        user = User.query().filter(User.email == email).get()

        if user is not None:
            user.fav_tools.remove(int(tool_uid))
            user.put()
            return True
        else:
            return False


def get_user_favorite_tools(email):
    """Returns a list of UIDs for all the user's favorite tools."""
    with client.context():
        user = User.query().filter(User.email == email).get()

        if user is not None:
            return user.fav_tools
        else:
            return False


def get_user_profile_photo(uid):
    """
    Returns the profile photo URL of the user with the given UID.

    Arguments:
        `uid` (`int`): The UID of the user.

    Returns:
        `str | None`: The profile photo URL of the user, or `None` if the user is not found.

    """
    with client.context():
        user = User.get_by_id(uid)

        if user is not None:
            return user.picture
        else:
            return None
