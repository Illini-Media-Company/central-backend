from flask import request, render_template, Blueprint
from util.helpers.ap_datetime import ap_date
from datetime import datetime
from zoneinfo import ZoneInfo


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

    show_stats = b("show_stats")
    show_quad = b("show_quad")
    show_alma = b("show_alma")
    show_datetime = b("show_datetime")
    show_nc_avail = b("show_nc_avail")      # News conference table availability
    show_bc_avail = b("show_bc_avail")      # Business conference table availability

    if show_datetime:
        current_date = ap_date(datetime.now(ZoneInfo("America/Chicago")))
    else:
        current_date = None

    return render_template(
        "rotatingtv_display.html",
        rotate_ms=30000,
        show_stats=show_stats,
        show_quad=show_quad,
        show_alma=show_alma,
        show_datetime=show_datetime,
        show_nc_avail=show_nc_avail,
        show_bc_avail=show_bc_avail,
        current_date=current_date,
    )
