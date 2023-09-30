import json
import logging
import os
import urllib

from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user
)
from flask_seasurf import SeaSurf
from oauthlib.oauth2 import WebApplicationClient
import requests
from talisman import Talisman

# Local imports
from db.user import add_user, get_user
from oauth import get_google_provider_cfg
from views.illordle import illordle_routes
from views.socials import socials_routes
from views.users import users_routes


load_dotenv()
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)
app.register_blueprint(illordle_routes)
app.register_blueprint(socials_routes)
app.register_blueprint(users_routes)

# csp = {
#     'default-src': '*'
# }
Talisman(app, content_security_policy=[])
csrf = SeaSurf(app)

login_manager = LoginManager()
login_manager.init_app(app)

client = WebApplicationClient(GOOGLE_CLIENT_ID)


@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect('/login?state=' + urllib.parse.quote(request.path))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    state = request.args.get('state')

    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg['authorization_endpoint']

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + '/callback',
        scope=['openid', 'email', 'profile'],
        state=state
    )
    return redirect(request_uri)


@app.route('/login/callback')
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get('code')
    state = request.args.get('state')

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
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
    userinfo_endpoint = google_provider_cfg['userinfo_endpoint']
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body).json()

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.get('email_verified'):
        unique_id = userinfo_response['sub']
        users_email = userinfo_response['email']
        users_name = userinfo_response['name']

        # Create a user in your db with the information provided by Google
        user = get_user(users_email)
        if user is None:
            if users_email.endswith('@illinimedia.com'):
                user = add_user(sub=unique_id, name=users_name, email=users_email)
            else:
                return 'User email must end with @illinimedia.com for automatic registration.', 403
        elif user.sub is None:
            user = add_user(sub=unique_id, name=users_name, email=users_email)

        # Begin user session by logging the user in
        login_user(user)

        if state is not None:
            url = urllib.parse.unquote(state)
            parsed_url = urllib.parse.urlparse(url)
            if not (parsed_url.scheme or parsed_url.netloc):
                return redirect(url)
            else:
                return 'Illegal redirect URL.', 400

        return redirect(url_for('index'))
    else:
        return 'User email not available or not verified by Google.', 400


@app.route('/api-query')
@login_required
def api_query():
    return render_template('api_query.html')


@app.route('/logout')
@login_required
def logout():
    if current_user.email.endswith('@illinimedia.com'):
        logout_user()
        return redirect(url_for('yurr'))
    else:
        logout_user()
        return redirect(url_for('index'))


@app.route('/logout-success')
def yurr():
    return render_template('yurr.html')


if __name__ == '__main__':
    if os.environ.get('DATASTORE_EMULATOR_HOST') is None:
        logging.fatal('DATASTORE_EMULATOR_HOST environment variable must be set!')
        exit(1)
    app.run(port=5001, ssl_context='adhoc')
