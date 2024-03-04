from flask import Blueprint, render_template
from flask_login import login_required

retool_routes = Blueprint("retool_routes", __name__, url_prefix="/retool")

from util.fetch_retool import fetch_retool_embed_url
from constants import RETOOL_TOKEN

@retool_routes.route("/dashboard")
@login_required
def dashboard():
    try:
        embed_url = fetch_retool_embed_url(RETOOL_TOKEN)
        return render_template("retool.html", embed_url=embed_url)
    except Exception as e:
        return str(e), 500
