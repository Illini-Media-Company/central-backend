from flask import Blueprint, request
from flask_login import current_user, login_required
from util.employee_agreement_slackbot import send_employee_agreement_notification, follow_up_notification

employee_agreement_routes = Blueprint("employee_agreement_routes", __name__, url_prefix="/employee-agreement")



#we need to get the user_slack_id and agreement_url from the request this will be from the employee agreement db 


@employee_agreement_routes.route("/send-notification", methods=["POST"])
@login_required
def send_notification():
    send_employee_agreement_notification("U09LTPY3MSP", "http://example.com/agreement")
    return "Notification sent", 200

@employee_agreement_routes.route("/send-follow-up", methods=["POST"])
@login_required
def send_follow_up():
    follow_up_notification("U09LTPY3MSP")
    return "Follow-up sent", 200


#in python and jinga we can do {{current_user.name}} to get the name of the user

