"""
email_service.py
-----------------
Lightweight SMTP email service for Meedicoapp.

Deliberately dependency-free (uses smtplib + email.mime from the standard
library) so it works whether or not Flask-Mail is installed. If SMTP
credentials are not configured, emails are printed to the console instead
of failing the request - useful for local development/demo.
"""

import smtplib
import ssl
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailService:
    def __init__(self, app=None):
        self.app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

    def _config(self, key, default=None):
        return self.app.config.get(key, default)

    def _should_suppress(self):
        setting = self._config("MAIL_SUPPRESS_SEND", "auto")
        if setting == "auto":
            return not (self._config("MAIL_USERNAME") and self._config("MAIL_PASSWORD"))
        return str(setting).lower() == "true"

    def send(self, to_email, subject, html_body, text_body=None, async_send=True):
        """Send an email. Falls back to console logging if SMTP isn't configured."""
        if self._should_suppress():
            print("=" * 70)
            print(f"[EMAIL - SUPPRESSED / CONSOLE MODE] To: {to_email}")
            print(f"Subject: {subject}")
            print(text_body or html_body)
            print("=" * 70)
            return True

        def _send():
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self._config("MAIL_DEFAULT_SENDER")
                msg["To"] = to_email
                if text_body:
                    msg.attach(MIMEText(text_body, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                context = ssl.create_default_context()
                with smtplib.SMTP(self._config("MAIL_SERVER"), self._config("MAIL_PORT")) as server:
                    if self._config("MAIL_USE_TLS"):
                        server.starttls(context=context)
                    server.login(self._config("MAIL_USERNAME"), self._config("MAIL_PASSWORD"))
                    server.sendmail(self._config("MAIL_DEFAULT_SENDER"), to_email, msg.as_string())
            except Exception as exc:  # noqa: BLE001
                print(f"[EMAIL ERROR] Could not send email to {to_email}: {exc}")

        if async_send:
            threading.Thread(target=_send, daemon=True).start()
        else:
            _send()
        return True

    # ---- Pre-built templates for OP-Booking events ----------------------

    def send_welcome_email(self, to_email, name):
        subject = "Welcome to Meedicoapp"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto">
          <h2 style="color:#0d6efd">Welcome to Meedicoapp, {name}!</h2>
          <p>Your account has been created successfully. You can now log in and
          book OP appointments with our doctors in just a few clicks.</p>
          <p style="color:#6c757d;font-size:12px">This is an automated message from Meedicoapp.</p>
        </div>
        """
        self.send(to_email, subject, html)

    def send_booking_confirmation(self, to_email, name, doctor_name, date, time, op_number):
        subject = f"Appointment Booked - {op_number}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto">
          <h2 style="color:#198754">Your OP appointment is booked!</h2>
          <p>Hi {name}, your appointment has been scheduled.</p>
          <table style="border-collapse:collapse;width:100%">
            <tr><td style="padding:6px 0;color:#6c757d">OP Number</td><td><b>{op_number}</b></td></tr>
            <tr><td style="padding:6px 0;color:#6c757d">Doctor</td><td>{doctor_name}</td></tr>
            <tr><td style="padding:6px 0;color:#6c757d">Date</td><td>{date}</td></tr>
            <tr><td style="padding:6px 0;color:#6c757d">Time</td><td>{time}</td></tr>
          </table>
          <p>Please arrive 15 minutes early with your OP number.</p>
          <p style="color:#6c757d;font-size:12px">This is an automated message from Meedicoapp.</p>
        </div>
        """
        self.send(to_email, subject, html)

    def send_status_update_email(self, to_email, name, op_number, status):
        subject = f"Appointment {status.title()} - {op_number}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto">
          <h2 style="color:#0d6efd">Appointment update</h2>
          <p>Hi {name}, your appointment <b>{op_number}</b> status has been updated to:
          <b>{status.upper()}</b>.</p>
          <p style="color:#6c757d;font-size:12px">This is an automated message from Meedicoapp.</p>
        </div>
        """
        self.send(to_email, subject, html)


email_service = EmailService()
