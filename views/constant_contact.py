import base64

import logging
from flask import Blueprint, redirect, request, url_for, abort
from flask_cors import cross_origin
from flask_login import login_required
import requests
import urllib

from constants import CC_CLIENT_ID, CC_CLIENT_SECRET, CC_LIST_MAPPING
from db.kv_store import kv_store_get, kv_store_set
from util.security import csrf, verify_recaptcha


CC_AUTHORIZATION_URL = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
CC_SUBSCRIBE_URL = "https://api.cc.email/v3/contacts/sign_up_form"

logger = logging.getLogger(__name__)


constant_contact_routes = Blueprint(
    "constant_contact_routes", __name__, url_prefix="/constant-contact"
)


@constant_contact_routes.route("/login", methods=["GET"])
@login_required
def cc_login():
    logger.info("Starting Constant Contact OAuth flow")

    try:
        redirect_url = url_for(
            "constant_contact_routes.cc_login_callback", _external=True
        )

        params = {
            "client_id": CC_CLIENT_ID,
            "client_secret": CC_CLIENT_SECRET,
            "redirect_uri": redirect_url,
            "scope": "contact_data offline_access",
            "response_type": "code",
            "state": "state",
        }

        authorization_url = CC_AUTHORIZATION_URL + "?" + urllib.parse.urlencode(params)

        logger.info(
            f"Redirecting to Constant Contact authorization URL: {authorization_url}"
        )
        return redirect(authorization_url)
    except Exception as e:
        logger.exception(f"Error initiating Constant Contact OAuth flow: {str(e)}")
        abort(
            500,
            description="An error occurred while initiating Constant Contact authentication. Please try again.",
        )


@constant_contact_routes.route("/login/callback", methods=["GET"])
@login_required
def cc_login_callback():
    logger.info("Received Constant Contact OAuth callback")

    try:
        auth_code = request.args.get("code")

        redirect_url = url_for(
            "constant_contact_routes.cc_login_callback", _external=True
        )

        ref_token = get_refresh_token(
            redirect_url, CC_CLIENT_ID, CC_CLIENT_SECRET, auth_code
        )["refresh_token"]

        kv_store_set("CC_REFRESH_TOKEN", ref_token)

        logger.info("Constant Contact OAuth flow completed successfully")
        return redirect(url_for("index"))
    except Exception as e:
        logger.exception(f"Error during Constant Contact OAuth callback: {str(e)}")
        abort(
            500,
            description="An error occurred during Constant Contact authentication. Please try again.",
        )


@constant_contact_routes.route("/subscribe", methods=["POST"])
@csrf.exempt
@cross_origin()
def cc_create_contact():
    logger.info("Received request to subscribe contact to Constant Contact")

    # Extract fields from form
    try:
        email = request.form["email"]
        newsletter = request.form["newsletter"]
        recaptcha_token = request.form["grecaptcha_token"]

        # Verify reCAPTCHA token
        recaptcha_score = verify_recaptcha(recaptcha_token)
        if recaptcha_score < 0.5:
            logger.warning(
                f"reCAPTCHA verification failed for {email} with score {recaptcha_score}"
            )
            return "reCAPTCHA verification failed. Please try again.", 400
    except KeyError as e:
        logger.error(f"Missing required form field: {str(e)}")
        return "Missing required form field.", 400

    # Determine newsletter ID based on mapping
    if newsletter in CC_LIST_MAPPING:
        newsletter_id = CC_LIST_MAPPING[newsletter]
    else:
        logger.warning(f"Invalid newsletter specified: {newsletter}")
        return "Invalid newsletter.", 400

    # Obtain access token
    try:
        redirect_url = url_for(
            "constant_contact_routes.cc_login_callback", _external=True
        )
        ref_token = kv_store_get("CC_REFRESH_TOKEN")
        keys_json = get_access_token(
            redirect_url, CC_CLIENT_ID, CC_CLIENT_SECRET, ref_token
        )
        if not keys_json:
            logger.error("Failed to obtain access token")
            return "Failed to create contact.", 500

        access_token = keys_json["access_token"]
        new_ref_token = keys_json["refresh_token"]
        kv_store_set("CC_REFRESH_TOKEN", new_ref_token)
    except Exception as e:
        logger.exception(f"Error obtaining access token: {str(e)}")
        return "Failed to create contact.", 500

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        data = {
            "create_source": "Account",
            "email_address": email,
            "list_memberships": [newsletter_id],
        }

        response = requests.post(CC_SUBSCRIBE_URL, headers=headers, json=data)

        if response.status_code == 201 or response.status_code == 200:
            logger.info(
                f"Contact created successfully for {email} (reCAPTCHA score: {recaptcha_score})"
            )
            return "Contact created successfully!", 200
        else:
            logger.error(f"Failed to create contact for {email}: {str(response)}")
            return "Failed to create contact.", 500
            # print(f"failed to create contact for {email}")
            # print(response.text)
            # print(f"reCAPTCHA score: {recaptcha_score}")
            # if response.json()[0]["error_key"] == "contacts.api.validation.error":
            #     # We don't want spambots to know
            #     return "Contact created successfully!", 200
            # else:
            #     return "Failed to create contact.", 500
    except Exception as e:
        logger.exception(f"Error creating contact for {email}: {str(e)}")
        return "Failed to create contact.", 500


def get_refresh_token(
    redirect_uri: str, client_id: str, client_secret: str, auth_code: str
) -> dict | None:
    """
    Obtains a refresh token from Constant Contact using the authorization code.

    Arguments:
        `redirect_uri` (`str`): The redirect URI used during the authorization process.
        `client_id` (`str`): The Constant Contact API client ID.
        `client_secret` (`str`): The Constant Contact API client secret.
        `auth_code` (`str`): The authorization code received from Constant Contact.

    Returns:
        `dict | None`: A dictionary containing the refresh token if successful, or `None` if the process fails.
    """
    logger.info("Exchanging Constant Contact authorization code for refresh token.")

    if not auth_code:
        logger.error("No authorization code provided to exchange for refresh token.")
        return None

    try:
        base_url = "https://authz.constantcontact.com/oauth2/default/v1/token"

        to_b64 = client_id + ":" + client_secret

        auth_headers = {
            "Accept": "application/json",
            "Content-type": "application/x-www-form-urlencoded",
            "Authorization": "Basic "
            + base64.b64encode(bytes(to_b64, "utf-8")).decode("utf-8"),
            "create_source": "Account",
        }

        params = {
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        # Post to CC API
        logger.debug(
            f"Sending POST request to {base_url} with grant_type='authorization_code'."
        )
        request_url = base_url + "?" + urllib.parse.urlencode(params)
        response = requests.post(request_url, headers=auth_headers)

        logger.debug(
            f"Received response with status code {response.status_code} from token endpoint."
        )
        response.raise_for_status()  # Raise an exception for HTTP errors

        logger.debug("Attempting to parse JSON response from token endpoint.")
        token_data = response.json()
        logger.info("Successfully obtained new refresh token.")
        return token_data

    # Handle potential HTTP errors
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error occurred: {http_err} — Response content: {response.text}"
        )
        return None

    # Handle potential connection errors
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred: {conn_err}")
        return None

    # Handle potential timeout errors
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred: {timeout_err}")
        return None

    except ValueError as json_err:
        logger.error(
            f"JSON decoding failed: {json_err} — Response content: {response.text}"
        )
        return None

    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while exchanging refresh token: {str(e)}"
        )
        return None


def get_access_token(
    redirect_uri: str, client_id: str, client_secret: str, ref_token: str
) -> dict | None:
    """
    Uses the provided refresh token to obtain a new access token from Constant Contact.

    Arguments:
        `redirect_uri` (`str`): The redirect URI used during the authorization process.
        `client_id` (`str`): The Constant Contact API client ID.
        `client_secret` (`str`): The Constant Contact API client secret.
        `ref_token` (`str`): The refresh token to exchange for a new access token.

    Returns:
        `dict | None`: A dictionary containing the new access token and refresh token if
        successful, or `None` if the token refresh process fails.
    """
    logger.info("Requesting new Constant Contact access token using refresh token")

    if not ref_token:
        logger.error("No refresh token available to obtain access token")
        return None

    try:
        base_url = "https://authz.constantcontact.com/oauth2/default/v1/token"

        to_b64 = client_id + ":" + client_secret

        auth_headers = {
            "Accept": "application/json",
            "Content-type": "application/x-www-form-urlencoded",
            "Authorization": "Basic "
            + base64.b64encode(bytes(to_b64, "utf-8")).decode("utf-8"),
            "create_source": "Account",
        }

        params = {
            "refresh_token": ref_token,
            "redirect_uri": redirect_uri,
            "grant_type": "refresh_token",
        }

        # Post to CC API
        logger.debug(
            f"Sending POST request to {base_url} with grant_type='refresh_token'."
        )
        request_url = base_url + "?" + urllib.parse.urlencode(params)
        response = requests.post(request_url, headers=auth_headers)

        logger.debug(
            f"Received response with status code {response.status_code} from token endpoint."
        )
        response.raise_for_status()  # Raise an exception for HTTP errors

        logger.debug("Attempting to parse JSON response from token endpoint.")
        token_data = response.json()
        logger.info("Successfully obtained new access token.")
        return token_data

    # Handle potential HTTP errors
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error occurred: {http_err} — Response content: {response.text}"
        )
        return None

    # Handle potential connection errors
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred: {conn_err}")
        return None

    # Handle potential timeout errors
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred: {timeout_err}")
        return None

    except ValueError as json_err:
        logger.error(
            f"JSON decoding failed: {json_err} — Response content: {response.text}"
        )
        return None

    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while refreshing access token: {str(e)}"
        )
        return None
