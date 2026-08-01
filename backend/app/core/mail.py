# app/core/mail.py

import os
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def generate_otp() -> str:
    """Generates a 6-digit numeric OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp: str, full_name: str):
    """Sends a real OTP verification email via Gmail SMTP."""

    subject = "PriceGuard - Verify Your Email"
    body = f"""
Hi {full_name},

Thank you for signing up for PriceGuard.

Your verification code is: {otp}

This code will expire in 10 minutes. If you did not request this, please ignore this email.

- PriceGuard Team
"""

    message = MIMEMultipart()
    message["From"] = EMAIL_SENDER
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False