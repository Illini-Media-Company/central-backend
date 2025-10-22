from flask import Blueprint, request
from util.slackbot import app
from flask_login import current_user, login_required
from util.employee_agreement_slackbot import send_employee_agreement_notification, follow_up_notification
from db.employee_agreement import add_employee_agreement, get_employee_agreement_by_user

employee_agreement_routes = Blueprint("employee_agreement_routes", __name__, url_prefix="/employee-agreement")



#we need to get the user_slack_id and agreement_url from the request this will be from the employee agreement db 
#do we need to get a get, which is the input from the user and then post to send the notification using the input from the manager 
#after that we need to get the update from the signature as another get and that tells us when to send the follow up notification 
"""
@employee_agreement_routes.route("/send-notification", methods=["POST"])
@login_required
def send_notification():
    send_employee_agreement_notification("U09LTPY3MSP", "http://example.com/agreement")
    return "Notification sent", 200
"""

@employee_agreement_routes.route("/send-notification", methods=["POST"])
@login_required
def send_notification():
    data = request.get_json()
    emails = data.get("emails", [])

    if not emails:
        return "No emails provided", 400

    for email in emails:
        email = email.strip()

        user_data = app.client.users_lookupByEmail(email=email)

        #we need to do the lookup by email for hring manager, editor, cheif
        #assume that the hiring manager would be the only one on this page 
        hiring_email = current_user.email
        hiring_data = app.client.users_lookupByEmail(email=hiring_email)
        if not hiring_data.get("ok"):
            return "Hiring manager not found", 404
        hiring_slack_id = hiring_data["user"]["id"]


        if (user_data.get("ok")):
            user_slack_id = user_data["user"]["id"]
            agreement_url = "http://example.com/agreement" #change to match the site that will be used for the agreement

            #fix this with the correct stuff how are we getting managerid and cheif id, are these imputs from the hirer 
            add_employee_agreement(user_id=user_slack_id, hiring_id=hiring_slack_id, manager_id="", chief_id="", agreement_url=agreement_url)

            #we need to add the user to the db and then call the notification function
            send_employee_agreement_notification(user_slack_id, agreement_url)
        else :
            return f"User with email {email} not found", 404

            
    return "Emails sucessfully sent", 200  



#is it better to have a function that is universal or should we have multiple functions for each step of the process

#called after the user signs the agreement on the webpage 
@employee_agreement_routes.route("/send-next-notifcation", methods=["POST"])
@login_required
def send_next_notification():

    logged_in_user_email = current_user.email
    user_data = app.client.users_lookupByEmail(email=logged_in_user_email)

    if not user_data.get("ok"):
        return "User not found", 404
    
    employee_agreement = get_employee_agreement_by_user(user_data["user"]["id"])

    if not employee_agreement:
        return "Employee agreement not found", 404
    # Logic to determine the next notification recipient
    recipient_id = None

    if employee_agreement["user_signed"] is None:
        recipient_id = employee_agreement["user_id"]
    elif employee_agreement["hriring_signed"] is None:
        recipient_id = employee_agreement["hiring_id"]
    elif employee_agreement["manager_signed"] is None:
        recipient_id = employee_agreement["manager_id"]     
    elif employee_agreement["chief_signed"] is None:
        recipient_id = employee_agreement["cheif_id"]
    
    if recipient_id is None:
        return "All parties have signed the agreement", 200
    
    agreement_url = employee_agreement["agreement_url"]
    #we should send a follow up email maybe saying who has signed it so far and what is left to be signed
    send_employee_agreement_notification(recipient_id, agreement_url)
     




@employee_agreement_routes.route("/send-follow-up", methods=["POST"])
@login_required
def send_follow_up():
    follow_up_notification("U09LTPY3MSP")
    return "Follow-up sent", 200


#in python and jinga we can do {{current_user.name}} to get the name of the user

#app.client.users_lookupByEmail to find user by email 
# need to make sure that the user and bot have the read.email 


#we can get the user and the hiring manager id, how are we getting the editors id and how are we getting cheif id 


"""
what it will look like:
{
    "ok": true,
    "user": {
        "id": "U0123ABCDE", // <-- This is the Slack User ID you need!
        "team_id": "TXXXXXXXX",
        "name": "john.doe",
        "profile": {
            "email": "user@example.com",
            // ... other profile fields
        },
        """

#need to itterate thriough all inputs, create a user and their email based on their user id
#store the perosn id and email in the db
#then send the notification to the user based on their email
# should check with group to see what  they have done 