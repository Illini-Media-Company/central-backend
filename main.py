import json
import logging
import os
from threading import Thread
import urllib
import atexit
from datetime import datetime

from db import client as dbclient

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for,
    session,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests
from talisman import Talisman

# Local imports
import constants
from constants import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    TOOLS_ADMIN_ACCESS_GROUPS,
)
from db.user import (
    add_user,
    update_user,
    get_user,
    get_user_favorite_tools,
)
from util.security import (
    csrf,
    get_google_provider_cfg,
    is_user_in_group,
    update_groups,
)

from db.all_tools import (
    get_all_tools,
    get_all_tools_restricted,
    get_tool_by_uid,
)

from util.map_point import remove_point
from db.map_point import get_all_points
from util.gcal import get_allstaff_events

from db.json_store import json_store_set

from util.copy_editing import scheduler as copy_scheduler
from util.map_point import scheduler as map_scheduler
from util.scheduler import scheduler_to_json, db_to_scheduler
from apscheduler.triggers.date import DateTrigger

from util.slackbots.slackbot import start_slack
import util.slackbots.employee_agreement_slackbot
from views.all_tools import tools_routes
from views.content_doc import content_doc_routes
from views.constant_contact import constant_contact_routes
from views.illordle import illordle_routes
from views.socials import socials_routes
from views.retool_apps import retool_routes
from views.users import users_routes
from views.groups import groups_routes
from views.breaking_news import breaking_routes
from views.copy_schedule import copy_schedule_routes
from views.map_points import map_points_routes
from views.overlooked import overlooked_routes
from views.food_truck import food_truck_routes
from views.employee_agreement import employee_agreement_routes

from util.helpers.ap_datetime import (
    ap_datetime,
    ap_date,
    ap_time,
)

from util.all_tools import format_restricted_groups

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# csp = {
#     'default-src': '*'
# }
#
Talisman(app, content_security_policy=[])
csrf.init_app(app)

app.register_blueprint(tools_routes)
app.register_blueprint(content_doc_routes)
app.register_blueprint(constant_contact_routes)
app.register_blueprint(illordle_routes)
app.register_blueprint(socials_routes)
app.register_blueprint(retool_routes)
app.register_blueprint(users_routes)
app.register_blueprint(groups_routes)
app.register_blueprint(breaking_routes)
app.register_blueprint(copy_schedule_routes)
app.register_blueprint(map_points_routes)
app.register_blueprint(overlooked_routes)
app.register_blueprint(food_truck_routes)
app.register_blueprint(employee_agreement_routes)

login_manager = LoginManager()
login_manager.init_app(app)

client = WebApplicationClient(GOOGLE_CLIENT_ID)

start_slack(app)

# Regiser filters with Jinja
app.jinja_env.filters["ap_datetime"] = ap_datetime
app.jinja_env.filters["ap_date"] = ap_date
app.jinja_env.filters["ap_time"] = ap_time
app.jinja_env.filters["format_restricted_groups"] = format_restricted_groups


@atexit.register
def log_scheduler():
    maps = scheduler_to_json(map_scheduler)
    copy = scheduler_to_json(copy_scheduler)
    json_store_set("MAP_JOBS", maps)
    json_store_set("COPY_JOBS", copy)


@app.before_request
def track_url():
    current_url = request.url.removeprefix("https://app.dailyillini.com")

    url_prefix_ignore = ["/static", "/login", "/favicon.ico"]

    for url in url_prefix_ignore:
        if current_url.startswith(url):
            return

    if current_url == "/":
        return

    history = session.setdefault("url_history", [])
    history.insert(0, current_url)
    session["url_history"] = history[:10]
    session.modified = True


@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect("/login?state=" + urllib.parse.quote(request.path))


# Everythhing in this function will be available in all templates
@app.context_processor
def add_template_context():
    # Checks if the current user is in any of the groups passed in, calls a function from util/security.py
    def is_current_user_in_group(groups):
        if isinstance(groups, str):
            groups = [groups]
        return current_user.is_authenticated and is_user_in_group(current_user, groups)

    # Turns a Google Calendar ID into a URL
    def get_gcal_url(gcal_id):
        return f"https://calendar.google.com/calendar?cid={gcal_id}"

    # Things in this dict can be used/called from all templates, like the get_gcal_url function
    return dict(
        constants=constants,
        is_current_user_in_group=is_current_user_in_group,
        get_gcal_url=get_gcal_url,
    )


@app.route("/schedulers")
def schedulers():
    # whatever
    # token = request.args.get("token")
    # if token != os.environ.get("SCHEDULER_TOKEN"):
    #     return "Invalid token", 403
    # db_to_scheduler(map_scheduler, "MAP_JOBS")
    # db_to_scheduler(copy_scheduler, "COPY_JOBS")
    map_points = get_all_points()
    for point in map_points:
        if point["end_date"] < datetime.now():
            trigger = DateTrigger(point["end_date"], timezone="America/Chicago")
            map_scheduler.add_job(
                func=remove_point, args=[int(point["uid"])], trigger=trigger
            )
    return "Schedulers updated", 200


# Consider this to client-side fetching so that the page loads faster.
# i.e., render immediately, then have JavaScript call endpoints for those functions.
# However, then we can't use Jinja because it won't be filled
@app.route("/")
def index():
    if current_user.is_authenticated:
        upcoming_events = get_allstaff_events()

        # Get the user's favorite tools
        favorites_uids = get_user_favorite_tools(current_user.email)
        favorites = []
        for uid in favorites_uids:
            with dbclient.context():
                favorites.append(get_tool_by_uid(uid))

        if is_user_in_group(
            current_user, TOOLS_ADMIN_ACCESS_GROUPS
        ):  # These are the groups that can view all tools
            print("Passing all tools")
            with dbclient.context():
                tools = get_all_tools()
                admin = True
        else:
            print("Passing filtered tools")
            with dbclient.context():
                tools = get_all_tools_restricted()
                admin = False
    else:
        print("Passing no tools")
        upcoming_events = []
        favorites = []
        tools = {}
        admin = False
    return render_template(
        "index.html",
        upcoming_events=upcoming_events,
        tools=tools,
        admin=admin,
        favorites=favorites,
    )


@app.route("/login")
def login():
    state = request.args.get("state")

    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
        state=state,
    )
    return redirect(request_uri)


@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    state = request.args.get("state")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body).json()

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.get("email_verified"):
        unique_id = userinfo_response["sub"]
        user_email = userinfo_response["email"]
        user_name = userinfo_response["name"]
        user_picture = userinfo_response["picture"]
        user_domain = userinfo_response.get("hd", "")

        # Create or update user in db
        user = get_user(user_email)
        # If the user does not already exist
        if user is None:
            if user_domain == "illinimedia.com":
                user = add_user(
                    sub=unique_id,
                    name=user_name,
                    email=user_email,
                    picture=user_picture,
                    groups=[],
                )
            else:
                return (
                    "User must be a member of Illini Media for automatic registration.",
                    403,
                )
        # If we don't already store sub (a unique identifier for the user)
        elif user.sub is None:
            user = add_user(
                sub=unique_id,
                name=user_name,
                email=user_email,
                picture=user_picture,
                groups=[],
            )
        # Otherwise, make sure we have the most recent name and email
        else:
            user = update_user(
                name=user_name,
                email=user_email,
                picture=user_picture,
            )

        # Create new thread to sync user's group memberships
        thread = Thread(target=update_groups, args=[user_email])
        thread.start()

        # Begin user session by logging the user in
        login_user(user)

        if state is not None:
            url = urllib.parse.unquote(state)
            parsed_url = urllib.parse.urlparse(url)
            if not (parsed_url.scheme or parsed_url.netloc):
                return redirect(url)
            else:
                return "Illegal redirect URL.", 400

        return redirect(url_for("index"))
    else:
        return "User email not available or not verified by Google.", 400


@app.route("/url-history")
@login_required
def url_history():
    url_history = session.get("url_history", [])
    return render_template("url_history.html", url_history=url_history)


@app.route("/api-query")
@login_required
def api_query():
    return render_template("api_query.html")


@app.route("/logout")
@login_required
def logout():
    if current_user.email.endswith("@illinimedia.com"):
        logout_user()
        return redirect(url_for("yurr"))
    else:
        logout_user()
        return redirect(url_for("index"))


@app.route("/logout-success")
def yurr():
    return render_template("yurr.html")


if __name__ == "__main__":
    if os.environ.get("DATASTORE_EMULATOR_HOST") is None:
        logging.fatal("DATASTORE_EMULATOR_HOST environment variable must be set!")
        exit(1)
    app.jinja_env.auto_reload = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    try:
        db_to_scheduler(map_scheduler, "MAP_JOBS")
        db_to_scheduler(copy_scheduler, "COPY_JOBS")
    except Exception as e:
        print(f"{e} no jobs to import")
    app.run(port=5001, ssl_context="adhoc")
