import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from util.security import get_admin_creds

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

"""
Sends the onboarding email via Gmail API using admin/service-account credentials.
Validates required inputs, builds both plain-text and HTML email bodies, and sends
from the configured sender (onboarding@illinimedia.com). Returns {"ok": True, "message_id": ...}
on success, or {"ok": False, "error": ...} if the Gmail API call fails.
"""


def send_onboarding_email(to_email: str, first_name: str, onboarding_url: str) -> dict:
    if not to_email:
        raise ValueError("to_email is required")
    if not onboarding_url:
        raise ValueError("onboarding_url is required")

    creds = get_admin_creds(GMAIL_SEND_SCOPE)

    # Only impersonate if creds are service-account creds
    # sender_email = "imc_admin@illinimedia.com"
    sender_email = "onboarding@illinimedia.com"
    if isinstance(creds, service_account.Credentials):
        creds = creds.with_scopes([GMAIL_SEND_SCOPE]).with_subject(sender_email)

    service = build("gmail", "v1", credentials=creds)

    subject = "Complete your Illini Media onboarding"
    text_body = f"""Hi {first_name},

Welcome to Illini Media! Please fill out your onboarding form using the link below:

{onboarding_url}

If you have any issues accessing the form, reply to this email.

Best,
Illini Media Team
"""

    html_body = f"""
    <html><body>
      <p>Hi {first_name},</p>
      <p>Welcome to Illini Media! Please fill out your onboarding form using the link below:</p>
      <p><a href="{onboarding_url}">Complete Onboarding Form</a></p>
      <p>If you have any issues accessing the form, reply to this email.</p>
      <p>Best,<br/>Illini Media Team</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "message_id": sent.get("id")}
    except HttpError as e:
        return {"ok": False, "error": str(e)}


"""
This file defines the helper functions and error codes for the Employee Management System.

Created by Jacob Slabosz on Feb. 3, 2026
Last modified Feb. 3, 2026
"""

EUSERDNE = -1  # User does not exist
EEMPDNE = -2  # EmployeeCard does not exist
EPOSDNE = -3  # PositionCard does not exist
ERELDNE = -4  # EmployeePositionRelation does not exist

EMISSING = -5  # Required field is missing
EEXCEPT = -6  # Unknown exception occurred during operation
EEXISTS = -7  # EmployeeCard or EmployeePositionRelation already exists
ESUPREP = -8  # Error setting supervisor(s) or direct report(s)
EGROUP = -9  # Google Groups update failed
EGROUPDNE = -10  # Google Group email does not exist or is invalid
ESLACKDNE = -11  # Slack channel ID does not exist or is not accessible


# Get correct image URL
def get_ems_brand_image_url(brand: str) -> str:
    """
    Returns the image URL for a given brand.

    Args:
        brand (str): The brand name.

    Returns:
        str: The image URL for the brand.
    """
    brand_images = {
        "Chambana Eats": "/static/brandmarks/background/96x96/CE_SquareIcon.png",
        "The Daily Illini": "/static/brandmarks/background/96x96/DI_SquareIcon.png",
        "Illini Content Studio": "/static/brandmarks/background/96x96/ICS_SquareIcon.png",
        "Illio": "/static/brandmarks/background/96x96/Illio_SquareIcon.png",
        "IMC": "/static/brandmarks/background/96x96/IMC_SquareIcon.png",
        "WPGU": "/static/brandmarks/background/96x96/WPGU_SquareIcon.png",
    }
    return brand_images.get(brand, "/static/defaults/position_profile.png")
