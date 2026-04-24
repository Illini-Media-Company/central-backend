"""Shared helpers for sending Gmail API messages."""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from util.security import get_admin_creds

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def send_gmail_message(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    impersonated_sender: str,
    from_header: str | None = None,
) -> dict:
    """Send a multipart Gmail message using admin impersonation."""
    if not to_email:
        return {"ok": False, "error": "No recipient email provided"}
    if not subject:
        return {"ok": False, "error": "No subject provided"}
    if not text_body:
        return {"ok": False, "error": "No text body provided"}
    if not html_body:
        return {"ok": False, "error": "No HTML body provided"}
    if not impersonated_sender:
        return {"ok": False, "error": "No impersonated sender provided"}

    creds = get_admin_creds([GMAIL_SEND_SCOPE])
    if isinstance(creds, service_account.Credentials):
        creds = creds.with_scopes([GMAIL_SEND_SCOPE]).with_subject(impersonated_sender)

    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["From"] = from_header or impersonated_sender
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("Gmail message sent to %s with subject %s", to_email, subject)
        return {"ok": True, "message_id": sent.get("id")}
    except HttpError as exc:
        logger.error(
            "Failed to send Gmail message to %s with subject %s: %s",
            to_email,
            subject,
            exc,
        )
        return {"ok": False, "error": str(exc)}
