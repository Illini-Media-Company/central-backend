import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from constants import ADVERTISER_METRICS_RANGE_OPTIONS, ADVERTISER_METRICS_SITES
from db.json_store import json_store_get, json_store_set
from util.google_analytics import normalize_run_report, run_ga4_report
from util.security import csrf


logger = logging.getLogger(__name__)

advertiser_metrics_api_routes = Blueprint(
    "advertiser_metrics_api_routes", __name__, url_prefix="/api/advertiser-metrics"
)

CACHE_VERSION = "v1"
CACHE_TTLS = {
    "overview": timedelta(minutes=30),
    "timeseries": timedelta(minutes=30),
    "top-pages": timedelta(hours=1),
    "referrers": timedelta(hours=1),
}

COMING_SOON_MESSAGE = "Analytics will appear once this site starts sending data."
PUBLIC_ERROR_MESSAGE = "Advertiser metrics are temporarily unavailable."
CHICAGO_TZ = ZoneInfo("America/Chicago")


@advertiser_metrics_api_routes.route("/sites", methods=["GET"])
@cross_origin()
@csrf.exempt
def list_sites():
    now = _utcnow()
    return (
        jsonify(
            {
                "sites": [
                    _public_site(site_key, site)
                    for site_key, site in ADVERTISER_METRICS_SITES.items()
                ],
                "updated_at": _isoformat(now),
                "cached_until": _isoformat(now),
            }
        ),
        200,
    )


@advertiser_metrics_api_routes.route("/overview", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_overview():
    return _report_response("overview", _fetch_overview)


@advertiser_metrics_api_routes.route("/timeseries", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_timeseries():
    return _report_response("timeseries", _fetch_timeseries)


@advertiser_metrics_api_routes.route("/top-pages", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_top_pages():
    return _report_response("top-pages", _fetch_top_pages)


@advertiser_metrics_api_routes.route("/referrers", methods=["GET"])
@cross_origin()
@csrf.exempt
def get_referrers():
    return _report_response("referrers", _fetch_referrers)


def _report_response(report_type, fetch_report):
    site_key = (request.args.get("site") or "").strip()
    range_key = (request.args.get("range") or "30d").strip()

    validation_error = _validate_report_request(site_key, range_key)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    site = ADVERTISER_METRICS_SITES[site_key]
    date_range = _date_range(range_key)

    if not site.get("has_data", False):
        return (
            jsonify(_coming_soon_response(report_type, site_key, site, range_key)),
            200,
        )

    cached = _get_cached_report(report_type, site_key, range_key)
    if cached:
        return jsonify(cached), 200

    try:
        payload = fetch_report(site_key, site, range_key, date_range)
    except Exception:
        logger.exception(
            "Failed to fetch advertiser metrics report",
            extra={"report_type": report_type, "site": site_key, "range": range_key},
        )
        return jsonify({"error": PUBLIC_ERROR_MESSAGE}), 502

    _set_cached_report(report_type, site_key, range_key, payload)
    return jsonify(payload), 200


def _validate_report_request(site_key, range_key):
    if site_key not in ADVERTISER_METRICS_SITES:
        return "Invalid site."
    if range_key not in ADVERTISER_METRICS_RANGE_OPTIONS:
        return "Invalid range."
    return None


def _fetch_overview(site_key, site, range_key, date_range):
    response = run_ga4_report(
        property_id=site["property_id"],
        date_range=date_range,
        metrics=[
            "screenPageViews",
            "activeUsers",
            "sessions",
            "engagementRate",
            "averageSessionDuration",
        ],
    )
    rows = normalize_run_report(response)
    totals = rows[0]["metrics"] if rows else {}
    return _base_response("overview", site_key, site, range_key, date_range) | {
        "totals": {
            "screenPageViews": totals.get("screenPageViews", 0),
            "activeUsers": totals.get("activeUsers", 0),
            "sessions": totals.get("sessions", 0),
            "engagementRate": totals.get("engagementRate", 0.0),
            "averageSessionDuration": totals.get("averageSessionDuration", 0.0),
        },
        "rows": [],
    }


def _fetch_timeseries(site_key, site, range_key, date_range):
    response = run_ga4_report(
        property_id=site["property_id"],
        date_range=date_range,
        dimensions=["date"],
        metrics=["screenPageViews", "activeUsers", "sessions"],
        order_bys=[{"dimension": {"dimensionName": "date"}}],
    )
    rows = [
        {
            "date": _format_ga_date(row["dimensions"].get("date")),
            "screenPageViews": row["metrics"].get("screenPageViews", 0),
            "activeUsers": row["metrics"].get("activeUsers", 0),
            "sessions": row["metrics"].get("sessions", 0),
        }
        for row in normalize_run_report(response)
    ]
    return _base_response("timeseries", site_key, site, range_key, date_range) | {
        "totals": {},
        "rows": rows,
    }


def _fetch_top_pages(site_key, site, range_key, date_range):
    response = run_ga4_report(
        property_id=site["property_id"],
        date_range=date_range,
        dimensions=["pagePath", "pageTitle"],
        metrics=["screenPageViews", "activeUsers", "sessions"],
        limit=10,
        order_bys=[{"metric": {"metricName": "screenPageViews"}, "desc": True}],
    )
    rows = [
        {
            "pagePath": row["dimensions"].get("pagePath", ""),
            "pageTitle": row["dimensions"].get("pageTitle", ""),
            "screenPageViews": row["metrics"].get("screenPageViews", 0),
            "activeUsers": row["metrics"].get("activeUsers", 0),
            "sessions": row["metrics"].get("sessions", 0),
        }
        for row in normalize_run_report(response)
    ]
    return _base_response("top-pages", site_key, site, range_key, date_range) | {
        "totals": {},
        "rows": rows,
    }


def _fetch_referrers(site_key, site, range_key, date_range):
    response = run_ga4_report(
        property_id=site["property_id"],
        date_range=date_range,
        dimensions=["sessionSourceMedium"],
        metrics=["sessions", "activeUsers"],
        limit=10,
        order_bys=[{"metric": {"metricName": "sessions"}, "desc": True}],
    )
    rows = [
        {
            "sourceMedium": row["dimensions"].get("sessionSourceMedium", ""),
            "sessions": row["metrics"].get("sessions", 0),
            "activeUsers": row["metrics"].get("activeUsers", 0),
        }
        for row in normalize_run_report(response)
    ]
    return _base_response("referrers", site_key, site, range_key, date_range) | {
        "totals": {},
        "rows": rows,
    }


def _base_response(report_type, site_key, site, range_key, date_range):
    now = _utcnow()
    ttl = CACHE_TTLS[report_type]
    return {
        "site": site_key,
        "name": site["name"],
        "has_data": True,
        "report": report_type,
        "range": range_key,
        "range_label": ADVERTISER_METRICS_RANGE_OPTIONS[range_key]["label"],
        "date_range": date_range,
        "updated_at": _isoformat(now),
        "cached_until": _isoformat(now + ttl),
    }


def _coming_soon_response(report_type, site_key, site, range_key):
    now = _utcnow()
    return {
        "site": site_key,
        "name": site["name"],
        "has_data": False,
        "report": report_type,
        "range": range_key,
        "range_label": ADVERTISER_METRICS_RANGE_OPTIONS[range_key]["label"],
        "date_range": _date_range(range_key),
        "updated_at": _isoformat(now),
        "cached_until": _isoformat(now),
        "message": COMING_SOON_MESSAGE,
        "totals": {},
        "rows": [],
    }


def _public_site(site_key, site):
    return {
        "site": site_key,
        "name": site["name"],
        "has_data": bool(site.get("has_data", False)),
    }


def _date_range(range_key):
    days = ADVERTISER_METRICS_RANGE_OPTIONS[range_key]["days"]
    end_date = datetime.now(CHICAGO_TZ).date()
    start_date = end_date - timedelta(days=days - 1)
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def _get_cached_report(report_type, site_key, range_key):
    try:
        cached = json_store_get(_cache_key(report_type, site_key, range_key))
    except Exception:
        logger.exception(
            "Failed to read advertiser metrics cache",
            extra={"report_type": report_type, "site": site_key, "range": range_key},
        )
        return None

    if not cached:
        return None

    expires_at = _parse_iso(cached.get("expires_at"))
    payload = cached.get("payload")
    if not expires_at or not payload:
        return None

    if expires_at <= _utcnow():
        return None

    return payload


def _set_cached_report(report_type, site_key, range_key, payload):
    try:
        json_store_set(
            _cache_key(report_type, site_key, range_key),
            {
                "expires_at": payload["cached_until"],
                "payload": payload,
            },
        )
    except Exception:
        logger.exception(
            "Failed to write advertiser metrics cache",
            extra={"report_type": report_type, "site": site_key, "range": range_key},
        )


def _cache_key(report_type, site_key, range_key):
    return f"ADVERTISER_METRICS:{CACHE_VERSION}:{report_type}:{site_key}:{range_key}"


def _format_ga_date(value):
    if not value or len(value) != 8:
        return value
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def _utcnow():
    return datetime.now(timezone.utc)


def _isoformat(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None
