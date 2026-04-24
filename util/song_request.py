"""Email helpers for WPGU song request notifications."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from util.gmail import send_gmail_message

logger = logging.getLogger(__name__)

WPGU_IMPERSONATED_SENDER = "wpgu-no-reply@illinimedia.com"
WPGU_FROM_HEADER = "wpgu-no-reply@wpgu.com"
SONG_REQUEST_EMAIL_TEMPLATE = "wpgu-song-req/wpgu_song_request_email.html"

_EMAIL_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def _build_song_request_email_content(
    song_name: str,
    artist_name: str,
    status: str,
    rejection_reason: str | None = None,
) -> dict:
    if status == "submitted":
        return {
            "subject": f"WPGU Song Request Received: {song_name}",
            "preheader": f"We received your request for {song_name}.",
            "status_label": "Submission Received",
            "status_accent": "#4CAF50",
            "status_tint": "#C8E6C9",
            "headline": "We received your song request",
            "body_paragraphs": [
                (
                    f'Thanks for submitting a request for "{song_name}" by '
                    f"{artist_name} to WPGU 107.1 FM."
                ),
                (
                    "The WPGU Music Team will review it, and because you provided "
                    "this email address, we will send future status updates here."
                ),
            ],
            "rejection_reason": None,
        }

    if status == "accepted":
        return {
            "subject": f"WPGU Song Request Update: {song_name}",
            "preheader": f"Your request for {song_name} was approved.",
            "status_label": "Approved",
            "status_accent": "#4CAF50",
            "status_tint": "#C8E6C9",
            "headline": "Your song request was approved",
            "body_paragraphs": [
                (
                    f'Great news. Your request for "{song_name}" by {artist_name} '
                    "has been approved and added to the WPGU library."
                ),
                "Keep listening to WPGU 107.1 FM to hear it on air.",
            ],
            "rejection_reason": None,
        }

    if status == "declined":
        return {
            "subject": f"WPGU Song Request Update: {song_name}",
            "preheader": f"Your request for {song_name} was not approved.",
            "status_label": "Not Approved",
            "status_accent": "#F44336",
            "status_tint": "#FFCDD2",
            "headline": "Your song request was not approved",
            "body_paragraphs": [
                (
                    f'Thank you for submitting a request for "{song_name}" by '
                    f"{artist_name}."
                ),
                "We are unable to add it to the WPGU library at this time.",
            ],
            "rejection_reason": rejection_reason,
        }

    raise ValueError("Invalid status for song request email.")


def _render_song_request_email_html(
    content: dict, song_name: str, artist_name: str
) -> str:
    template = _EMAIL_ENV.get_template(SONG_REQUEST_EMAIL_TEMPLATE)
    return template.render(
        preheader=content["preheader"],
        status_label=content["status_label"],
        status_accent=content["status_accent"],
        status_tint=content["status_tint"],
        headline=content["headline"],
        body_paragraphs=content["body_paragraphs"],
        song_name=song_name,
        artist_name=artist_name,
        rejection_reason=content["rejection_reason"],
    )


def _render_song_request_email_text(
    content: dict, song_name: str, artist_name: str
) -> str:
    lines = ["Hi there!", ""]
    lines.extend(content["body_paragraphs"])
    lines.extend(["", f"Song: {song_name}", f"Artist: {artist_name}"])

    if content["rejection_reason"]:
        lines.extend(["", f"Reason: {content['rejection_reason']}"])

    lines.extend(["", "The WPGU Music Team"])
    return "\n".join(lines)


def _send_song_request_email(
    to_email: str,
    song_name: str,
    artist_name: str,
    status: str,
    rejection_reason: str | None = None,
) -> dict:
    if not to_email:
        return {"ok": False, "error": "No email provided"}

    try:
        content = _build_song_request_email_content(
            song_name=song_name,
            artist_name=artist_name,
            status=status,
            rejection_reason=rejection_reason,
        )
    except ValueError as exc:
        logger.error("Failed to build song request email content: %s", exc)
        return {"ok": False, "error": str(exc)}

    text_body = _render_song_request_email_text(content, song_name, artist_name)
    html_body = _render_song_request_email_html(content, song_name, artist_name)

    return send_gmail_message(
        to_email=to_email,
        subject=content["subject"],
        text_body=text_body,
        html_body=html_body,
        impersonated_sender=WPGU_IMPERSONATED_SENDER,
        from_header=WPGU_FROM_HEADER,
    )


def send_song_request_submission_email(
    to_email: str,
    song_name: str,
    artist_name: str,
) -> dict:
    """Send a submission confirmation email for an outside user's request."""

    return _send_song_request_email(
        to_email=to_email,
        song_name=song_name,
        artist_name=artist_name,
        status="submitted",
    )


def send_song_request_update_email(
    to_email: str,
    song_name: str,
    artist_name: str,
    status: str,
    rejection_reason: str | None = None,
) -> dict:
    """Send an approval or denial email for an outside user's request."""

    return _send_song_request_email(
        to_email=to_email,
        song_name=song_name,
        artist_name=artist_name,
        status=status,
        rejection_reason=rejection_reason,
    )
