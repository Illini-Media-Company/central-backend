from google.cloud import ndb

from . import client


class QuickLink(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    name = ndb.StringProperty()
    url = ndb.StringProperty()
    group = ndb.StringProperty()


def add_quick_link(name, url, group=None):
    with client.context():
        quick_link = QuickLink.query().filter(QuickLink.name == name).get()
        if quick_link is not None:
            quick_link.url = url
            quick_link.group = group
        else:
            quick_link = QuickLink(name=name, url=url, group=group)
        quick_link.put()
    return quick_link.to_dict()


def get_all_quick_links():
    with client.context():
        quick_links = [quick_link.to_dict() for quick_link in QuickLink.query().fetch()]
    return quick_links


def remove_quick_link(uid):
    with client.context():
        quick_link = QuickLink.get_by_id(uid)
        if quick_link is not None:
            quick_link.key.delete()
            return True
        else:
            return False
