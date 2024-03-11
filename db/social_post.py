from enum import StrEnum
import uuid
from datetime import datetime, timedelta
from google.cloud import ndb

from . import client


class SocialPlatform(StrEnum):
    REDDIT = "Reddit"
    TWITTER = "Twitter"
    ILLINOIS_APP = "Illinois app"


class SocialPost(ndb.Model):
    title = ndb.StringProperty()
    url = ndb.StringProperty()
    platform = ndb.StringProperty(choices=list(SocialPlatform))
    created_by = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()


def add_post(title, url, platform, created_by):
    with client.context():
        post = SocialPost(
            title=title,
            url=url,
            platform=platform,
            created_by=created_by,
            created_at=datetime.now(),
        )
        post.put()
    return post.to_dict()


def get_all_posts():
    with client.context():
        posts = [post.to_dict() for post in SocialPost.query().fetch()]
    return posts


def get_recent_posts(count):
    with client.context():
        posts = [
            post.to_dict()
            for post in SocialPost.query()
            .order(-SocialPost.created_at)
            .fetch(limit=count)
        ]
    return posts


def delete_all_posts():
    with client.context():
        posts = SocialPost.query().fetch()
        for post in posts:
            post.key.delete()


def check_limit(platform, limit, days):
    with client.context():
        current_datetime = datetime.now()
        start_datetime = current_datetime - timedelta(days=days)
        recent_posts = (
            SocialPost.query()
            .filter(
                SocialPost.platform == platform,
                SocialPost.created_at >= start_datetime,
                SocialPost.created_at <= current_datetime,
            )
            .fetch()
        )
    return len(recent_posts) >= limit
