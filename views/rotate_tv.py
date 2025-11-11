from flask import request, render_template, Blueprint
from util.helpers.ap_datetime import ap_date
from util.gcal import get_resource_events_today
from datetime import datetime
from zoneinfo import ZoneInfo

NEWS_CONF_RESOURCE_GCAL_ID = (
    "c_1880trl645hpqj39k57idpvutni6g@resource.calendar.google.com"
)
BIS_CONF_RESOURCE_GCAL_ID = (
    "c_188756k7nm7tkgu4gpsiqsb07802a@resource.calendar.google.com"
)
WPGU_OFFICE_RESOURCE_GCAL_ID = (
    "c_188ejl7c2di5uisrjp7qdcu8f7pto@resource.calendar.google.com"
)
WPGU_ONAIR_GCAL_ID = "c_b888554deb36a74a61aea32bac28ab500ade0003cd2ae61085354e07c2fa0fa0@group.calendar.google.com"


rotate_tv_routes = Blueprint("rotate_tv_routes", __name__, url_prefix="/tv-rotation")


@rotate_tv_routes.route("/dashboard", methods=["GET"])
def tv_rotation_dashboard():
    return render_template("rotatingtv_dash.html")


@rotate_tv_routes.route("/screen", methods=["GET"])
def tv_rotation_screen():
    g = request.args.get
    b = (
        lambda key: g(key, "false").lower() == "true"
    )  # "true" -> True, everything else -> False

    show_quad = b("show_quad")
    show_alma = b("show_alma")
    show_datetime = b("show_datetime")
    show_nc_avail = b("show_nc_avail")  # News conference table availability
    show_bc_avail = b("show_bc_avail")  # Business conference table availability
    show_pgu_avail = b("show_pgu_avail")  # WPGU office availability
    show_pgu_onair = b("show_pgu_onair")  # WPGU on-air calendar

    # Get the current date in AP Style
    current_date = ap_date(datetime.now(ZoneInfo("America/Chicago")))

    # Check which events to show
    if show_nc_avail:
        avail_events = get_resource_events_today(NEWS_CONF_RESOURCE_GCAL_ID, 9, 21)
        show_avail = True
        avail_header_text = "News Conference Table"
        avail_subtext = "Availability"
    elif show_bc_avail:
        avail_events = get_resource_events_today(BIS_CONF_RESOURCE_GCAL_ID, 9, 21)
        show_avail = True
        avail_header_text = "Business Conference Table"
        avail_subtext = "Availability"
    elif show_pgu_avail:
        avail_events = get_resource_events_today(WPGU_OFFICE_RESOURCE_GCAL_ID, 9, 21)
        show_avail = True
        avail_header_text = "WPGU Office"
        avail_subtext = "Availability"
    else:
        show_avail = False
        avail_events = None
        avail_header_text = None
        avail_subtext = None

    if show_pgu_onair:
        onair_events1 = get_resource_events_today(WPGU_ONAIR_GCAL_ID, 0, 12)
        onair_events2 = get_resource_events_today(WPGU_ONAIR_GCAL_ID, 12, 24)
        show_onair = True
    else:
        show_onair = False
        onair_events1 = None
        onair_events2 = None

    return render_template(
        "rotatingtv_display.html",
        rotate_ms=30000,
        show_quad=show_quad,
        show_alma=show_alma,
        show_datetime=show_datetime,
        current_date=current_date,
        show_avail=show_avail,
        avail_events=avail_events,
        avail_header_text=avail_header_text,
        avail_subtext=avail_subtext,
        show_onair=show_onair,
        onair_events1=onair_events1,
        onair_events2=onair_events2,
    )
