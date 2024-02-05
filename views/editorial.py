import requests
import re

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

editorial_routes = Blueprint("editorial_routes", __name__, url_prefix="/editorial")

@editorial_routes.route("")
@login_required
def editorial():
    return render_template("editorial.html")
