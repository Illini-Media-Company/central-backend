import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from util.security import get_admin_creds

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

def send_song_request_update_email(to_email: str, song_name: str, artist_name: str, status: str, rejection_reason: str = None) -> dict:
    """
    Sends an update email to an outside user via the Gmail API regarding their song request.
    Returns {"ok": True, "message_id": ...} on success, or {"ok": False, "error": ...} on failure.
    """
    if not to_email:
        return {"ok": False, "error": "No email provided"}

    creds = get_admin_creds(GMAIL_SEND_SCOPE)

    # Change this to different email later 
    sender_email = "helpdesk@illinimedia.com" 
    
   
    if isinstance(creds, service_account.Credentials):
        creds = creds.with_scopes([GMAIL_SEND_SCOPE]).with_subject(sender_email)

    service = build("gmail", "v1", credentials=creds)

    subject = f"WPGU Song Request Update: {song_name}"
    
    if status == "accepted":
        text_body = (
            f"Hi there!\n\n"
            f"Great news! Your request for '{song_name}' by {artist_name} "
            f"has been approved and added to the WPGU library.\n\n"
            f"Make sure you listen in to hear it in the future!\n\n"
            f"- The WPGU Music Team"
        )
    elif status == "declined":
        reason_text = f" Reason: {rejection_reason}" if rejection_reason else ""
        text_body = (
            f"Hi there,\n\n"
            f"Thank you for submitting a request for '{song_name}' by {artist_name}. "
            f"Unfortunately, we are unable to add it to the WPGU library at this time.{reason_text}\n\n"
            f"We appreciate your suggestion, keep listening to WPGU!\n\n"
            f"- The WPGU Music Team"
        )
    else:
        return {"ok": False, "error": "Invalid status for email."}

    html_body = text_body.replace('\n', '<br>')

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info(f"WPGU update email sent to {to_email} regarding {song_name}")
        return {"ok": True, "message_id": sent.get("id")}
    except HttpError as e:
        logger.error(f"Failed to send WPGU email to {to_email}: {e}")
        return {"ok": False, "error": str(e)}