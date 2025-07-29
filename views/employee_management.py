from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from flask_cors import cross_origin

from db.employee_management.employee_card import create_employee
from db.employee_management.position_assignment import (
    create_position_assignment,
    close_position_assignment,
)
from db.employee_management.position_type import create_position_type

from util.security import restrict_to, csrf
from datetime import datetime
from db import client

employee_management_routes = Blueprint(
    "employee_management_routes", __name__, url_prefix="/ems"
)
