#
#
# Create Dec. 9, 2025 by Jacob Slabosz
# Last updated Dec. 9, 2025

from flask import request
import requests

from constants import IMC_CONSOLE_GOOGLE_ANALYTICS_KEY


ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def send_ga4_event(name: str, measurement_id: str, params: dict, client_id: str = None):
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
        "client_id": client_id or request.remote_addr,
        "events": [{"name": name, "params": params}],
    }
    requests.post(url, json=payload)


def run_ga4_report(
    property_id: str,
    date_range: dict,
    metrics: list[str],
    dimensions: list[str] | None = None,
    limit: int | None = None,
    order_bys: list[dict] | None = None,
):
    """
    Runs a fixed Google Analytics Data API report for a GA4 property.
    """
    from googleapiclient.discovery import build
    from util.security import get_creds

    body = {
        "dateRanges": [
            {
                "startDate": date_range["start_date"],
                "endDate": date_range["end_date"],
            }
        ],
        "metrics": [{"name": metric} for metric in metrics],
    }

    if dimensions:
        body["dimensions"] = [{"name": dimension} for dimension in dimensions]
    if limit:
        body["limit"] = limit
    if order_bys:
        body["orderBys"] = order_bys

    service = build(
        "analyticsdata",
        "v1beta",
        credentials=get_creds([ANALYTICS_READONLY_SCOPE]),
        cache_discovery=False,
    )
    return (
        service.properties()
        .runReport(property=f"properties/{property_id}", body=body)
        .execute()
    )


def normalize_run_report(response: dict) -> list[dict]:
    """
    Converts a GA4 runReport response into row dictionaries with dimensions and metrics.
    """
    dimension_names = [
        header.get("name") for header in response.get("dimensionHeaders", [])
    ]
    metric_names = [header.get("name") for header in response.get("metricHeaders", [])]

    rows = []
    for row in response.get("rows", []):
        dimensions = {
            name: value.get("value", "")
            for name, value in zip(dimension_names, row.get("dimensionValues", []))
            if name
        }
        metrics = {
            name: _parse_metric_value(name, value.get("value", "0"))
            for name, value in zip(metric_names, row.get("metricValues", []))
            if name
        }
        rows.append({"dimensions": dimensions, "metrics": metrics})

    return rows


def _parse_metric_value(metric_name: str, value: str):
    int_metrics = {
        "activeUsers",
        "eventCount",
        "newUsers",
        "screenPageViews",
        "sessions",
    }
    float_metrics = {
        "averageSessionDuration",
        "engagementRate",
    }

    if metric_name in int_metrics:
        return int(float(value or 0))
    if metric_name in float_metrics:
        return float(value or 0)

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return value

    if parsed.is_integer():
        return int(parsed)
    return parsed
