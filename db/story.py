from datetime import datetime
from google.cloud import ndb

from . import client


class Story(ndb.Model):
    title = ndb.StringProperty()
    url = ndb.StringProperty()
    post_to_reddit = ndb.BooleanProperty()
    post_to_twitter = ndb.BooleanProperty()
    slack_message_id = ndb.StringProperty()
    created_by = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()


def add_story(
    title, url, post_to_reddit, post_to_twitter, slack_message_id, created_by
):
    with client.context():
        story = Story(
            title=title,
            url=url,
            post_to_reddit=post_to_reddit,
            post_to_twitter=post_to_twitter,
            slack_message_id=slack_message_id,
            created_by=created_by,
            created_at=datetime.now(),
        )
        story.put()
    return story.to_dict()


def get_all_stories():
    with client.context():
        stories = [story.to_dict() for story in Story.query().fetch()]
    return stories


def get_recent_stories(count):
    with client.context():
        stories = [
            story.to_dict()
            for story in Story.query().order(-Story.created_at).fetch(limit=count)
        ]
    return stories


def delete_all_stories():
    with client.context():
        stories = Story.query().fetch()
        for story in stories:
            story.key.delete()
