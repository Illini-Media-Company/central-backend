from flask import Blueprint, redirect, request, url_for
from flask_cors import cross_origin
from flask_login import login_required
import requests
import urllib

from constants import OV_ENDPOINT
from util.security import csrf, verify_recaptcha

overlooked_routes = Blueprint("overlooked_routes", __name__, url_prefix="/overlooked")


@overlooked_routes.route("/subscribe", methods=["POST"])
@csrf.exempt
@cross_origin()
def sub():
    email = request.form["email"]
    # newsletter = request.form["newsletter"]
    recaptcha_token = request.form["grecaptcha_token"]
    recaptcha_score = verify_recaptcha(recaptcha_token)

    headers = {
        "Content-Type": "application/json",
    }
    data = {"email": email, "firstName": "", "lastName": ""}

    response = requests.post(OV_ENDPOINT, headers=headers, json=data)
    if response.status_code == 201 or response.status_code == 200:
        print(f"Contact created successfully for {email}")
        print(f"reCAPTCHA score: {recaptcha_score}")
        return "Contact created successfully!", 200
    else:
        print(f"failed to create contact for {email}:")
        print(response)
        return "Failed to create contact.", 500
