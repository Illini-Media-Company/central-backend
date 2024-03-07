from google.cloud import ndb

from . import client


class Group(ndb.Model):
    name = ndb.StringProperty()
    ancestors = ndb.JsonProperty()


def add_group(name, ancestors):
    with client.context():
        group = Group.query().filter(Group.name == name).get()
        if group is not None:
            group.name = name
            group.ancestors = ancestors
        else:
            group = Group(name=name, ancestors=ancestors)
        group.put()
    return group.to_dict()


def get_all_groups():
    with client.context():
        groups = [group.to_dict() for group in Group.query().fetch()]
    return groups
