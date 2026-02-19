"""
RSS feed listener for Daily Illini stories.

Periodically fetches the Daily Illini RSS feed, filters out sponsored content,
and posts new stories to the social media Slack channel. Runs automatically
via a background scheduler when the app starts.

Last modified by Aryaa Rathi on Feb 19, 2026
"""

import feedparser
import traceback
from datetime import datetime
from db.json_store import json_store_set
from util.scheduler import scheduler_to_json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
            return datetime(*entry.published_parsed[:6])
    except Exception:
        pass

    return datetime.utcnow()


def fetch_rss():
    """
    Fetch and parse the Daily Illini RSS feed, returning all entries.
    """
    try:
        feed = feedparser.parse(RSS_URL)
        return feed.entries
    except Exception as e:
        print(f"[rss_listener] Failed to get RSS feed: {e}")
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
        "pub_date": pub_date.isoformat(),
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
        if not link or not title:
            continue
        if get_story_by_url(link) is not None:
            continue
        add_social_story(link, title)
        notify_new_story_from_rss(story_url=link, story_title=title)
        posted.append(link)

    return len(posted), posted


_rss_scheduler = BackgroundScheduler(timezone="America/Chicago")


def _rss_job():
    """
    Scheduled job that runs periodically to check RSS feed and post new stories to Slack.
    """
    try:
        process_new_stories_to_slack()
    except Exception:
        traceback.print_exc()


_minutes = 45
_rss_scheduler.add_job(
    _rss_job,
    trigger=IntervalTrigger(minutes=_minutes),
    id="rss_social_listener",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)

_rss_scheduler.start()
rss_json = scheduler_to_json(_rss_scheduler)
json_store_set("RSS_JOBS", rss_json, replace=True)
print(f"[rss_listener] started (every {_minutes} min)")


if __name__ == "__main__":
    process_new_stories_to_slack()
