import os
import smtplib

from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

MAIL_ADDRESS = os.getenv("MAIL_ADDRESS")
MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")


def send_email(recipient, subject, body):
    if not MAIL_ADDRESS or not MAIL_APP_PASSWORD:
        raise ValueError("Email credentials are missing from the .env file.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = MAIL_ADDRESS
    message["To"] = recipient
    message.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(MAIL_ADDRESS, MAIL_APP_PASSWORD)
        server.send_message(message)


def send_test_email(recipient):
    send_email(
        recipient,
        "WS1 Attendance System - Test Email",
        """
Hello!

This is a test email from the WS1 Attendance Management System.

Your Gmail SMTP configuration is working.

WS1 Attendance Management System
""",
    )
