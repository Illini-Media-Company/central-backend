from google.cloud import ndb
from datetime import datetime, timezone
from . import client


class StoryObject(ndb.Model):
    title = ndb.StringProperty()
    description = ndb.StringProperty()
    writer = ndb.StringProperty()
    writer_email = ndb.StringProperty()
    department = ndb.StringProperty()
    google_doc_link = ndb.StringProperty()
    snow_link = ndb.StringProperty()
    writer_status = ndb.StringProperty()
    copy_status = ndb.StringProperty()
    publish_time = ndb.DateTimeProperty()
    notes = ndb.StringProperty()
    editors = ndb.StringProperty(repeated=True)
    copy_editors = ndb.StringProperty()
    visuals = ndb.StringProperty()
    graphics = ndb.StringProperty()


def add_story(title, description, writer, writer_email, department, google_doc_link, snow_link, writer_status, copy_status, publish_time, notes, editors, copy_editors, visuals, graphics):
    """Create and save a new story."""

    with client.context():
        story = StoryObject(
            title=title,
            description=description,
            writer=writer,
            writer_email=writer_email,
            department=department,
            google_doc_link=google_doc_link,
            snow_link=snow_link,
            writer_status=writer_status,
            copy_status=copy_status,
            publish_time=publish_time,
            notes=notes,
            editors=editors or [],
            copy_editors=copy_editors,
            visuals=visuals,
            graphics=graphics,
        )
        story.put()
        return story.to_dict()


def get_all_stories():
    """Return every story."""

    with client.context():
        stories = [story.to_dict() for story in StoryObject.query().fetch()]
    return stories


def get_story_by_id(story_id):
    """Return one story by id, or None."""

    with client.context():
        story = StoryObject.get_by_id(int(story_id))
        return story.to_dict() if story else None


def update_story(story_id, **kwargs):
    """Update a story by id."""

    with client.context():
        story = StoryObject.get_by_id(int(story_id))

        if not story:
            raise ValueError(f"Story with ID {story_id} not found.")

        is_dirty = False

        for key, value in kwargs.items():
            if hasattr(story, key) and getattr(story, key) != value:
                setattr(story, key, value)
                is_dirty = True

        if is_dirty:
            story.put()

        return story.to_dict()