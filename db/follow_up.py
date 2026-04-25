from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from . import client

logger = logging.getLogger(__name__)


class FollowUpItem(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    title = ndb.StringProperty()
    notes = ndb.StringProperty()
    status = ndb.StringProperty()     
    priority = ndb.StringProperty()   
    category = ndb.StringProperty()
    owner = ndb.StringProperty()
    filed = ndb.BooleanProperty(default=False)
    created_at = ndb.DateTimeProperty()
    updated_at = ndb.DateTimeProperty()


def create_item(title, notes, status, priority, category, owner):
    pass


def get_all_active_items():
    pass


def get_item_by_id(uid):
    pass


def update_item(uid, **fields):
    pass


def resolve_item(uid):
    pass


def get_resolved_items():
    pass
