from flask import Blueprint, request, render_template
from util.slackbots.slackbot import app
from util.security import restrict_to
from flask_login import current_user, login_required
from util.slackbots.employee_agreement_slackbot import (
    send_employee_agreement_notification,
)
from db.employee_agreement import (
    add_employee_agreement,
    get_employee_agreements_by_user,
    get_pending_agreements_for_editor,
    get_pending_agreements_for_manager,
    get_pending_agreements_for_chief,
    get_agreement_objects_by_user,
)
from zoneinfo import ZoneInfo
from datetime import datetime

employee_agreement_routes = Blueprint(
    "employee_agreement_routes", __name__, url_prefix="/employee-agreement"
)
from google.cloud import ndb

client = ndb.Client()

# we need to get the user_slack_id and agreement_url from the request this will be from the employee agreement db
# do we need to get a get, which is the input from the user and then post to send the notification using the input from the manager
# after that we need to get the update from the signature as another get and that tells us when to send the follow up notification
"""
@employee_agreement_routes.route("/send-notification", methods=["POST"])
@login_required
def send_notification():
    send_employee_agreement_notification("U09LTPY3MSP", "http://example.com/agreement")
    return "Notification sent", 200
"""


@employee_agreement_routes.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    user_name = current_user.name
    return render_template(
        "di_contract_automization_dashboard.html", currentUserName=user_name
    )


@employee_agreement_routes.route("/admin", methods=["GET"])
@login_required
@restrict_to(["imc-staff-webdev", "di-section-editors"])
def admin_dashboard():
    return render_template("di_contract_automization_admin.html")


@employee_agreement_routes.route("/send-notification", methods=["POST"])
@login_required
def send_notification():
    data = request.get_json()
    emails = data.get("emails", [])

    if not emails:
        return "No emails provided", 400
    manager_email = data.get("manager", "")
    chief_email = data.get("chief", "")
    editor_email = data.get("editor", "")
    url = data.get("agreement_link", "")

    for email in emails:
        email = email.strip()

        user_data = app.client.users_lookupByEmail(email=email)

        # we need to do the lookup by email for hring manager, editor, cheif
        # assume that the hiring manager would be the only one on this page
        editor_data = app.client.users_lookupByEmail(email=editor_email)
        if not editor_data.get("ok"):
            return "editor manager not found", 404
        editor_slack_id = editor_data["user"]["id"]

        manager_data = app.client.users_lookupByEmail(email=manager_email)
        if not manager_data.get("ok"):
            return "Manager not found", 404
        manager_slack_id = manager_data["user"]["id"]

        chief_data = app.client.users_lookupByEmail(email=chief_email)
        if not chief_data.get("ok"):
            return "Chief not found", 404
        chief_slack_id = chief_data["user"]["id"]

        if user_data.get("ok"):
            user_slack_id = user_data["user"]["id"]
            agreement_url = url

            add_employee_agreement(
                user_id=user_slack_id,
                editor_id=editor_slack_id,
                manager_id=manager_slack_id,
                chief_id=chief_slack_id,
                agreement_url=agreement_url,
            )

            # we need to add the user to the db and then call the notification function
            send_employee_agreement_notification(user_slack_id)
        else:
            return f"User with email {email} not found", 404
    return "Emails sucessfully sent", 200


@employee_agreement_routes.route("/get-pending-signatures", methods=["GET"])
@login_required
def get_pending_signatures():
    logged_in_user_email = current_user.email
    user_data = app.client.users_lookupByEmail(email=logged_in_user_email)
    if not user_data.get("ok"):
        return "User not found", 404
    user_slack_id = user_data["user"]["id"]
    pending_agreements = []
    my_agreements_list = get_employee_agreements_by_user(user_slack_id)

    for agreement in my_agreements_list:
        if agreement["user_signed"] is None:
            pending_agreements.append(agreement)
    # Check for pending agreements as editor
    editor_agreements = get_pending_agreements_for_editor(user_slack_id)
    pending_agreements.extend(editor_agreements)
    # Check for pending agreements as manager
    manager_agreements = get_pending_agreements_for_manager(user_slack_id)
    pending_agreements.extend(manager_agreements)
    # Check for pending agreements as chief
    chief_agreements = get_pending_agreements_for_chief(user_slack_id)
    pending_agreements.extend(chief_agreements)
    return {"pending_agreements": pending_agreements}, 200


# called after the user signs the agreement on the webpage
@employee_agreement_routes.route("/sign-agreement", methods=["POST"])
@login_required
def sign_agreement():
    data = request.get_json()
    agreement_user_id = data.get("agreement_user_id")
    if not agreement_user_id:
        return "Agreement ID is required", 400
    logged_in_user_email = current_user.email
    user_data = app.client.users_lookupByEmail(email=logged_in_user_email)
    if not user_data.get("ok"):
        return "User not found", 404
    signer_slack_id = user_data["user"]["id"]
    agreement_list = get_agreement_objects_by_user(agreement_user_id)
    if not agreement_list:
        return "Agreement not found", 404

    agreement = None

    for agr in agreement_list:
        if signer_slack_id == agr.user_id and agr.user_signed is None:
            agreement = agr
            break
        elif signer_slack_id == agr.editor_id and agr.editor_signed is None:
            agreement = agr
            break
        elif signer_slack_id == agr.manager_id and agr.manager_signed is None:
            agreement = agr
            break
        elif signer_slack_id == agr.chief_id and agr.chief_signed is None:
            agreement = agr
            break

    if not agreement:
        return (
            "You are not authorized to sign this agreement, it's not your turn, or it has already been signed",
            403,
        )

    next_signer_id = None
    next_signer_role = None

    if signer_slack_id == agreement.user_id and agreement.user_signed is None:
        agreement.user_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
        next_signer_id = agreement.editor_id
        next_signer_role = "editor"
    elif signer_slack_id == agreement.editor_id and agreement.editor_signed is None:
        agreement.editor_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
        next_signer_id = agreement.manager_id
        next_signer_role = "manager"
    elif signer_slack_id == agreement.manager_id and agreement.manager_signed is None:
        agreement.manager_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
        next_signer_id = agreement.chief_id  # FIX: Set next signer
        next_signer_role = "chief"
    elif signer_slack_id == agreement.chief_id and agreement.chief_signed is None:
        agreement.chief_signed = datetime.now(tz=ZoneInfo("America/Chicago"))
    else:
        return (
            "You are not authorized to sign this agreement or have already signed",
            403,
        )

    with client.context():
        agreement.put()

    if next_signer_id:  # Check if there *is* a next signer
        pending_list = []
        if next_signer_role == "editor":
            pending_list = get_pending_agreements_for_editor(next_signer_id)
        elif next_signer_role == "manager":
            pending_list = get_pending_agreements_for_manager(next_signer_id)
        elif next_signer_role == "chief":
            pending_list = get_pending_agreements_for_chief(next_signer_id)

        if len(pending_list) == 1:
            send_employee_agreement_notification(next_signer_id)

    return "Agreement signed successfully", 200
