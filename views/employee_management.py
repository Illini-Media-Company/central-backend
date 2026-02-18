"""
This file defines the API for the Employee Management System.

Created by Jacob Slabosz on Jan. 12, 2026
Last modified Feb. 16, 2026
"""

import logging
from flask import Blueprint, render_template, request, jsonify, abort, session
from flask_login import login_required, current_user
from util.security import restrict_to, is_user_in_group
from datetime import datetime

from flask import request, jsonify, url_for
from util.employee_management import send_onboarding_email

from constants import EMS_ADMIN_ACCESS_GROUPS

from db.user import get_user_profile_photo

from util.employee_management import (
    EUSERDNE,
    EEMPDNE,
    EPOSDNE,
    ERELDNE,
    EMISSING,
    EEXCEPT,
    EEXISTS,
    ESUPREP,
    EGROUP,
    EGROUPDNE,
    ESLACKDNE,
    ESLACK,
    slack_dm_onboarding_started,
    slack_dm_info_received,
    slack_dm_google_created,
    slack_dm_google_failed,
    slack_dm_onboarding_complete,
    get_ems_brand_image_url,
)
from util.slackbots.general import _lookup_user_id_by_email
from util.google_admin import create_google_user

from db.employee_management import (
    get_imc_brand_names,
    get_slack_channel_id,
    create_employee_onboarding_card,
    update_employee_onboarding_card,
    create_employee_card,
    modify_employee_card,
    get_all_employee_cards,
    get_employee_card_by_id,
    get_employee_card_by_email,
    delete_employee_card,
    create_position_card,
    modify_position_card,
    get_all_position_cards,
    get_all_active_position_cards,
    get_position_card_by_id,
    delete_position_card,
    archive_position_card,
    restore_position_card,
    create_relation,
    modify_relation,
    get_all_relations,
    get_relation_by_id,
    get_relations_by_employee,
    get_relations_by_employee_current,
    get_relations_by_employee_past,
    get_relations_by_position,
    get_relations_by_position_current,
    get_relations_by_position_past,
    delete_relation,
    get_groups_for_employee,
    create_employee,
)

from constants import (
    EMPLOYEE_STATUS_OPTIONS,
    EMPLOYEE_GRAD_YEARS,
    EMPLOYEE_PRONOUNS,
    IMC_BRANDS,
    PAY_TYPES,
    DEPART_CATEGORIES,
    DEPART_REASON_VOL,
    DEPART_REASON_INVOL,
    DEPART_REASON_ADMIN,
)

logger = logging.getLogger(__name__)

ems_routes = Blueprint("ems_routes", __name__, url_prefix="/ems")


# TEMPLATE
@ems_routes.route("/", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_dashboard():
    """
    Renders the Employee Management System dashboard.
    """
    return render_template("employee_management/ems_base.html", selection="dash")


# TEMPLATE
@ems_routes.route("/org-chart", methods=["GET"])
@login_required
def ems_org_chart():
    """
    Renders the Org Chart dashboard.
    """
    return render_template(
        "employee_management/employee_org_chart.html", selection="dash"
    )


# TEMPLATE
@ems_routes.route("/settings", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_settings():
    """
    Renders the Employee Management System settings page.
    """
    from db.employee_management import AppSettings

    settings = AppSettings.get_settings()

    return render_template(
        "employee_management/ems_settings.html",
        selection="settings",
        brands=settings.brands,
    )


################################################################################
### EMPLOYEE FUNCTIONS #########################################################
################################################################################


# TEMPLATE — employees
@ems_routes.route("/employees", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_employees():
    """
    Renders the Employee Management System employees page.
    """
    all_employees = get_all_employee_cards()

    # Get the corresponding user's profile photo
    for emp in all_employees:
        if emp["user_uid"]:
            emp["user_profile"] = (
                get_user_profile_photo(emp["user_uid"])
                or "/static/defaults/employee_profile.png"
            )
        else:
            emp["user_profile"] = "/static/defaults/employee_profile.png"

        # Determine what brands the employee currently works for
        cur_pos = get_relations_by_employee_current(emp["uid"])
        emp["cur_brands"] = []
        if cur_pos:
            emp["num_cur_pos"] = len(cur_pos)

            for rel in cur_pos:
                position = get_position_card_by_id(rel["position_id"])
                if position:
                    emp["cur_brands"].append(position["brand"])
        else:
            emp["num_cur_pos"] = 0

        # Alphabetize and remove duplicates
        emp["cur_brands"] = sorted(list(set(emp["cur_brands"])))

    return render_template(
        "employee_management/ems_employees.html",
        selection="employees",
        selected_employees=all_employees,
        employee_statuses=EMPLOYEE_STATUS_OPTIONS,
        employee_grad_years=EMPLOYEE_GRAD_YEARS,
        all_brands=IMC_BRANDS,
    )


# TEMPLATE — employee_add
@ems_routes.route("/employee/add", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
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


# TEMPLATE — employee_add_bulk
@ems_routes.route("/employee/add/bulk", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_employee_add_bulk():
    """
    Renders the file upload page to upload multiple employees.
    """
    return render_template(
        "employee_management/ems_employee_add_bulk.html",
        pronouns=", ".join(EMPLOYEE_PRONOUNS),
        statuses=", ".join(EMPLOYEE_STATUS_OPTIONS),
    )


# TEMPLATE — employee_view
@ems_routes.route("/employee/view/<int:emp_id>", methods=["GET"])
@login_required
def ems_employee_view(emp_id):
    """
    Renders the view employee page.
    """
    logging.info(f"Viewing employee with ID {emp_id}")

    # Get the employee
    employee = get_employee_card_by_id(emp_id)

    if employee == EEMPDNE:
        logging.debug(f"Employee with ID {emp_id} does not exist.")
        abort(
            404,
            description="That employee doesn't seem to exist! \
                Ensure this employee has not been deleted. \
                If the issue persists, contact an administrator.",
        )

    # Validate access
    # if is_user_in_group(current_user, EMS_ADMIN_ACCESS_GROUPS):
    if is_user_in_group(current_user, EMS_ADMIN_ACCESS_GROUPS):
        logging.info(
            f"User {current_user.email} has admin access to employee ID {emp_id}."
        )
        admin_access = True
    else:
        admin_access = False  # Gives less viewing permissions than an admin would have
        if not employee["imc_email"] or employee["imc_email"] != current_user.email:
            logging.info(
                f"User {current_user.email} attempted to access employee ID {emp_id} without permission."
            )
            abort(
                403,
                description="You do not have permission to view this employee.",
            )
        else:
            logging.info(
                f"User {current_user.email} is viewing their own employee record (ID {emp_id})."
            )

    logging.debug(f"Employee data for ID {emp_id}: {employee}")

    employee["current_positions"] = []
    employee["past_positions"] = []

    # Get the employee's current positions
    cur_relations = get_relations_by_employee_current(emp_id)
    for rel in cur_relations:
        position = get_position_card_by_id(rel["position_id"])
        if position:
            employee["current_positions"].append(
                {
                    "relation_uid": rel["uid"],
                    "position_uid": position["uid"],
                    "brand": position["brand"],
                    "title": position["title"],
                    "start_date": rel["start_date"],
                }
            )
    logging.debug(
        f"Current positions for employee ID {emp_id}: {employee['current_positions']}"
    )

    # Get the employee's past positions
    past_relations = get_relations_by_employee_past(emp_id)
    for rel in past_relations:
        position = get_position_card_by_id(rel["position_id"])
        if position:
            employee["past_positions"].append(
                {
                    "relation_uid": rel["uid"],
                    "position_uid": position["uid"],
                    "brand": position["brand"],
                    "title": position["title"],
                    "start_date": rel["start_date"],
                    "end_date": rel["end_date"],
                    "departure_category": rel["departure_category"],
                    "departure_reason": rel["departure_reason"],
                    "departure_notes": rel["departure_notes"],
                }
            )
    logging.debug(
        f"Past positions for employee ID {emp_id}: {employee['past_positions']}"
    )

    # Get all possible position options for dropdown (not needed if not an admin)
    if admin_access:
        all_positions = get_all_active_position_cards()
        position_options = [
            {"value": pos["uid"], "name": f"{pos['brand']} — {pos['title']}"}
            for pos in all_positions
        ]
    else:
        position_options = []

    # Get the corresponding user's profile photo
    if employee["user_uid"]:
        employee["user_profile"] = (
            get_user_profile_photo(employee["user_uid"])
            or "/static/defaults/employee_profile.png"
        )
    else:
        employee["user_profile"] = "/static/defaults/employee_profile.png"

    return render_template(
        "employee_management/ems_employee_view.html",
        selection="employees",
        employee=employee,
        employee_statuses=EMPLOYEE_STATUS_OPTIONS,
        employee_grad_years=EMPLOYEE_GRAD_YEARS,
        employee_pronouns=EMPLOYEE_PRONOUNS,
        position_options=position_options,
        departure_categories=DEPART_CATEGORIES,
        depart_reasons_vol=DEPART_REASON_VOL,
        depart_reasons_invol=DEPART_REASON_INVOL,
        depart_reasons_admin=DEPART_REASON_ADMIN,
        admin_access=admin_access,
    )


@ems_routes.route("employee/view/me", methods=["GET"])
@login_required
def ems_employee_view_me():
    """
    Renders the current user's employee view page.
    """
    user_email = current_user.email

    employee = get_employee_card_by_email(user_email)
    if not employee or employee == EEMPDNE:
        logging.info(
            f"Employee card for user email {user_email} does not exist or has been deleted."
        )
        abort(
            404,
            description=f"Your email ({user_email}) is not currently linked to an employee record. If you believe this is a mistake, please contact an administrator.",
        )

    return ems_employee_view(employee["uid"])


# TEMPLATE — employee_onboard
@ems_routes.route("/employee/onboard", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_employee_onboard():
    """
    Renders the employee onboarding (send invite) page.
    """
    return render_template(
        "employee_management/ems_employee_onboard.html",
        selection="employees",
        brand_options=get_imc_brand_names(),
    )


# TEMPLATE — employee_onboarding_form
@ems_routes.route("/onboarding/<int:emp_id>", methods=["GET"])
def ems_employee_onboarding_form(emp_id):
    logging.info(f"Accessing onboarding form for employee ID {emp_id}")

    # Ensure this employee card was not deleted
    employee = get_employee_card_by_id(emp_id)
    if not employee or employee == EEMPDNE:
        logging.info(f"Employee with ID {emp_id} does not exist or has been deleted.")
        abort(404)

    # Check if onboarding form already completed to prevent reuse of the link after onboarding is done
    if employee.get("onboarding_form_done"):
        # If onboarding complete, they cannot use this link
        if employee.get("onboarding_complete"):
            logging.info(
                f"Onboarding form for employee ID {emp_id} has already been completed."
            )
            abort(
                400,
                description="This onboarding link has already been used! \
                    To make changes, please reach out to your supervisor \
                    or email helpdesk@illinimedia.com.",
            )
        # Otherwise if the form is done but onboarding not complete, give them the next steps page
        else:
            logging.info(
                f"Onboarding form for employee ID {emp_id} has already been completed, but onboarding is not marked as complete. Redirecting to next steps page."
            )
            return ems_employee_onboard_nextsteps_success(emp_id)

    return render_template(
        "employee_management/ems_onboarding_form.html",
        employee=employee,
        employee_first_name=employee.get("first_name"),
        employee_last_name=employee.get("last_name"),
        grad_year_options=EMPLOYEE_GRAD_YEARS,
        pronoun_options=EMPLOYEE_PRONOUNS,
    )


# TEMPLATE — onboarding_nextsteps_success
@ems_routes.route("/onboarding/nextsteps/login/<int:uid>")
def ems_employee_onboard_nextsteps_success(uid):
    session_uid = session.get("onboarding_uid")
    email = None
    password = None

    # Ensure the employee was not deleted
    employee = get_employee_card_by_id(uid)
    if not employee or employee == EEMPDNE:
        logging.info(f"Employee with ID {uid} does not exist or has been deleted.")
        abort(404, description="Unable to locate an employee with that ID.")

    # Check if onboarding done
    if employee["onboarding_complete"]:
        logging.info(f"Employee with ID {uid} has already completed onboarding.")
        abort(
            400,
            description="This onboarding link has already been used! \
                To make changes, please reach out to your supervisor \
                or email helpdesk@illinimedia.com.",
        )

    # Prefer to get info from the session cookies
    if session_uid and session_uid == uid:
        email = session.get("onboarding_email")
        password = session.get("onboarding_password")

    # Get from the DB object if not available in the session
    if not email or not password:
        logging.info(
            f"Onboarding info for employee ID {uid} not found in session. Fetching from database."
        )
        email = employee.get("imc_email")

        # Eventual consistency issue, should resolve after a short moment
        if not email:
            logging.warning(
                f"Employee with ID {uid} does not have an email associated."
            )
            abort(
                400,
                description="Google account not yet provisioned. Please wait a moment, then refresh this page. If the issue persists, email helpdesk@illinimedia.com.",
            )

        # Check if this was a manually resent link or if they reused the onboarding form link
        if request.args.get("override") == "true":
            # Since this block only runs if the link was sent manually
            password = "(Password provided via email)"
            logging.info(
                f"Onboarding link for employee ID {uid} was manually resent. Displaying generic password message instead of actual password."
            )
        else:
            # Rebuild using same login as util/google_admin.py
            password = f"temporary-{employee.get('uid')}"

    return render_template(
        "/employee_management/ems_onboarding_nextstep_success.html",
        email=email,
        password=password,
        uid=uid,
    )


# TEMPLATE — onboarding_nextsteps_failure
@ems_routes.route("/onboarding/nextsteps/wait")
def ems_employee_onboard_nextsteps_failure():
    return render_template("/employee_management/ems_onboarding_nextstep_failure.html")


# TEMPLATE & API
@ems_routes.route("/onboarding/<int:emp_id>/complete", methods=["GET"])
@login_required
def ems_onboarding_complete(emp_id):
    logging.info(
        f"Completing onboarding for employee ID {emp_id} by user {current_user.email}"
    )

    # Get the employee
    employee = get_employee_card_by_id(emp_id)
    if employee:
        # Check if the logged in user is this employee
        if current_user.email != employee["imc_email"]:
            logging.info(
                f"User {current_user.email} attempted to complete onboarding for employee ID {emp_id} with email {employee['imc_email']}."
            )
            abort(
                409,
                description="The logged in user does not match the employee.",
            )

        # Check if this employee is already marked as complete
        if employee["onboarding_complete"]:
            logging.info(
                f"Employee ID {emp_id} attempted to complete onboarding, but it is already marked as complete."
            )
            return render_template("/employee_management/ems_onboarding_complete.html")

        # Ensure they've logged into Slack & get their ID
        slack_id = _lookup_user_id_by_email(employee["imc_email"])
        if not slack_id:
            logging.info(
                f"Employee ID {emp_id} with email {employee['imc_email']} has not logged into Slack or could not be found in Slack."
            )
            return render_template(
                "error.html",
                code="409",
                error="It seems you did not log into Slack. Please do so, then refresh this page.",
            )

        logging.debug(
            f"Employee ID {emp_id} has Slack ID {slack_id}. Proceeding with onboarding completion."
        )

        # Save the employee's Slack ID
        modify_employee_card(
            uid=employee["uid"],
            slack_id=slack_id,
            onboarding_complete=True,
            status="Active",
        )
        logging.debug(
            f"Employee ID {emp_id} marked as onboarding complete with Slack ID {slack_id}."
        )

        slack_channel = employee["onboarding_update_channel"]
        slack_ts = employee["onboarding_update_ts"]
        full_name = employee["full_name"]
        ems_url = url_for("ems_routes.ems_employee_view", emp_id=emp_id, _external=True)

        res = slack_dm_onboarding_complete(
            channel_id=slack_channel,
            thread_ts=slack_ts,
            employee_name=full_name,
            slack_id=slack_id,
            ems_url=ems_url,
        )
        if not isinstance(res, dict):
            logging.error(
                f"Failed to send completion Slack message for employee ID {emp_id} due to an unknown error."
            )
        if not res.get("ok"):
            logging.error(
                f"Failed to send completion Slack message for employee ID {emp_id}. Error: {res['error']}"
            )
        return render_template("/employee_management/ems_onboarding_complete.html")
    # If employee not found
    else:
        logging.info(f"Employee with ID {emp_id} does not exist or has been deleted.")
        abort(
            404,
            description="That onboarding link is not valid. Please contact helpdesk@illinimedia.com if you believe this is a mistake.",
        )


################################################################################


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
    data.pop("_csrf_token", None)

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

        # Fatal error
        if not created:
            return (
                jsonify({"error": "A fatal error occurred."}),
                500,
            )

        # Unknown exception
        if created == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while creating the employee."}),
                500,
            )

        # User does not exist
        if created == EUSERDNE:
            return (
                jsonify({"error": "The chosen user does not exist."}),
                400,
            )

        # Employee already exists
        if created == EEXISTS:
            return (
                jsonify(
                    {"error": "An employee already exists with the given IMC email."}
                ),
                400,
            )

        # Missing required fields
        if created == EMISSING:
            return (
                jsonify(
                    {
                        "error": "Missing required fields. Ensure all required fields are included and try again."
                    }
                ),
                400,
            )

        # No errors
        return jsonify({"message": "Employee created", "request": created}), 200

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create employee with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/employee/create/bulk", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_employee_create_all():
    import pandas as pd

    logging.info("Bulk creating employees via CSV upload.")

    if "file_input" not in request.files:
        logging.info("No file part in the request.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file_input"]

    if file.filename == "":
        logging.info("No file selected for upload.")
        return jsonify({"error": "No selected file"}), 400

    # 2. You can read the file directly into Pandas without saving it to disk
    try:
        # Move pointer to start of file just in case
        file.seek(0)
        uploaded_df = pd.read_csv(file, encoding="unicode_escape")

        validate_csv(uploaded_df)

        logging.info(f"Processing {len(uploaded_df)} rows from uploaded CSV.")
        return jsonify({"message": f"Processed {len(uploaded_df)} rows"}), 200
    except Exception as e:
        logging.error(f"Error processing CSV: {str(e)}")
        return jsonify({"error": str(e)}), 500


# API
@ems_routes.route("/api/employee/<int:uid>/modify", methods=["POST"])
@login_required
def ems_api_employee_modify(uid):
    """
    API endpoint to modify an existing employee.

    Args:
        uid (int): The unique ID of the employee to modify.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    data.pop("_csrf_token", None)

    date_fields = ["birth_date", "initial_hire_date"]

    try:
        for field in date_fields:
            if data.get(field):
                # Converts "YYYY-MM-DD" string to a Python date object
                data[field] = datetime.strptime(data[field], "%Y-%m-%d").date()
    except Exception as e:
        return (
            jsonify({"error": "Invalid birth date or initial hire date format."}),
            400,
        )

    try:
        if data.get("payroll_number"):
            data["payroll_number"] = int(data["payroll_number"])
    except Exception as e:
        return jsonify({"error": "Invalid payroll number format."}), 400

    try:
        if data.get("user_uid"):
            data["user_uid"] = int(data["user_uid"])
    except Exception as e:
        return jsonify({"error": "Invalid user ID format."}), 400

    if data:
        # Validate access
        if is_user_in_group(current_user, EMS_ADMIN_ACCESS_GROUPS):
            logging.info(
                f"User {current_user.email} has admin access to modify employee ID {uid}."
            )
        else:
            employee = get_employee_card_by_id(uid)
            if not employee["imc_email"] or employee["imc_email"] != current_user.email:
                logging.info(
                    f"User {current_user.email} attempted to modify employee ID {uid} without permission."
                )
                return (
                    jsonify(
                        {"error": "You do not have permission to modify this employee."}
                    ),
                    403,
                )
            else:
                logging.info(
                    f"User {current_user.email} is modifying their own employee record (ID {uid})."
                )

                # Remove field that non-admins are not allowed to modify
                data.pop("status", None)
                data.pop("imc_email", None)
                data.pop("initial_hire_date", None)
                data.pop("payroll_number", None)

        modified = modify_employee_card(uid, **data)

        # Fatal error
        if not modified:
            return (
                jsonify({"error": "A fatal error occurred."}),
                500,
            )

        # Unknown exception
        if modified == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while modifying the employee."}),
                500,
            )

        # Employee does not exist
        if modified == EEMPDNE:
            return jsonify({"error": "Employee not found."}), 400

        # User does not exist
        if modified == EUSERDNE:
            return (
                jsonify({"error": "The chosen user does not exist."}),
                400,
            )

        # Employee already exists
        if modified == EEXISTS:
            return (
                jsonify(
                    {"error": "An employee already exists with the given IMC email."}
                ),
                400,
            )

        # No errors
        return (
            jsonify(
                {"message": "Employee modified successfully.", "request": modified}
            ),
            200,
        )

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot modify employee with no information."
            }
        ),
        400,
    )


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


# API
@ems_routes.route("/api/employee/<int:uid>/delete", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_employee_delete(uid):
    """
    API endpoint to delete an employee.

    Args:
        uid (int): The unique ID of the employee to delete.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    deleted = delete_employee_card(uid)

    # Fatal error
    if not deleted:
        return (
            jsonify({"error": "A fatal error occurred while deleting the employee."}),
            500,
        )

    # Employee not found
    if deleted == EEMPDNE:
        return jsonify({"error": "Employee not found."}), 400

    # Unknown exception
    if deleted == EEXCEPT:
        return jsonify({"error": "An error occurred while deleting the employee."}), 500

    # No errors
    return jsonify({"message": "Employee deleted successfully."}), 200


# API
@ems_routes.route("/api/employee/onboard/send", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_employee_onboard_send():
    """
    Admin-only endpoint: validates invitee input, creates a provisional
    onboarding employee record, and builds a public onboarding link.
    Sends the onboarding email and returns an error on failure;
    otherwise redirects back to the EMS employees page.
    """
    data = (
        request.form.to_dict()
        if request.form
        else (request.get_json(silent=True) or {})
    )

    logging.info(
        f"{current_user.email if current_user else 'unknown user'} sending an onboarding invite to {data.get('email', 'unknown email')}."
    )

    # Get data
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    onboarded_brand = (data.get("onboarded_brand") or "").strip()
    onboarded_by = current_user.email if current_user else "onboarding@illinimedia.com"

    # Validate required fields
    if not first_name or not last_name or not email or not onboarded_brand:
        logging.debug(f"Onboarding invite failed validation. Received data: {data}")
        return (
            jsonify({"error": "First name, last name, email and brand are required."}),
            400,
        )
    if "@" not in email:
        logging.debug(
            f"Onboarding invite failed validation due to invalid email format: {email}"
        )
        return jsonify({"error": "Invalid email format."}), 400

    # Bool, whether to notify the user (True) or the brand's channel (False)
    indv_notif = bool(data.get("indv_notif"))

    # Send Slack messages notifying that step 1 of onboarding is done
    if indv_notif:
        logging.debug(
            f"Individual notification selected for onboarding {first_name} {last_name}. Attempting to look up Slack ID for {onboarded_by} to send DM updates."
        )
        # Channel should be the user who onboarded
        user_id = _lookup_user_id_by_email(onboarded_by)
        if not user_id:
            logging.error(
                f"Failed to look up Slack ID for {onboarded_by}. Cannot send individual onboarding notifications."
            )
            return (
                jsonify({"error": "The logged in user could not be found in Slack."}),
                500,
            )
        onboarding_update_channel = user_id
    else:
        logging.debug(
            f"Brand channel notification selected for onboarding {first_name} {last_name}. Attempting to look up Slack channel ID for brand {onboarded_brand} to send updates."
        )
        # Channel should be the brand's EMS channel
        channel_id = get_slack_channel_id(onboarded_brand)
        if not channel_id:
            logging.error(
                f"Failed to look up Slack channel ID for brand {onboarded_brand}. Cannot send onboarding notifications to brand channel."
            )
            return (
                jsonify(
                    {"error": "The brand's channel_id is not defined in settings."}
                ),
                500,
            )
        onboarding_update_channel = channel_id

    # Create the EmployeeCard
    logging.debug(
        f"Creating onboarding employee record for {first_name} {last_name} with email {email} and brand {onboarded_brand}."
    )
    created = create_employee_onboarding_card(
        first_name=first_name,
        last_name=last_name,
        onboarding_update_channel=onboarding_update_channel,
    )
    if created in (None, EEXCEPT):
        logging.error(
            f"Failed to create onboarding employee record for {first_name} {last_name}. Error: {created if created else 'unknown error'}"
        )
        return jsonify({"error": "Failed to create employee."}), 500

    # Get the URL for the employee's onboarding link
    emp_id = created["uid"]
    onboarding_url = url_for(
        "ems_routes.ems_employee_onboarding_form",
        emp_id=emp_id,
        _external=True,
    )
    logging.debug(f"Onboarding URL for employee ID {emp_id}: {onboarding_url}")

    # Email the employee
    rc = send_onboarding_email(
        to_email=email,
        first_name=first_name,
        onboarding_url=onboarding_url,
    )
    if not isinstance(rc, dict) or not rc.get("ok"):
        logging.error(
            f"Failed to send onboarding email to {email} for employee ID {emp_id}. Error: {rc if isinstance(rc, dict) else 'unknown error'}"
        )
        return (
            jsonify(
                {
                    "error": "Failed to send onboarding email.",
                    "details": rc.get("error") if isinstance(rc, dict) else str(rc),
                }
            ),
            500,
        )
    logging.debug(
        f"Onboarding email sent successfully to {email} for employee ID {emp_id}."
    )

    # Send Slack messages notifying that step 1 of onboarding is done
    res = slack_dm_onboarding_started(
        channel_id=onboarding_update_channel, employee_name=created["full_name"]
    )
    if not isinstance(res, dict):
        logging.error(
            f"Failed to send onboarding started Slack message for employee ID {emp_id} due to an unknown error."
        )
        return jsonify({"error": "Slack message failed for an unknown reason."}), 500
    if not res.get("ok"):
        logging.error(
            f"Failed to send onboarding started Slack message for employee ID {emp_id}. Error: {res['error']}"
        )
        return jsonify({"error": f"Slack message failed: {res['error']}"}), 500

    # Store the Slack TS
    res = update_employee_onboarding_card(uid=created["uid"], ts=res["ts"])
    if res == EEMPDNE:
        logging.error(
            f"Failed to update onboarding employee record for employee ID {emp_id} with Slack TS {res['ts']} because the employee was not found."
        )
        return jsonify({"error": "Creating the employee failed."}), 400
    if res == EEXCEPT:
        logging.error(
            f"An exception occurred while updating onboarding employee record for employee ID {emp_id} with Slack TS {res['ts']}."
        )
        return jsonify({"error": "A fatal error occurred."}), 400

    logging.debug(
        f"Onboarding process successfully initiated for employee ID {emp_id}."
    )
    return jsonify({"ok": True, "message": "Onboarding successfully started."}), 200


# API
@ems_routes.route("/api/onboarding/<int:emp_id>/submit", methods=["POST"])
def ems_api_onboarding_submit(emp_id):
    """
    Public onboarding submit endpoint: validates required fields,
    parses optional birth_date, marks link as used, and saves employee data.
    """
    logging.info(f"Submitting onboarding form for employee ID {emp_id}.")

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    data.pop("_csrf_token", None)

    # Get the NetID to create an IMC email address
    netid = data.pop("netid", None)
    if not netid:
        logging.debug(
            f"Onboarding form submission for employee ID {emp_id} failed validation due to missing NetID."
        )
        return jsonify({"ok": False, "error": "NetID is required."}), 400

    # convert to lowercase to ensure consistency
    netid = netid.lower()

    # Validate the NetID (make sure not UIN or email)
    is_alphanumeric = netid.isalnum()
    if not is_alphanumeric:
        logging.debug(
            f"Onboarding form submission for employee ID {emp_id} failed validation due to invalid NetID format: {netid}"
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "NetID must be alphanumeric. Ensure you have only entered your NetID, not your full email.",
                }
            ),
            400,
        )

    is_not_all_numbers = not netid.isdigit()
    if not is_not_all_numbers:
        logging.debug(
            f"Onboarding form submission for employee ID {emp_id} failed validation due to invalid NetID format: {netid}"
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "NetID must be alphanumeric. Ensure you entered your NetID, not your UIN.",
                }
            ),
            400,
        )

    # Ensure employee exists (has not since been deleted)
    employee = get_employee_card_by_id(emp_id)
    if not employee:
        logging.debug(
            f"Onboarding form submission failed because employee with ID {emp_id} does not exist."
        )
        abort(
            404,
            description="That onboarding link has since been deleted. Please contact helpdesk@illinimedia.com",
        )

    # Ensure not already filled out
    if employee.get("onboarding_form_done"):
        logging.debug(
            f"Onboarding form submission for employee ID {emp_id} failed because the onboarding form has already been completed."
        )
        return (
            jsonify(
                {"ok": False, "error": "This onboarding link has already been used."}
            ),
            400,
        )

    # Check for missing fields
    required = [
        "last_name",
        "first_name",
        "personal_email",
        "pronouns",
        "phone_number",
        "permanent_address_1",
        "permanent_city",
        "permanent_zip",
        "major",
        "graduation",
        "birth_date",
    ]
    missing = [k for k in required if not (data.get(k) or "").strip()]
    if missing:
        logging.debug(
            f"Onboarding form submission for employee ID {emp_id} failed validation due to missing required fields: {missing}"
        )
        return (
            jsonify(
                {"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}
            ),
            400,
        )

    # Format date of birth
    if data.get("birth_date"):
        try:
            data["birth_date"] = datetime.strptime(
                data["birth_date"], "%Y-%m-%d"
            ).date()
        except ValueError:
            logging.debug(
                f"Onboarding form submission for employee ID {emp_id} failed validation due to invalid birth date format: {data['birth_date']}"
            )
            return (
                jsonify(
                    {"ok": False, "error": "Invalid birth date format. Use YYYY-MM-DD."}
                ),
                400,
            )

    # Modify the employee
    updated = modify_employee_card(uid=emp_id, onboarding_form_done=True, **data)
    if updated in (EEMPDNE, EUSERDNE, EEXISTS, EEXCEPT):
        logging.error(
            f"Failed to update employee record for employee ID {emp_id} upon onboarding form submission. Error: {updated if updated else 'unknown error'}"
        )
        return jsonify({"ok": False, "error": "Failed to submit onboarding form."}), 500

    # Notify via Slack of completion
    first_name = updated["first_name"]
    last_name = updated["last_name"]
    slack_channel = updated["onboarding_update_channel"]
    slack_ts = updated["onboarding_update_ts"]

    res = slack_dm_info_received(channel_id=slack_channel, thread_ts=slack_ts)
    if not isinstance(res, dict):
        logging.error(
            f"Failed to send onboarding info received Slack message for employee ID {emp_id} due to an unknown error."
        )
        return jsonify({"error": "Slack message failed for an unknown reason."}), 500
    if not res.get("ok"):
        logging.error(
            f"Failed to send onboarding info received Slack message for employee ID {emp_id}. Error: {res['error']}"
        )
        return jsonify({"error": f"Slack message failed: {res['error']}"}), 500
    logging.debug(
        f"Onboarding info received Slack message sent successfully for employee ID {emp_id}."
    )

    # Create the Google account
    personal_email = updated["personal_email"]
    uid = updated["uid"]
    success, data = create_google_user(
        netid=netid,
        first_name=first_name,
        last_name=last_name,
        personal_email=personal_email,
        password=uid,
    )

    if success == True:
        logging.debug(
            f"Google account created successfully for employee ID {emp_id} with NetID {netid}."
        )

        # Save the new email to the EmployeeCard
        updated = modify_employee_card(uid=emp_id, imc_email=f"{netid}@illinimedia.com")

        # If the Google account created successfully, notify via Slack, display page
        res = slack_dm_google_created(channel_id=slack_channel, thread_ts=slack_ts)

        # Save info in session storage to display on next page
        session["onboarding_email"] = f"{netid}@illinimedia.com"
        session[
            "onboarding_password"
        ] = data  # Returned password from Google account creation
        session["onboarding_uid"] = emp_id

        redirect_url = url_for(
            "ems_routes.ems_employee_onboard_nextsteps_success",
            uid=emp_id,
            _external=True,
        )
    else:
        # Else, notify and display other page
        logging.error(
            f"Failed to create Google account for employee ID {emp_id} with NetID {netid}. Error: {str(data)}"
        )
        res = slack_dm_google_failed(
            channel_id=slack_channel, thread_ts=slack_ts, error=str(data)
        )
        redirect_url = url_for(
            "ems_routes.ems_employee_onboard_nextsteps_failure", _external=True
        )

    logging.debug(
        f"Onboarding process completed for employee ID {emp_id}. Redirecting to next steps page."
    )
    return (
        jsonify(
            {
                "ok": True,
                "message": "Onboarding submitted successfully.",
                "redirect_url": redirect_url,
            }
        ),
        200,
    )


# API
@ems_routes.route("/api/onboarding/<int:emp_id>/override", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_onboarding_override(emp_id):
    """
    Manually override onboarding completion for an employee. This is intended for use in exceptional
    cases where the employee cannot complete the onboarding process through normal means (e.g.,
    issues with Google account creation, Slack access, etc.) but still needs to be marked as onboarded
    in the system. This endpoint will mark the employee's onboarding as complete and send a Slack
    message to notify relevant parties. It does not perform any of the usual checks or processes
    involved in standard onboarding completion, so it should be used with caution.
    """
    logging.info(
        f"Manually overriding onboarding for employee ID {emp_id} by user {current_user.email}"
    )

    try:
        # Get the employee
        employee = get_employee_card_by_id(emp_id)
        if employee:
            # Check if this employee is already marked as complete
            if employee["onboarding_complete"]:
                logging.info(f"Onboarding already complete for employee {emp_id}.")
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "Onboarding is already marked as complete for this employee.",
                        }
                    ),
                    400,
                )

            # Save the employee's Slack ID
            modify_employee_card(
                uid=employee["uid"],
                onboarding_form_done=True,
                onboarding_complete=True,
                status="Active",
            )
            logging.debug(f"Employee ID {emp_id} marked as onboarding complete.")

            slack_channel = employee["onboarding_update_channel"]
            slack_ts = employee["onboarding_update_ts"]
            full_name = employee["full_name"]
            ems_url = url_for(
                "ems_routes.ems_employee_view", emp_id=emp_id, _external=True
            )

            res = slack_dm_onboarding_complete(
                channel_id=slack_channel,
                thread_ts=slack_ts,
                employee_name=full_name,
                slack_id=None,
                ems_url=ems_url,
            )
            if not isinstance(res, dict):
                logging.error(
                    f"Failed to send completion Slack message for employee ID {emp_id} due to an unknown error."
                )
            if not res.get("ok"):
                logging.error(
                    f"Failed to send completion Slack message for employee ID {emp_id}. Error: {res['error']}"
                )
            return (
                jsonify(
                    {
                        "ok": True,
                        "message": "Onboarding successfully overridden.",
                    }
                ),
                200,
            )
        # If employee not found
        else:
            logging.info(
                f"Employee with ID {emp_id} does not exist or has been deleted."
            )
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "Employee not found.",
                    }
                ),
                404,
            )
    except Exception as e:
        logging.error(
            f"An exception occurred while overriding onboarding for employee ID {emp_id}. Error: {str(e)}"
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "An error occurred while overriding onboarding.",
                }
            ),
            500,
        )


################################################################################

################################################################################
### POSITION FUNCTIONS #########################################################
################################################################################


# TEMPLATE
@ems_routes.route("/positions", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_positions():
    """
    Renders the Employee Management System positions page.
    """
    all_positions = get_all_position_cards()
    for pos in all_positions:
        pos["brand_image_url"] = get_ems_brand_image_url(pos["brand"])

    return render_template(
        "employee_management/ems_positions.html",
        selection="positions",
        selected_positions=all_positions,
        imc_brands_choices=IMC_BRANDS,
        pay_types_choices=PAY_TYPES,
    )


# TEMPLATE
@ems_routes.route("/position/add", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
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


# TEMPLATE
@ems_routes.route("/position/view/<int:pos_id>", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_position_view(pos_id):
    """
    Renders the view position page.
    """
    logging.info(f"Viewing position with ID {pos_id}")
    # Get the position
    position = get_position_card_by_id(pos_id)

    if position == EPOSDNE:
        logging.debug(f"Position with ID {pos_id} does not exist.")
        abort(
            404,
            description="That position doesn't seem to exist! \
                Ensure this position has not been deleted. \
                If the issue persists, contact an administrator.",
        )

    logging.debug(f"Position data for ID {pos_id}: {position}")

    position["current_employees"] = []
    position["past_employees"] = []

    # Get the position's current employees
    cur_relations = get_relations_by_position_current(pos_id)
    for rel in cur_relations:
        employee = get_employee_card_by_id(rel["employee_id"])
        if employee:
            position["current_employees"].append(
                {
                    "relation_uid": rel["uid"],
                    "employee_uid": employee["uid"],
                    "first_name": employee["first_name"],
                    "last_name": employee["last_name"],
                    "start_date": rel["start_date"],
                }
            )
    logging.debug(
        f"Current employees for position ID {pos_id}: {position['current_employees']}"
    )

    # # Get the position's past employees
    # past_relations = get_relations_by_position_past(pos_id)
    # for rel in past_relations:
    #     employee = get_employee_card_by_id(rel["employee_id"])
    #     if employee:
    #         position["past_employees"].append(
    #             {
    #                 "relation_uid": rel["uid"],
    #                 "employee_uid": employee["uid"],
    #                 "first_name": employee["first_name"],
    #                 "last_name": employee["last_name"],
    #                 "start_date": rel["start_date"],
    #                 "end_date": rel["end_date"],
    #                 "departure_category": rel["departure_category"],
    #                 "departure_reason": rel["departure_reason"],
    #                 "departure_notes": rel["departure_notes"],
    #             }
    #         )

    # Get all possible employee options for dropdown
    all_employees = get_all_employee_cards()
    employee_options = [
        {"value": emp["uid"], "name": f"{emp['last_name']}, {emp['first_name']}"}
        for emp in all_employees
    ]

    # All positions (used for adding supervisors)
    all_positions = get_all_position_cards()

    # Format the position options for the dropdown
    position_options = [
        {"value": pos["uid"], "name": f"{pos['brand']} — {pos['title']}"}
        for pos in all_positions
        if pos["uid"] != position["uid"]
    ]

    # Get this position's supervisors
    new_supervisors = []
    for pos in position["supervisors"]:
        supervisor = get_position_card_by_id(pos)
        if supervisor:
            new_supervisors.append(
                {
                    "uid": supervisor["uid"],
                    "title": supervisor["title"],
                    "brand": supervisor["brand"],
                }
            )
    position["supervisors"] = new_supervisors

    # Get this position's direct reports
    new_direct_reports = []
    for pos in position["direct_reports"]:
        direct_report = get_position_card_by_id(pos)
        if direct_report:
            new_direct_reports.append(
                {
                    "uid": direct_report["uid"],
                    "title": direct_report["title"],
                    "brand": direct_report["brand"],
                }
            )
    position["direct_reports"] = new_direct_reports

    return render_template(
        "employee_management/ems_position_view.html",
        selection="positions",
        position=position,
        imc_brands_choices=IMC_BRANDS,
        pay_types_choices=PAY_TYPES,
        position_options=position_options,
        employee_options=employee_options,
        departure_categories=DEPART_CATEGORIES,
        depart_reasons_vol=DEPART_REASON_VOL,
        depart_reasons_invol=DEPART_REASON_INVOL,
        depart_reasons_admin=DEPART_REASON_ADMIN,
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
    data.pop("_csrf_token", None)

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

        # Fatal error
        if not created:
            return (
                jsonify(
                    {"error": "A fatal error occurred while creating the position."}
                ),
                400,
            )

        # Unknown exception
        if created == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while creating the position."}),
                500,
            )

        # Google Group does not exist
        if created == EGROUPDNE:
            return (
                jsonify(
                    {
                        "error": "That Google Group does not exist. Check the spelling and make sure it exists in the Admin console."
                    }
                ),
                400,
            )

        # Slack channel error
        if created == ESLACKDNE:
            return (
                jsonify(
                    {
                        "error": "One or more of the Slack channels provided does not exist, or Scout does not have access to it."
                    }
                ),
                400,
            )

        # Position already exists
        if created == EEXISTS:
            return (
                jsonify(
                    {"error": "A position with that brand and title already exists."}
                ),
                400,
            )

        # No errors
        return jsonify({"message": "Position created", "request": created}), 200

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create position with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/position/<int:uid>/modify", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_modify(uid):
    """
    API endpoint to modify an existing employee.

    Args:
        uid (int): The unique ID of the employee to modify.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    data.pop("_csrf_token", None)

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
        modified = modify_position_card(uid, **data)

        # Fatal error
        if not modified:
            return (
                jsonify(
                    {"error": "A fatal error occurred while modifying the position."}
                ),
                500,
            )

        # Unknown exception
        if modified == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while modifying the position."}),
                500,
            )

        # Position not found
        if modified == EPOSDNE:
            return (
                jsonify({"error": "Position not found."}),
                400,
            )

        # Position already exists
        if modified == EEXISTS:
            return (
                jsonify(
                    {"error": "A position with that brand and title already exists."}
                ),
                400,
            )

        # Position already exists
        if modified == EGROUPDNE:
            return (
                jsonify(
                    {
                        "error": "That Google Group does not exist. Check the spelling and make sure it exists in the Admin console."
                    }
                ),
                400,
            )

        # Slack channel error
        if modified == ESLACKDNE:
            return (
                jsonify(
                    {
                        "error": "One or more of the Slack channels provided does not exist, or Scout does not have access to it."
                    }
                ),
                400,
            )

        # Error setting supervisors or direct reports
        if modified == ESUPREP:
            return (
                jsonify({"error": "Error updating supervisors or direct reports."}),
                400,
            )

        # Groups error
        if modified == EGROUP:
            return (
                jsonify(
                    {
                        "error": "The position was updated, but there was an error updating \
                            the Google Groups for at least one employee. Check that the group \
                            email is correct and manually remove the employee from the group."
                    }
                ),
                500,
            )

        # SLACK error
        if modified == ESLACK:
            return (
                jsonify(
                    {
                        "error": "The position was updated, but there was an error updating \
                            the Slack channels for at least one employee. Check that the channel \
                            IDs are correct and manually remove the employee from the channels."
                    }
                ),
                500,
            )

        # No errors
        return jsonify({"message": "Position modified.", "request": modified}), 200

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot modify position with no information."
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

    # Fatal error
    if not deleted:
        return (
            jsonify({"error": "A fatal error occurred while deleting the position."}),
            500,
        )

    # Position not found
    if deleted == EPOSDNE:
        return jsonify({"error": "Position not found."}), 400

    # Unknown exception
    if deleted == EEXCEPT:
        return jsonify({"error": "An error occurred while deleting the position."}), 500

    # No errors
    return jsonify({"message": "Position deleted successfully."}), 200


# API
@ems_routes.route("/api/position/<int:uid>/archive", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_archive(uid):
    """
    API endpoint to archive a position.

    Args:
        uid (int): The unique ID of the position to archive.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    archived = archive_position_card(uid)

    # Fatal error
    if not archived:
        return (
            jsonify({"error": "A fatal error occurred while archiving the position."}),
            500,
        )

    # Position not found
    if archived == EPOSDNE:
        return (
            jsonify({"error": "Position not found."}),
            400,
        )

    # Position has active relations
    if archived == EEXISTS:
        return (
            jsonify(
                {"error": "Position has active employee relations, cannot archive."}
            ),
            400,
        )

    # Unknown exception
    if archived == EEXCEPT:
        return (
            jsonify({"error": "An error occurred while archiving the position."}),
            500,
        )

    # No errors
    return jsonify({"message": "Position archived successfully."}), 200


# API
@ems_routes.route("/api/position/<int:uid>/restore", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_position_restore(uid):
    """
    API endpoint to restore an archived position.

    Args:
        uid (int): The unique ID of the position to restore.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    restored = restore_position_card(uid)

    # Fatal error
    if not restored:
        return (
            jsonify({"error": "A fatal error occurred while restoring the position."}),
            500,
        )

    # Unknown exception
    if restored == EEXCEPT:
        return (
            jsonify({"error": "An error occurred while restoring the position."}),
            500,
        )

    # Position not found
    if restored == EPOSDNE:
        return (
            jsonify({"error": "Position not found."}),
            400,
        )

    # No errors
    return jsonify({"message": "Position restored successfully."}), 200


################################################################################

################################################################################
### RELATION FUNCTIONS #########################################################
################################################################################


# API
@ems_routes.route("/api/relation/create", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_relation_create():
    """
    API endpoint to create a new employee-position relation.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    data.pop("_csrf_token", None)

    date_fields = ["start_date", "end_date"]

    for field in date_fields:
        if data.get(field):
            # Converts "YYYY-MM-DD" string to a Python date object
            data[field] = datetime.strptime(data[field], "%Y-%m-%d").date()

    if data.get("position_id"):
        data["position_id"] = int(data["position_id"])

    if data.get("employee_id"):
        data["employee_id"] = int(data["employee_id"])

    if data:
        created = create_relation(**data)

        # Fatal error
        if not created:
            return (
                jsonify(
                    {"error": "A fatal error occurred while creating the relation."}
                ),
                500,
            )

        # Already exists
        if created == EEXISTS:
            return (
                jsonify(
                    {
                        "error": "A relation already exists with that position and employee."
                    }
                ),
                400,
            )

        # Position not found
        if created == EPOSDNE:
            return (
                jsonify({"error": "Position not found."}),
                400,
            )

        # Employee not found
        if created == EEMPDNE:
            return (
                jsonify({"error": "Employee not found."}),
                400,
            )

        # Missing required fields
        if created == EMISSING:
            return (
                jsonify({"error": "Missing required fields to create relation."}),
                400,
            )

        # Unknown exception
        if created == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while creating the relation."}),
                500,
            )

        # Groups error
        if created == EGROUP:
            return (
                jsonify(
                    {
                        "error": "The relation was created, but there was an error updating \
                            the employee's Google Groups. Check that the group email is correct \
                            and manually remove the employee from the group."
                    }
                ),
                400,
            )

        # Slack error
        if created == ESLACK:
            return (
                jsonify(
                    {
                        "error": "The relation was created, but there was an error updating \
                            the employee's Slack channels. Check that the channel IDs are correct \
                            and manually remove the employee from the channels."
                    }
                ),
                400,
            )

        # No errors
        return jsonify({"message": "Relation created", "request": created}), 200

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot create relation with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/relation/<int:uid>/modify", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_relation_modify(uid):
    """
    API endpoint to modify an existing employee-position relation.

    Args:
        uid (int): The unique ID of the relation to modify.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    # Extract data from request
    data = request.get_json() or {}

    # Remove the CSRF token from the JSON to pass to the function
    data.pop("_csrf_token", None)

    date_fields = ["start_date", "end_date"]

    for field in date_fields:
        if data.get(field):
            # Converts "YYYY-MM-DD" string to a Python date object
            data[field] = datetime.strptime(data[field], "%Y-%m-%d").date()

    if data.get("position_id"):
        data["position_id"] = int(data["position_id"])

    if data.get("employee_id"):
        data["employee_id"] = int(data["employee_id"])

    if data:
        modified = modify_relation(uid, **data)

        # Fatal error
        if not modified:
            return (
                jsonify(
                    {"error": "A fatal error occurred while modifying the relation."}
                ),
                500,
            )

        # Unknown exception
        if modified == EEXCEPT:
            return (
                jsonify({"error": "An error occurred while modifying the relation."}),
                500,
            )

        # Relation not found
        if modified == ERELDNE:
            return (
                jsonify({"error": "Relation not found."}),
                400,
            )

        # Employee not found
        if modified == EEMPDNE:
            return (
                jsonify({"error": "Associated employee not found."}),
                400,
            )

        # Groups error
        if modified == EGROUP:
            return (
                jsonify(
                    {
                        "error": "The relation was modified, but there was an error updating \
                            the employee's Google Groups. Check that the group email is correct \
                            and manually remove the employee from the group."
                    }
                ),
                400,
            )

        # Slack error
        if modified == ESLACK:
            return (
                jsonify(
                    {
                        "error": "The relation was modified, but there was an error updating \
                            the employee's Slack channels. Check that the channel IDs are correct \
                            and manually remove the employee from the channels."
                    }
                ),
                400,
            )

        # No errors
        return jsonify({"message": "Relation modified.", "request": modified}), 200

    # No data entered
    return (
        jsonify(
            {
                "error": "No data was entered. Cannot modify relation with no information."
            }
        ),
        400,
    )


# API
@ems_routes.route("/api/relation/get/all", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_relation_get_all():
    """
    API endpoint to get all employee-position relations.

    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    relations = get_all_relations()
    return jsonify(relations), 200


# API
@ems_routes.route("/api/relation/<int:uid>/get", methods=["GET"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_relation_get_by_id(uid):
    """
    API endpoint to get an employee-position relation by its unique ID.

    Args:
        uid (int): The unique ID of the relation.
    Returns:
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    relation = get_relation_by_id(uid)

    # Fatal error
    if not relation:
        return (
            jsonify({"error": "A fatal error occurred while retrieving the relation."}),
            500,
        )

    # Relation not found
    if relation == ERELDNE:
        return jsonify({"error": "Relation not found."}), 400

    # No errors
    return jsonify(relation), 200


# API
@ems_routes.route("api/relation/<int:uid>/delete", methods=["POST"])
@login_required
@restrict_to(EMS_ADMIN_ACCESS_GROUPS)
def ems_api_relation_delete(uid):
    """
    API endpoint to delete an employee-position relation.

    Args:
        uid (int): The unique ID of the relation to delete.

    Returns:e
        (json, int): A tuple containing a JSON response and HTTP status code.
    """
    deleted = delete_relation(uid)

    # Fatal error
    if not deleted:
        return jsonify({"error": "Relation not found."}), 500

    # Unknown exception
    if deleted == EEXCEPT:
        return jsonify({"error": "An error occurred while deleting the relation."}), 500

    # Relation not found
    if deleted == ERELDNE:
        return jsonify({"error": "Relation not found."}), 400

    # Employee not found
    if deleted == EEMPDNE:
        return jsonify({"error": "Associated employee not found."}), 400

    # Groups error
    if deleted == EGROUP:
        return (
            jsonify(
                {
                    "error": "The relation was deleted, but there was an error updating \
                        the employee's Google Groups. Check that the group email is correct \
                        and manually remove the employee from the group."
                }
            ),
            400,
        )

    # Slack error
    if deleted == ESLACK:
        return (
            jsonify(
                {
                    "error": "The relation was deleted, but there was an error updating \
                        the employee's Slack channels. Check that the channel IDs are correct \
                        and manually remove the employee from the channels."
                }
            ),
            400,
        )

    # No errors
    return jsonify({"message": "Relation deleted successfully."}), 200


################################################################################

################################################################################
### HELPER FUNCTIONS ###########################################################
################################################################################


def validate_csv(csv):
    """
    Validates CSV uploaded to create multiple employees at once

    Arguments:
        `csv`: pandas dataframe

    Returns:
        None

    """
    logging.debug(f"Validating uploaded CSV with columns: {csv.columns.tolist()}")

    required_columns = [
        "last_name",
        "first_name",
        "imc_email",
        "status",
    ]
    not_req_columns = [
        "user_uid",
        "pronouns",
        "personal_email",
        "phone_number",
        "permanent_address_1",
        "permanent_address_2",
        "permanent_city",
        "permanent_state",
        "permanent_zip",
        "major",
        "major_2",
        "major_3",
        "minor",
        "minor_2",
        "minor_3",
        "birth_date",
        "payroll_number",
        "initial_hire_date",
        "graduation",
    ]
    invalid_columns = []
    missing_columns = []
    for req_col in required_columns:
        if req_col not in csv.columns:
            missing_columns.append(req_col)
    for col in csv.columns:
        if col not in not_req_columns and col not in required_columns:
            invalid_columns.append(col)
    if len(missing_columns) > 0:
        logging.debug(f"CSV is missing required columns: {missing_columns}")
        raise Exception(f"CSV missing columns: {missing_columns}")
    if len(invalid_columns) > 0:
        logging.debug(f"CSV contains invalid columns: {invalid_columns}")
        raise Exception(f"CSV contains invalid columns: {invalid_columns}")
    # use create API to validate each row

    csv = csv.where(csv.notnull(), None)
    csv["permanent_zip"] = csv["permanent_zip"].astype(str)

    for i, row in csv.iterrows():
        # Convert row to dict and remove any keys where the value is None or NaN
        row_dict = {k: v for k, v in row.to_dict().items() if v is not None and v == v}

        logging.debug(f"Validating row {i} with data: {row_dict}")
        res = create_employee(row_dict)

        # Check for errors
        if not isinstance(res, dict):
            if not res:
                logging.debug(
                    f"Fatal error occurred while creating employee for row {i}."
                )
                error = "A fatal error occurred while creating the employee."
            if res == EEXISTS:
                logging.debug(
                    f"An employee already exists with that IMC email for row {i}."
                )
                error = "An employee already exists with that IMC email."
            if res == EUSERDNE:
                logging.debug(
                    f"The associated user account does not exist for row {i}."
                )
                error = "The associated user account does not exist."
            if res == EMISSING:
                logging.debug(
                    f"Missing required fields for employee creation for row {i}."
                )
                error = "Missing required fields for employee creation."
            if res == EEXCEPT:
                logging.debug(
                    f"An unexpected error occurred during employee creation for row {i}."
                )
                error = "An unexpected error occurred during employee creation."

            raise Exception(
                f"Successfully uploaded until row {i+1} of data before an error occurred; {error}"
            )


################################################################################
### ORG CHART FUNCTIONS ########################################################
################################################################################


@ems_routes.route("/api/org/tree", methods=["GET"])
@login_required
def get_org_tree():
    """
    Build org chart hierarchy for a specific company.
    Company is at root with all positions branching from it.
    Multiple employees in same position share children nodes.
    """
    try:
        # Get company parameter from request
        company_filter = request.args.get("company", "").strip()

        if not company_filter:
            return (
                jsonify({"success": False, "error": "Company parameter is required"}),
                400,
            )

        # Get database data
        employees = get_all_employee_cards()
        positions = get_all_position_cards()
        relations = get_all_relations()

        # Filter positions by company
        positions = [
            p for p in positions if p.get("brand", "").lower() == company_filter.lower()
        ]

        # Return empty structure if no positions found
        if not positions:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "name": company_filter.upper(),
                            "title": company_filter,
                            "brand": company_filter,
                            "has_employee": False,
                            "is_company_root": True,
                            "children": [],
                        },
                        "company": company_filter,
                    }
                ),
                200,
            )

        # Create lookup dictionaries
        employee_dict = {emp["uid"]: emp for emp in employees}
        position_dict = {pos["uid"]: pos for pos in positions}

        # Map employees to their positions (active relations only)
        position_employees_map = {}
        for rel in relations:
            if not rel.get("end_date"):
                emp_id = rel["employee_id"]
                pos_id = rel["position_id"]
                if pos_id in position_dict:
                    if pos_id not in position_employees_map:
                        position_employees_map[pos_id] = []
                    position_employees_map[pos_id].append(emp_id)

        # Build position hierarchy structure
        position_hierarchy = {}
        position_parents = {}

        # Initialize position nodes
        for pos in positions:
            pos_id = pos["uid"]
            position_hierarchy[pos_id] = {
                "position": pos,
                "children": [],
                "parent": None,
                "employees": position_employees_map.get(pos_id, []),
                "is_manager": bool(pos.get("direct_reports")),
            }

            # Track supervisor relationships
            for sup_id in pos.get("supervisors", []):
                if sup_id in position_dict:
                    position_parents[pos_id] = sup_id

        # Build parent-child relationships from direct reports
        for pos_id, pos_data in position_hierarchy.items():
            for report_id in pos_data["position"].get("direct_reports", []):
                if report_id in position_hierarchy:
                    if report_id not in pos_data["children"]:
                        pos_data["children"].append(report_id)
                    if position_hierarchy[report_id]["parent"] is None:
                        position_hierarchy[report_id]["parent"] = pos_id

            # Add supervisor relationships
            if pos_data["parent"] is None and pos_id in position_parents:
                parent_id = position_parents[pos_id]
                if parent_id in position_hierarchy:
                    pos_data["parent"] = parent_id
                    if pos_id not in position_hierarchy[parent_id]["children"]:
                        position_hierarchy[parent_id]["children"].append(pos_id)

        # Find root positions (no parent)
        root_positions = []
        for pos_id, pos_data in position_hierarchy.items():
            if pos_data["parent"] is None:
                root_positions.append(pos_id)

        # Cache for shared children nodes
        node_cache = {}

        # Recursive function to build tree nodes
        def build_position_tree(pos_id, visited=None):
            if visited is None:
                visited = set()

            if pos_id in visited:
                return None
            visited.add(pos_id)

            if pos_id not in position_hierarchy:
                return None

            pos_data = position_hierarchy[pos_id]
            pos = pos_data["position"]

            # Get employees in this position
            employees_in_pos = []
            for emp_id in pos_data["employees"]:
                if emp_id in employee_dict:
                    employees_in_pos.append(employee_dict[emp_id])

            position_nodes = []

            # Create nodes for employees or vacant position
            if employees_in_pos:
                for emp in employees_in_pos:
                    emp_node = {
                        "name": f"{emp['first_name']} {emp['last_name']}",
                        "title": pos["title"],
                        "brand": pos["brand"],
                        "has_employee": True,
                        "employee_data": {
                            "id": emp["uid"],
                            "first_name": emp["first_name"],
                            "last_name": emp["last_name"],
                            "email": emp["imc_email"],
                            "status": emp["status"],
                        },
                        "position_id": pos_id,
                        "is_manager": pos_data["is_manager"],
                        "is_position_node": True,
                        "position_title": pos["title"],
                    }

                    # Add children (shared for all employees in same position)
                    if pos_data["children"]:
                        cache_key = f"children_{pos_id}"
                        if cache_key not in node_cache:
                            child_nodes = []
                            for child_id in pos_data["children"]:
                                child_node = build_position_tree(
                                    child_id, visited.copy()
                                )
                                if child_node:
                                    if isinstance(child_node, list):
                                        child_nodes.extend(child_node)
                                    else:
                                        child_nodes.append(child_node)
                            node_cache[cache_key] = child_nodes

                        if node_cache[cache_key]:
                            emp_node["children"] = node_cache[cache_key]

                    position_nodes.append(emp_node)
            else:
                vacant_node = {
                    "name": f"{pos['title']} (Vacant)",
                    "title": pos["title"],
                    "brand": pos["brand"],
                    "has_employee": False,
                    "position_id": pos_id,
                    "is_manager": pos_data["is_manager"],
                    "is_position_node": True,
                    "position_title": pos["title"],
                }

                if pos_data["children"]:
                    cache_key = f"children_{pos_id}"
                    if cache_key not in node_cache:
                        child_nodes = []
                        for child_id in pos_data["children"]:
                            child_node = build_position_tree(child_id, visited.copy())
                            if child_node:
                                if isinstance(child_node, list):
                                    child_nodes.extend(child_node)
                                else:
                                    child_nodes.append(child_node)
                        node_cache[cache_key] = child_nodes

                    if node_cache[cache_key]:
                        vacant_node["children"] = node_cache[cache_key]

                position_nodes.append(vacant_node)

            # Return single node or list of nodes
            return (
                position_nodes
                if len(position_nodes) > 1
                else (position_nodes[0] if position_nodes else None)
            )

        # Build tree from root positions
        company_children = []
        for root_id in root_positions:
            root_node = build_position_tree(root_id)
            if root_node:
                if isinstance(root_node, list):
                    company_children.extend(root_node)
                else:
                    company_children.append(root_node)

        # Create flat structure if no hierarchy found
        if not company_children:
            for pos_id, pos_data in position_hierarchy.items():
                pos = pos_data["position"]
                employees_in_pos = []
                for emp_id in pos_data["employees"]:
                    if emp_id in employee_dict:
                        employees_in_pos.append(employee_dict[emp_id])

                if employees_in_pos:
                    for emp in employees_in_pos:
                        company_children.append(
                            {
                                "name": f"{emp['first_name']} {emp['last_name']}",
                                "title": pos["title"],
                                "brand": pos["brand"],
                                "has_employee": True,
                                "employee_data": {
                                    "id": emp["uid"],
                                    "first_name": emp["first_name"],
                                    "last_name": emp["last_name"],
                                    "email": emp["imc_email"],
                                    "status": emp["status"],
                                },
                                "position_id": pos_id,
                                "is_manager": pos_data["is_manager"],
                                "is_position_node": True,
                            }
                        )
                else:
                    company_children.append(
                        {
                            "name": f"{pos['title']} (Vacant)",
                            "title": pos["title"],
                            "brand": pos["brand"],
                            "has_employee": False,
                            "position_id": pos_id,
                            "is_manager": pos_data["is_manager"],
                            "is_position_node": True,
                        }
                    )

        # Create final company root node
        org_tree = {
            "name": company_filter.upper(),
            "title": company_filter,
            "brand": company_filter,
            "has_employee": False,
            "is_company_root": True,
            "is_manager": True,
            "children": company_children,
        }

        return (
            jsonify({"success": True, "data": org_tree, "company": company_filter}),
            200,
        )

    except Exception as e:
        import traceback

        print(f"ERROR building org chart: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
