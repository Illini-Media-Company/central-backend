"""
This file defines the API for the Employee Management System.

Created by Jacob Slabosz on Jan. 12, 2026
Last modified Jan. 12, 2026
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from util.security import restrict_to
from datetime import datetime

from constants import EMS_ADMIN_ACCESS_GROUPS

from db.employee_management import (
    create_employee_card,
    modify_employee_card,
    get_all_employee_cards,
    get_employee_card_by_id,
)

from constants import (
    EMPLOYEE_STATUS_OPTIONS,
    EMPLOYEE_GRAD_YEARS,
    EMPLOYEE_PRONOUNS,
)

ems_routes = Blueprint("ems_routes", __name__, url_prefix="/ems")


# TEMPLATE
@ems_routes.route("/", methods=["GET"])
@login_required
def ems_dashboard():
    """
    Renders the Employee Management System dashboard.
    """
    return render_template("employee_management/ems_base.html", selection="dash")


################################################################################
### EMPLOYEE FUNCTIONS #########################################################
################################################################################


# TEMPLATE
@ems_routes.route("/employees", methods=["GET"])
@login_required
def ems_employees():
    """
    Renders the Employee Management System employees page.
    """
    all_employees = get_all_employee_cards()
    return render_template(
        "employee_management/ems_employees.html",
        selection="employees",
        selected_employees=all_employees,
    )


# TEMPLATE
@ems_routes.route("/employee/add", methods=["GET"])
@login_required
def ems_employee_add():
    """
    Renders the add employee page.
    """
    return render_template(
        "employee_management/ems_employee_add.html",
        selection="employees",
        employee_statuses=EMPLOYEE_STATUS_OPTIONS,
        employee_grad_years=EMPLOYEE_GRAD_YEARS,
        employee_pronouns=EMPLOYEE_PRONOUNS,
    )


@ems_routes.route("/api/employee/create", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_employee_create():
    """
    API endpoint to create a new employee.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    del data["_csrf_token"]

    date_fields = ["birth_date", "initial_hire_date"]

    for field in date_fields:
        if data.get(field):
            # Converts "YYYY-MM-DD" string to a Python date object
            data[field] = datetime.strptime(data[field], "%Y-%m-%d").date()

    if data.get("payroll_number"):
        data["payroll_number"] = int(data["payroll_number"])

    if data:
        created = create_employee_card(**data)
        if not created:
            return (
                jsonify({"error": "An employee already exists with that IMC email"}),
                400,
            )
        if created == -1:
            return (
                jsonify({"error": "An error occurred while creating the employee."}),
                500,
            )
        return jsonify({"message": "updated", "request": created}), 200

    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create employee with no information."
            }
        ),
        400,
    )


# TEMPLATE
@ems_routes.route("/employee/view/<int:emp_id>", methods=["GET"])
@login_required
def ems_employee_view(emp_id):
    """
    Renders the view employee page.
    """
    employee = get_employee_card_by_id(emp_id)
    return render_template(
        "employee_management/ems_employee_view.html",
        selection="employees",
        employee=employee,
        employee_statuses=EMPLOYEE_STATUS_OPTIONS,
        employee_grad_years=EMPLOYEE_GRAD_YEARS,
        employee_pronouns=EMPLOYEE_PRONOUNS,
    )


@ems_routes.route("/api/employee/modify", methods=["POST"])
@ems_routes.route("/api/employee/get/all", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_employee_get_all():
    """
    API endpoint to get all employees.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    employees = get_all_employee_cards()
    return jsonify({"employees": employees}), 200


################################################################################


# TEMPLATE
@ems_routes.route("/positions", methods=["GET"])
@login_required
def ems_positions():
    """
    Renders the Employee Management System positions page.
    """
    return render_template("employee_management/ems_base.html", selection="positions")
