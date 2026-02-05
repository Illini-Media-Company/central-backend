from datetime import datetime, timedelta
from google.cloud import ndb

from . import client


class DiSocialStory(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    story_url = ndb.StringProperty()
    story_name = ndb.StringProperty()
    story_posted_timestamp = ndb.DateTimeProperty()
    slack_message_ts = (
        ndb.StringProperty()
    )  # Slack message ts (Unix); used for reaction lookup and "when posted"
    instagram_timestamp = ndb.DateTimeProperty()
    facebook_timestamp = ndb.DateTimeProperty()
    reddit_timestamp = ndb.DateTimeProperty()
    x_timestamp = ndb.DateTimeProperty()
    threads_timestamp = ndb.DateTimeProperty()


def add_social_story(url, name):
    """
    Create a new social story record.

    Args:
        url: Story URL
        name: Story name

    Returns:
        dict: The created story as a dictionary
    """
    with client.context():
        story = DiSocialStory(
            story_url=url,
            story_name=name,
            story_posted_timestamp=datetime.now(),
            instagram_timestamp=None,
            facebook_timestamp=None,
            reddit_timestamp=None,
            x_timestamp=None,
            threads_timestamp=None,
        )
        story.put()
    return story.to_dict()


def update_slack_details(url, message_ts):
    """
    Update the Slack message ts for a story with the given URL.

    Args:
        url: Story URL to update
        message_ts: Slack message ts string (e.g. from chat_postMessage response)

    Returns:
        dict: Updated story as dictionary, or None if not found
    """
    with client.context():
        query = DiSocialStory.query().filter(DiSocialStory.story_url == url)
        story = query.get()
        if story:
            story.slack_message_ts = message_ts
            story.put()
            return story.to_dict()
        else:
            return None


def update_social(url, social_media_name):
    """
    Update the timestamp for a specific social media platform to datetime.now().

    Args:
        url: Story URL to update
        social_media_name: Name of social media platform (from SocialMedia enum)

    Returns:
        dict: Updated story as dictionary, or None if not found
    """
    with client.context():
        query = DiSocialStory.query().filter(DiSocialStory.story_url == url)
        story = query.get()
        if story:
            now = datetime.now()
            if social_media_name == "Slack":
                # Slack "posted" time is set when the slackbot calls update_slack_message_ref with message_ts
                pass
            elif social_media_name == "Instagram":
                story.instagram_timestamp = now
            elif social_media_name == "Facebook":
                story.facebook_timestamp = now
            elif social_media_name == "Reddit":
                story.reddit_timestamp = now
            elif social_media_name == "X":
                story.x_timestamp = now
            elif social_media_name == "Threads":
                story.threads_timestamp = now
            else:
                raise ValueError(f"Invalid social media name: {social_media_name}")
            story.put()
            return story.to_dict()
        else:
            return None


def get_all_stories():
    """
    Get all social stories.

    Returns:
        list: List of all stories as dictionaries
    """
    with client.context():
        stories = [story.to_dict() for story in DiSocialStory.query().fetch()]
    return stories


def get_recent_stories(count):
    """
    Get recent social stories ordered by story_posted_timestamp.

    Args:
        count: Number of recent stories to return

    Returns:
        list: List of recent stories as dictionaries
    """
    with client.context():
        stories = [
            story.to_dict()
            for story in DiSocialStory.query()
            .order(-DiSocialStory.story_posted_timestamp)
            .fetch(limit=count)
        ]
    return stories


def get_story_by_url(url):
    """
    Get a story by its URL.

    Args:
        url: Story URL to find

    Returns:
        dict: Story as dictionary, or None if not found
    """
    with client.context():
        query = DiSocialStory.query().filter(DiSocialStory.story_url == url)
        story = query.get()
        if story:
            return story.to_dict()
        else:
            return None


def delete_all_stories():
    """
    Delete all social story records.

    Returns:
        str: Confirmation message
    """
    with client.context():
        stories = DiSocialStory.query().fetch()
        for story in stories:
            story.key.delete()
    return "All social stories deleted"


def _slack_ts_to_datetime(ts):
    """Convert Slack message ts string to local datetime, or None if invalid."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts))
    except (ValueError, TypeError):
        return None


def check_limit(social_media_name, limit, days):
    """
    Check if a social media platform has reached its posting limit within a time window.

    Args:
        social_media_name: Name of social media platform (from SocialMedia enum)
        limit: Maximum number of posts allowed
        days: Number of days to look back

    Returns:
        bool: True if limit reached, False otherwise
    """
    with client.context():
        current_datetime = datetime.now()
        start_datetime = current_datetime - timedelta(days=days)

        if social_media_name == "Slack":
            # Slack uses slack_message_ts (string); derive datetime for window
            stories = (
                DiSocialStory.query()
                .filter(DiSocialStory.slack_message_ts != None)
                .fetch()
            )
            recent_posts = []
            for s in stories:
                dt = _slack_ts_to_datetime(s.slack_message_ts)
                if dt and start_datetime <= dt <= current_datetime:
                    recent_posts.append(s)
        else:
            timestamp_field = {
                "Instagram": DiSocialStory.instagram_timestamp,
                "Facebook": DiSocialStory.facebook_timestamp,
                "Reddit": DiSocialStory.reddit_timestamp,
                "X": DiSocialStory.x_timestamp,
                "Threads": DiSocialStory.threads_timestamp,
            }.get(social_media_name)
            if timestamp_field is None:
                raise ValueError(f"Invalid social media name: {social_media_name}")
            recent_posts = (
                DiSocialStory.query()
                .filter(
                    timestamp_field >= start_datetime,
                    timestamp_field <= current_datetime,
                )
                .fetch()
            )
        return len(recent_posts) >= limit
