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
    create_position_card,
    get_all_position_cards,
    delete_position_card,
)

from constants import (
    EMPLOYEE_STATUS_OPTIONS,
    EMPLOYEE_GRAD_YEARS,
    EMPLOYEE_PRONOUNS,
    IMC_BRANDS,
    PAY_TYPES,
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
        employee_statuses=EMPLOYEE_STATUS_OPTIONS,
        employee_grad_years=EMPLOYEE_GRAD_YEARS,
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


# API
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

    if data.get("user_uid"):
        data["user_uid"] = int(data["user_uid"])

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
        return jsonify({"message": "Employee created", "request": created}), 200

    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create employee with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/employee/modify", methods=["POST"])


# API
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

################################################################################
### POSITION FUNCTIONS #########################################################
################################################################################


# TEMPLATE
@ems_routes.route("/positions", methods=["GET"])
@login_required
def ems_positions():
    """
    Renders the Employee Management System positions page.
    """
    return render_template("employee_management/ems_base.html", selection="positions")


# TEMPLATE
@ems_routes.route("/position/add", methods=["GET"])
@login_required
def ems_position_add():
    """
    Renders the add position page.
    """
    all_positions = get_all_position_cards()

    position_options = [
        {"value": pos["uid"], "name": f"{pos['brand']} — {pos['title']}"}
        for pos in all_positions
    ]

    return render_template(
        "employee_management/ems_position_add.html",
        selection="positions",
        imc_brands_choices=IMC_BRANDS,
        pay_types_choices=PAY_TYPES,
        position_options=position_options,
    )


# API
@ems_routes.route("/api/position/create", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_create():
    """
    API endpoint to create a new position.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    del data["_csrf_token"]

    # Convert pay rate to float
    try:
        if data.get("pay_rate"):
            data["pay_rate"] = float(data["pay_rate"])
    except Exception as e:
        return jsonify({"error": "Invalid pay rate format."}), 400

    # Convert supervisors to list of ints
    try:
        if data.get("supervisors"):
            data["supervisors"] = [int(uid) for uid in data["supervisors"]]
    except Exception as e:
        return jsonify({"error": "Invalid supervisors format."}), 400

    if data:
        created = create_position_card(**data)
        if not created:
            return (
                jsonify(
                    {"error": "A position already exists with that brand and title"}
                ),
                400,
            )
        if created == -1:
            return (
                jsonify({"error": "An error occurred while creating the position."}),
                500,
            )
        return jsonify({"message": "Position created", "request": created}), 200

    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create position with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/position/get/all", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_get_all():
    """
    API endpoint to get all positions.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    positions = get_all_position_cards()
    return jsonify(positions), 200


# API
@ems_routes.route("/api/position/<int:uid>/delete", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_delete(uid):
    """
    API endpoint to delete a position.

    Args:
        uid (int): The unique ID of the position to delete.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    deleted = delete_position_card(uid)
    if deleted == None:
        return jsonify({"error": "An error occurred while deleting the position."}), 500
    if not deleted:
        return jsonify({"error": "Position not found."}), 400
    return jsonify({"message": "Position deleted successfully."}), 200


################################################################################
