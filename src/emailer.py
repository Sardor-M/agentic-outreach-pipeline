"""
Gmail SMTP Sender — Send cold outreach emails via Gmail

Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env
(Use a Google App Password, NOT your regular Gmail password)
"""

import os
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def is_configured() -> bool:
    """Check if Gmail credentials are set."""
    return bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)


def parse_email_text(email_text: str) -> dict:
    """
    Parse the agent's email output into subject + body.

    Expected format:
        Subject: ...

        [body text]
    """
    subject = ""
    body = email_text.strip()

    # Extract subject line
    match = re.match(r"^Subject:\s*(.+?)(?:\n\n|\n)", email_text.strip())
    if match:
        subject = match.group(1).strip()
        # Body is everything after "Subject: ...\n\n"
        body = email_text.strip()[match.end():].strip()

    return {"subject": subject, "body": body}


def send_email(to_address: str, subject: str, body: str) -> dict:
    """
    Send a plain text email via Gmail SMTP SSL.

    Returns dict with 'success' bool and 'message' or 'error'.
    """
    if not is_configured():
        return {
            "success": False,
            "error": "Gmail not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env",
        }

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_address, msg.as_string())
        return {"success": True, "message": f"Email sent to {to_address}"}
    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "error": "Gmail authentication failed. Check GMAIL_APP_PASSWORD (must be an App Password).",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_outreach_email(to_address: str, email_text: str) -> dict:
    """
    Parse agent-generated email text and send it.

    Args:
        to_address: Recipient email
        email_text: Raw email text from the Cold Email Writer agent

    Returns:
        dict with 'success', 'subject', and 'message' or 'error'
    """
    parsed = parse_email_text(email_text)
    result = send_email(to_address, parsed["subject"], parsed["body"])
    result["subject"] = parsed["subject"]
    return result
