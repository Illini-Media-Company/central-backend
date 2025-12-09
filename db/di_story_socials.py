from datetime import datetime, timedelta
from google.cloud import ndb

from . import client


class DiStorySocials(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    story_url = ndb.StringProperty()
    story_name = ndb.StringProperty()
    story_posted_timestamp = ndb.DateTimeProperty()
    slack_message_timestamp = ndb.DateTimeProperty()
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
        story = DiStorySocials(
            story_url=url,
            story_name=name,
            story_posted_timestamp=datetime.now(),
            slack_message_timestamp=None,
            instagram_timestamp=None,
            facebook_timestamp=None,
            reddit_timestamp=None,
            x_timestamp=None,
            threads_timestamp=None,
        )
        story.put()
    return story.to_dict()


def update_slack_details(url, timestamp):
    """
    Update the Slack message timestamp for a story with the given URL.

    Args:
        url: Story URL to update
        timestamp: DateTime timestamp for Slack message

    Returns:
        dict: Updated story as dictionary, or None if not found
    """
    with client.context():
        query = DiStorySocials.query().filter(DiStorySocials.story_url == url)
        story = query.get()
        if story:
            story.slack_message_timestamp = timestamp
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
        query = DiStorySocials.query().filter(DiStorySocials.story_url == url)
        story = query.get()
        if story:
            now = datetime.now()
            if social_media_name == "Slack":
                story.slack_message_timestamp = now
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
        stories = [story.to_dict() for story in DiStorySocials.query().fetch()]
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
            for story in DiStorySocials.query()
            .order(-DiStorySocials.story_posted_timestamp)
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
        query = DiStorySocials.query().filter(DiStorySocials.story_url == url)
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
        stories = DiStorySocials.query().fetch()
        for story in stories:
            story.key.delete()
    return "All social stories deleted"


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

        # Determine which timestamp field to check based on social media name
        if social_media_name == "Slack":
            timestamp_field = DiStorySocials.slack_message_timestamp
        elif social_media_name == "Instagram":
            timestamp_field = DiStorySocials.instagram_timestamp
        elif social_media_name == "Facebook":
            timestamp_field = DiStorySocials.facebook_timestamp
        elif social_media_name == "Reddit":
            timestamp_field = DiStorySocials.reddit_timestamp
        elif social_media_name == "X":
            timestamp_field = DiStorySocials.x_timestamp
        elif social_media_name == "Threads":
            timestamp_field = DiStorySocials.threads_timestamp
        else:
            raise ValueError(f"Invalid social media name: {social_media_name}")

        recent_posts = (
            DiStorySocials.query()
            .filter(
                timestamp_field >= start_datetime,
                timestamp_field <= current_datetime,
            )
            .fetch()
        )
    return len(recent_posts) >= limit
