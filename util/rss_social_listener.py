import feedparser
from datetime import datetime
import logging

import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

RSS_URL = "https://dailyillini.com/feed/"


def is_sponsored(entry):
    """
    Returns True if sponsored post
    Checks categories and text for keywords
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
    Parse the date but fall back to UTC if not there
    """
    try:
        if hasattr(entry, "published"):
            return datetime(*entry.published_parsed[:6])
    except Exception:
        pass

    return datetime.utcnow()


def fetch_rss():
    """
    Fetch current RSS feed and return the list of items
    """
    try:
        feed = feedparser.parse(RSS_URL)
        return feed.entries
    except Exception as e:
        logging.error(f"Failed to get RSS feed: {e}")
        return []


def process_rss_item(entry):
    """
    RSS item processing to get title/linl/publication date
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


def check_rss_feed():
    """
    current function used by /socials/check-rss.
    processes RSS entries
    """
    logging.info("Checking RSS feed")

    entries = fetch_rss()

    if not entries:
        logging.info("No RSS entries found.")
        return 0, []

    processed_items = []
    processed_count = 0

    for entry in entries:
        # sponsored filter
        if is_sponsored(entry):
            logging.info(f"Skipping sponsored article: {entry.title}")
            continue
        result = process_rss_item(entry)
        if result:
            processed_items.append(result)
            processed_count += 1

    logging.info(f"Completed RSS check — processed {processed_count} stories")
    return processed_count, processed_items


def process_new_stories_to_slack():
    """
    Fetch RSS, filter sponsored, and for each story not already in DiSocialStory
    add the story and post to the social media Slack channel.
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
        logging.info(f"Posted new story to Slack: {title}")

    return len(posted), posted


_rss_scheduler = BackgroundScheduler(timezone="America/Chicago")


def _rss_job():
    try:
        count, posted = process_new_stories_to_slack()
        logging.info(f"[rss_listener] ran: new={count}")
    except Exception:
        logging.exception("[rss_listener] job failed")


def start_rss_listener():
    if getattr(_rss_scheduler, "running", False):
        return

    minutes = int(os.environ.get("RSS_POLL_MINUTES", "5"))

    _rss_scheduler.add_job(
        _rss_job,
        trigger=IntervalTrigger(minutes=minutes),
        id="rss_social_listener",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _rss_scheduler.start()
    logging.info(f"[rss_listener] started (every {minutes} min)")


if __name__ == "__main__":
    count, links = process_new_stories_to_slack()
    print(f"Posted {count} new stories to Slack: {links}")
