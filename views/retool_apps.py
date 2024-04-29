from flask import Blueprint, render_template
from flask_login import login_required

from util.retool import fetch_retool_embed_url
from util.security import restrict_to


retool_routes = Blueprint("retool_routes", __name__, url_prefix="/retool")


@retool_routes.route("/wpgu-website")
@login_required
@restrict_to(["wpgu-all-staff", "webdev", "imc-staff-webdev"])
def wpgu_website():
    embed_url = fetch_retool_embed_url("0afdf92e-b0d4-11ee-ab5f-83b642f596fa")
    return render_template(
        "retool.html", title="WPGU Website Settings", embed_url=embed_url
    )
