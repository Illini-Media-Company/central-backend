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


@employee_management_routes.route("/employee/create", methods=["POST"])
@login_required
@restrict_to(["imc-staff-webdev"])
def create_employee():
    with client.context():
        last_name = request.form["last_name"]
        first_name = request.form["first_name"]
        imc_email = request.form["imc_email"]
        phone = request.form["phone"]
        personal_email = request.form["personal_email"]
        hire_date = datetime.strptime(request.form["hire_date"], "%Y-%m-%d")

        create_employee(
            last_name=last_name,
            first_name=first_name,
            imc_email=imc_email,
            phone=phone,
            personal_email=personal_email,
            hire_date=hire_date,
        )

    return "Employee created.", 200


@employee_management_routes.route("/employee/get-all", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev"])
def get_all_employees():
    with client.context():
        employees = get_all_employees()
    return jsonify(employees), 200
