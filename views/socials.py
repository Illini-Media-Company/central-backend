from flask import (
    Blueprint,
    render_template
)
from flask_login import login_required


socials_routes = Blueprint('socials_routes', __name__, url_prefix='/socials')


@socials_routes.route('/dashboard')
@login_required
def dashboard():
    return render_template('socials.html')
