from flask import (
    Blueprint,
    render_template
)
from flask_login import login_required


illordle_routes = Blueprint('illordle_routes', __name__, url_prefix='/illordle')


@illordle_routes.route('/dashboard')
@login_required
def dashboard():
    return render_template('illordle.html')
