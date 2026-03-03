"""
Email Sender Tool — Send outreach emails via Gmail SMTP.

Ported directly from emailer.py.
"""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

from tools.base import BaseTool

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def is_configured() -> bool:
    """Check if Gmail credentials are set."""
    return bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)


def parse_email_text(email_text: str) -> dict:
    """Parse the agent's email output into subject + body."""
    subject = ""
    body = email_text.strip()

    match = re.match(r"^Subject:\s*(.+?)(?:\n\n|\n)", email_text.strip())
    if match:
        subject = match.group(1).strip()
        body = email_text.strip()[match.end():].strip()

    return {"subject": subject, "body": body}


def send_email(to_address: str, subject: str, body: str) -> dict:
    """Send a plain text email via Gmail SMTP SSL."""
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
    """Parse agent-generated email text and send it."""
    parsed = parse_email_text(email_text)
    result = send_email(to_address, parsed["subject"], parsed["body"])
    result["subject"] = parsed["subject"]
    return result


class EmailSenderTool(BaseTool):
    name = "send_email"
    description = "Send an email via Gmail SMTP. Requires Gmail credentials in .env."

    def _input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "to_address": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Email body text."},
            },
            "required": ["to_address", "subject", "body"],
        }

    def _execute(self, to_address: str = "", subject: str = "", body: str = "") -> str:
        if not to_address:
            return "Error: No recipient email provided."
        result = send_email(to_address, subject, body)
        if result["success"]:
            return result["message"]
        return f"Error: {result['error']}"
