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
    # link has no purpose for now since no google API integration yet
    email_link = ndb.StringProperty()  
    created_at = ndb.DateTimeProperty()
    updated_at = ndb.DateTimeProperty()


def create_item(title, notes, status, priority, category, owner, email_link=None):
    logger.info(f"Creating followup item: {title}")
    now = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
    item = FollowUpItem(
        title=title,
        notes=notes,
        status=status,
        priority=priority,
        category=category,
        owner=owner,
        email_link=email_link,
        created_at=now,
        updated_at=now,
    )
    item.put()
    logger.info(f"Created followup item with UID: {item.uid}")
    return item.to_dict()


def get_all_active_items():
    logger.info("Fetching all active followup items...")
    query = FollowUpItem.query(FollowUpItem.status != "Resolved")
    items = [item.to_dict() for item in query.fetch()]
    logger.info(f"Found {len(items)} active items.")
    return items


def get_item_by_id(uid):
    pass


def update_item(uid, **fields):
    pass


def resolve_item(uid):
    pass


def get_resolved_items():
    pass
