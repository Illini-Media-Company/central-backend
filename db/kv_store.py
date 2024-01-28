from datetime import datetime, timedelta
from google.cloud import ndb

from . import client


class KVStore(ndb.Model):
    value = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()
    updated_at = ndb.DateTimeProperty()


def kv_store_get(key):
    with client.context():
        store_obj = KVStore.get_by_id(key)
        if store_obj is not None:
            return store_obj.value
        else:
            return None


def kv_store_set(key, value, replace=True):
    with client.context():
        store_obj = KVStore.get_by_id(key)
        if store_obj is None:
            now = datetime.now()
            store_obj = KVStore(value=value, created_at=now, updated_at=now)
        elif not replace:
            return False
        else:
            store_obj.value = value
            store_obj.updated_at = datetime.now()

        store_obj.put()
        return True
