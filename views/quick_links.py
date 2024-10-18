from flask import Blueprint, render_template, request
from flask_login import login_required

from db.quick_link import get_all_quick_links, add_quick_link, remove_quick_link
from db.group import get_all_groups
from util.security import restrict_to


quick_links_routes = Blueprint(
    "quick_links_routes", __name__, url_prefix="/quick-links"
)


@quick_links_routes.route("/dashboard", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def dashboard():
    # TODO: Create dashboard for editing quick links
    links = get_all_quick_links()
    groups = get_all_groups()
    return render_template("quicklink.html", links=links, groups=groups)


@quick_links_routes.route("", methods=["GET"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def list_quick_links():
    return get_all_quick_links()


@quick_links_routes.route("/submit", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def create_quick_link():
    name = request.form["name"]
    url = request.form["url"]
    group = request.form.get("group", None)

    return add_quick_link(name, url, group)


@quick_links_routes.route("/<uid>/delete", methods=["POST"])
@login_required
@restrict_to(["student-managers", "editors", "imc-staff-webdev"])
def delete_quick_link(uid):
    if remove_quick_link(int(uid)):
        return "Quick link deleted.", 200
    else:
        return "Quick link not found.", 404
