import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Central configuration for the Meedicoapp OP-Booking system."""

    # --- Core / security ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "meedicoapp-dev-secret-change-me")

    # --- Database ---
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(basedir, "meedicoapp.db")
    )

    # --- JWT (Flask-JWT-Extended) used for the JSON /api/* endpoints ---
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "meedicoapp-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # --- CORS ---
    # Comma separated list of origins allowed to call the /api/* endpoints.
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # --- Email service (SMTP) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "Meedicoapp <no-reply@meedicoapp.local>"
    )
    # When True (or when credentials are missing) emails are printed to the
    # console instead of actually being sent - handy for local development.
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "auto")

    # --- App / seed data ---
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@meedicoapp.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
