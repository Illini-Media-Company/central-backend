from flask import request, render_template, Blueprint


rotate_tv_routes = Blueprint("rotate_tv_routes", __name__, url_prefix="/tv-rotation")


@rotate_tv_routes.route("/dashboard", methods=["GET"])
def tv_rotation_dashboard():
    return render_template("rotatingtv_screen.html")


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
    show_room = b("show_room")
    show_news = b("show_news")

    enabled_sections = [
        key
        for key, on in [
            ("stats", show_stats),
            ("quad", show_quad),
            ("alma", show_alma),
            ("datetime", show_datetime),
            ("room", show_room),
            ("news", show_news),
        ]
        if on
    ]

    print(
        f"{show_stats}, {show_quad}, {show_alma},  {show_datetime},  {show_room}, {show_news}"
    )
    return render_template(
        "rotatingtv_display.html",
        enabled_sections=enabled_sections,
        rotate_ms=30000,
        show_stats=show_stats,
        show_quad=show_quad,
        show_alma=show_alma,
        show_datetime=show_datetime,
        show_room=show_room,
        show_news=show_news,
    )
