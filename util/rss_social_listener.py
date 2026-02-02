import feedparser
from datetime import datetime
import logging

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


if __name__ == "__main__":
    count = check_rss_feed()
    print(f"Processed {count} stories.")
