#
#
# Create Dec. 9, 2025 by Jacob Slabosz
# Last updated Dec. 9, 2025

from flask import request
import requests

from constants import IMC_CONSOLE_GOOGLE_ANALYTICS_KEY


def send_ga4_event(name: str, measurement_id: str, params: dict):
    """
    Sends a new GA4 event to Google Analytics with given parameters. Useful for server-side event
    tracking of things Google Analytics cannot natively track, like API calls.

    :param name: A name for the event. Cannot contain spaces. Should be alphanumeric, all
        lowercase. Underscores are also allowed.
    :type name: str
    :param measurement_id: The GA4 Measurement ID for the property (e.g., "G-XXXXXXXXXX")
    :type measurement_id: str
    :param params: Description
    :type params: dict
    """
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={IMC_CONSOLE_GOOGLE_ANALYTICS_KEY}"
    payload = {
        "client_id": request.remote_addr,
        "events": [{"name": name, "params": params}],
    }
    requests.post(url, json=payload)
