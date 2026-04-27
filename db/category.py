from google.cloud import ndb
import logging

logger = logging.getLogger(__name__)

COLORS = [
    {"bg": "#f0f1f5", "text": "#4b5563"},  # gray
    {"bg": "#dfeafc", "text": "#2563eb"},  # blue
    {"bg": "#f1defc", "text": "#9927ff"},  # purple
    {"bg": "#f8ecb8", "text": "#d96a00"},  # yellow
    {"bg": "#d1fae5", "text": "#065f46"},  # green
    {"bg": "#fee2e2", "text": "#b91c1c"},  # red
    {"bg": "#fce7f3", "text": "#9d174d"},  # pink
]

DEFAULTS = [
    ("General", COLORS[0]),
    ("Finance", COLORS[1]),
    ("Housing", COLORS[2]),
    ("Senior Pics", COLORS[3]),
]


class Category(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    name = ndb.StringProperty()
    bg_color = ndb.StringProperty()
    text_color = ndb.StringProperty()


def get_all_categories():
    cats = Category.query().fetch()
    return sorted([c.to_dict() for c in cats], key=lambda c: c.get("name", ""))


def create_category(name):
    existing = Category.query().fetch()
    for cat in existing:
        if cat.name == name:
            return cat.to_dict()
    used_bgs = {cat.bg_color for cat in existing}
    color = next(
        (c for c in COLORS if c["bg"] not in used_bgs),
        COLORS[len(existing) % len(COLORS)],
    )
    cat = Category(name=name, bg_color=color["bg"], text_color=color["text"])
    cat.put()
    return cat.to_dict()


def delete_category(uid):
    cat = Category.get_by_id(uid)
    if cat:
        cat.key.delete()


def seed_default_categories():
    if not Category.query().fetch(limit=1):
        for name, color in DEFAULTS:
            Category(name=name, bg_color=color["bg"], text_color=color["text"]).put()
