from flask import Blueprint, request, render_template
from util.security import restrict_to
from flask_login import current_user, login_required
from util.slackbots.employee_agreement_slackbot import (
    send_employee_agreement_notification,
    send_reviewer_notification,
    send_confirmation_notification,
)
from db.employee_agreement import (
    add_employee_agreement,
    sign_update_agreement,
    get_agreement_name,
    get_pending_agreements_for_user,
    get_pending_agreements_for_editor,
    get_pending_agreements_for_manager,
    get_pending_agreements_for_chief,
    get_past_agreements_for_user,
    get_incomplete_agreements,
    remove_agreement,
    get_agreement_by_id,
    update_slack_info,
)

employee_agreement_routes = Blueprint(
    "employee_agreement_routes", __name__, url_prefix="/employee-agreement"
)


@employee_agreement_routes.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    # Get the user's name (used for the signature)
    user_name = current_user.name

    pending_agreements = []
    logged_in_user_email = current_user.email

    # Get pending agreements treating user as employee, editor, manager and EIC
    user_agreements = get_pending_agreements_for_user(logged_in_user_email)
    editor_agreements = get_pending_agreements_for_editor(logged_in_user_email)
    manager_agreements = get_pending_agreements_for_manager(logged_in_user_email)
    chief_agreements = get_pending_agreements_for_chief(logged_in_user_email)

    pending_agreements.extend(user_agreements)
    pending_agreements.extend(editor_agreements)
    pending_agreements.extend(manager_agreements)
    pending_agreements.extend(chief_agreements)

    past_agreements = get_past_agreements_for_user(logged_in_user_email)

    return render_template(
        "employee_agreement_dashboard.html",
        currentUserName=user_name,
        agreements=pending_agreements,
        past_agreements=past_agreements,
    )


@employee_agreement_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev", "di-section-editors"])
def admin_dashboard():
    # Handle pagination of in-progress agreements
    page_inprog = int(request.args.get("page-inprog", 1))
    PER_PAGE_INPROG = 8

    all_inprog = get_incomplete_agreements()
    total_inprog = len(all_inprog)

    start_inprog = (page_inprog - 1) * PER_PAGE_INPROG
    end_inprog = start_inprog + PER_PAGE_INPROG
    inprogress = all_inprog[start_inprog:end_inprog]

    return render_template(
        "employee_agreement_admin.html",
        inprogress_agreements=inprogress,
        total_inprog=total_inprog,
        page_inprog=page_inprog,
        per_page_inprog=PER_PAGE_INPROG,
    )


@employee_agreement_routes.route("/submit", methods=["POST"])
@login_required
def send_notification():
    data = request.get_json()
    emails = data.get("emails", [])

    if not emails:
        return "No emails provided.", 400

    # Extract editor, manager, EIC emails
    manager_email = data.get("manager", "")
    chief_email = data.get("chief", "")
    editor_email = data.get("editor", "")
    url = data.get("agreement_link", "")
    agr_name = data.get("agreement_name", "")

    if (
        not manager_email
        or not chief_email
        or not editor_email
        or not url
        or not agr_name
    ):
        return "Missing required information.", 400

    # Add an agreement for each user email
    for email in emails:
        email = email.strip()

        # Add to DB
        temp = add_employee_agreement(
            user_email=email,
            editor_email=editor_email,
            manager_email=manager_email,
            chief_email=chief_email,
            agreement_url=url,
            agreement_name=agr_name,
        )

        uid = temp.get("uid")

        # Send notification to the user
        res = send_employee_agreement_notification(email, agr_name)
        if not res.get("ok"):
            return "Failed to notify a user.", 400

        ch = res.get("channel")
        ts = res.get("ts")

        print(ch, ts)

        res = update_slack_info(int(uid), ch, ts)
        if not res:
            return "Error updating EmployeeAgreement object.", 400
    return "Notifications successfully sent.", 200


# called after the user signs the agreement on the webpage
@employee_agreement_routes.route("/<uid>/sign", methods=["POST"])
@login_required
def sign_agreement(uid):
    logged_in_user_email = current_user.email

    # Sign the agreement in the DB
    status, employee, next = sign_update_agreement(int(uid), logged_in_user_email)

    if status == False:
        return "Error signing agreement", 400

    agr_name = get_agreement_name(int(uid))
    if agr_name is None:
        agr_name = "Agreement"

    # Notify the next person (if there is a next person)
    if next:
        res = send_reviewer_notification(next, employee, agr_name)
        if res.get("ok") == False:
            return "Error notifying next signer.", 400
    else:
        temp = get_agreement_by_id(int(uid))
        ch = temp.get("slack_ch")
        ts = temp.get("slack_ts")

        res = send_confirmation_notification(employee, agr_name, ch, ts)
        if res.get("ok") == False:
            return "Error sending confirmation message.", 400

    return "Agreement signed successfully.", 200


@employee_agreement_routes.route("/<uid>/remove", methods=["POST"])
@login_required
def delete_agreement(uid):
    res = remove_agreement(int(uid))

    if res:
        return "Successfully deleted agreement.", 200
    else:
        return "Failed to delete agreement.", 400
