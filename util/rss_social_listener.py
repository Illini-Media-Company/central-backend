"""
RSS feed listener for Daily Illini stories.

Fetches the Daily Illini RSS feed, filters out sponsored content,
and posts new stories to the social media Slack channel. 

Designed to be triggered via HTTP endpoint by Google Cloud Scheduler
to avoid duplicate runs across multiple App Engine instances.

Last modified by Jacob Slabosz on Feb 21, 2026
"""

from zoneinfo import ZoneInfo

import feedparser
import logging
from datetime import datetime, timezone
from util.helpers.ap_datetime import ap_daydatetime

logger = logging.getLogger(__name__)

RSS_URL = "https://dailyillini.com/feed/"


def is_sponsored(entry):
    """
    Check if an RSS entry is a sponsored post by examining tags and text content.
    """
    # Category tags
    if hasattr(entry, "tags"):
        for tag in entry.tags:
            if "sponsored" in tag.term.lower():
                return True

    # Title / summary text check
    text = (entry.title + " " + entry.get("summary", "")).lower()
    if "sponsored" in text or "paid content" in text:
        return True

    return False


def parse_date(entry):
    """
    Parse publication date from RSS entry, falling back to current UTC time if unavailable.
    """
    try:
        if hasattr(entry, "published"):
            dt_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt_utc.astimezone(ZoneInfo("America/Chicago"))
    except Exception:
        pass

    return datetime.now(ZoneInfo("America/Chicago"))


def fetch_rss():
    """
    Fetch and parse the Daily Illini RSS feed, returning all entries.
    """
    try:
        logger.info(f"Fetching RSS feed from {RSS_URL}")
        feed = feedparser.parse(RSS_URL)
        return feed.entries
    except Exception as e:
        logger.error(f"Failed to get RSS feed: {str(e)}")
        return []


def process_rss_item(entry):
    """
    Extract title, link, summary, and publication date from an RSS entry.
    """
    title = entry.title.strip()
    link = entry.link.strip()
    summary = entry.get("summary", "").strip()
    pub_date = parse_date(entry)

    return {
        "title": title,
        "link": link,
        "summary": summary,
        "pub_date": pub_date,
    }


def process_new_stories_to_slack():
    """
    Fetch RSS feed, filter sponsored posts, and post new stories to Slack.
    Adds new stories to database and notifies the social media channel.
    Returns (number_new_posted, list of story links posted).
    """
    from db.socials_poster import add_social_story, get_story_by_url
    from util.slackbots.socials_slackbot import notify_new_story_from_rss

    entries = fetch_rss()
    if not entries:
        return 0, []

    posted = []
    for entry in entries:
        if is_sponsored(entry):
            continue
        result = process_rss_item(entry)
        if not result:
            continue
        link = result.get("link", "").strip()
        title = result.get("title", "").strip()
        date = result.get("pub_date", "")
        if not link or not title:
            continue
        if get_story_by_url(link) is not None:
            continue
        add_social_story(link, title, date)
        notify_new_story_from_rss(
            story_url=link, story_title=title, post_date=ap_daydatetime(date)
        )
        posted.append(link)

    logger.info(f"RSS processing complete: {len(posted)} new stories posted to Slack")
    return len(posted), posted


if __name__ == "__main__":
    process_new_stories_to_slack()
