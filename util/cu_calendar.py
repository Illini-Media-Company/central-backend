"""
Utility functions for the CU Calendar feature.

Includes geocoding addresses, Google Cloud Storage logic, and parsing Google Calendar URLs.
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo

import googlemaps
from google.cloud import storage
from gcsa.google_calendar import GoogleCalendar

from constants import GCS_BUCKET_NAME, BACKEND_GOOGLE_MAP_API
from util.security import get_creds


GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def geocode_address(address):
    api_key = BACKEND_GOOGLE_MAP_API
    if not api_key:
        print("Error: Google API key not found.")
        return None

    gmaps = googlemaps.Client(key=api_key)
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            return location["lat"], location["lng"]
        else:
            return None
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return None


def upload_images_to_gcs(files):
    if not files:
        return []
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    uploaded_urls = []
    for file in files:
        if file.filename == "":
            continue

        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{ext}"
        blob = bucket.blob(unique_filename)
        blob.upload_from_file(file)
        blob.make_public()

        uploaded_urls.append(blob.public_url)
    return uploaded_urls


def delete_images_from_gcs(image_urls):
    if not image_urls:
        return
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    for url in image_urls:
        try:
            blob_name = url.split(f"{GCS_BUCKET_NAME}/")[-1]
            blob = bucket.blob(blob_name)
            if blob.exists():
                blob.delete()
                print(f"Deleted image from GCS: {blob_name}")
        except Exception as e:
            print(f"Error deleting image {url} from GCS: {e}")


def _parse_calendar_id_from_url(gcal_url: str) -> Optional[str]:
    """
    Extract calendar ID from a Google Calendar URL.
    Supports:
    1. Embed / public view: .../calendar/embed?src=CALENDAR_ID&ctz=...
    2. Public iCal feed: .../calendar/ical/CALENDAR_ID/public/basic.ics
    """
    if not gcal_url or not isinstance(gcal_url, str):
        return None
    parsed = urlparse(gcal_url.strip())
    # Embed / public view: ?src=CALENDAR_ID (optional &ctz=...)
    if parsed.query:
        params = parse_qs(parsed.query)
        src_list = params.get("src")
        if src_list and src_list[0]:
            return unquote(src_list[0].strip())

    # Public iCal: /calendar/ical/CALENDAR_ID/public/basic.ics
    path = parsed.path or ""
    if "/ical/" in path:
        parts = path.split("/ical/", 1)[1].split("/", 1)
        if parts[0]:
            return unquote(parts[0].strip())
    return None


def gcal_to_events(gcal_url: str, future_days: int = 365) -> Optional[List[dict]]:
    """
    Parse a Google Calendar URL to extract the calendar ID, fetch events,
    and return a list of events compatible with the view.
    future_days: how many days ahead to fetch (default 365 = next year).
    Returns list of dicts with: title, start_date, end_date, address,
    description. Returns None if URL parsing or API access fails.
    """
    calendar_id = _parse_calendar_id_from_url(gcal_url)
    if not calendar_id:
        return None
    try:
        creds = get_creds(GCAL_SCOPES)
        gc = GoogleCalendar(calendar_id, credentials=creds)
    except Exception:
        return None

    tz = ZoneInfo("America/Chicago")
    time_min = datetime.now(tz)
    time_max = datetime.now(tz) + timedelta(days=future_days)
    try:
        events_iter = gc.get_events(
            time_min=time_min,
            time_max=time_max,
            single_events=True,
            order_by="startTime",
        )
    except Exception:
        return None

    result = []
    for event in events_iter:
        start = event.start
        end = event.end
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        elif isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=tz).astimezone(timezone.utc)
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
        elif isinstance(end, datetime) and end.tzinfo is None:
            end = end.replace(tzinfo=tz).astimezone(timezone.utc)

        result.append(
            {
                "title": (event.summary or "").strip(),
                "start_date": start,
                "end_date": end,
                "address": (event.location or "").strip() if event.location else "",
                "description": (event.description or "").strip()
                if event.description
                else "",
            }
        )
    return result


def sync_gcal_sources(*, future_days: int = 30) -> int:
    """
    Sync all stored Google Calendar sources: fetch events from each gcal URL,
    add any new events that are not already in the database.
    Returns the total number of new events added.
    """
    from db.cu_calender import (
        add_event,
        event_exists,
        get_all_calendar_sources,
    )

    sources = get_all_calendar_sources()
    total_added = 0

    for source in sources:
        gcal_url = source.get("gcal_url")
        company = source.get("company_name", "")
        if not gcal_url:
            continue

        parsed_events = gcal_to_events(gcal_url, future_days=future_days)
        if parsed_events is None:
            continue

        for event in parsed_events:
            if event_exists(gcal_url, event.get("title", ""), event.get("start_date")):
                continue

            coords = geocode_address(event.get("address") or "")
            if not coords:
                continue

            lat, lng = coords
            add_event(
                title=event.get("title", ""),
                lat=lat,
                long=lng,
                url=gcal_url,
                start_date=event.get("start_date"),
                end_date=event.get("end_date"),
                images=[],
                address=event.get("address", ""),
                event_type="Imported",
                description=event.get("description", ""),
                company_name=company,
                is_accepted=True,
            )
            total_added += 1

    return total_added
