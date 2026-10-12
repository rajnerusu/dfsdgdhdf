"""
app.py
------
Meedicoapp OP-Booking System - main Flask application.

Two parallel interfaces are exposed:
  1. Server-rendered web pages (Bootstrap 5) using Flask session auth.
  2. A JSON API under /api/* secured with JWT (Flask-JWT-Extended) + CORS,
     for mobile apps / SPA front-ends / integrations.

Run with:
    python app.py
"""

import os
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify
)
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)

import models
from models import User, Doctor, Appointment
from email_service import email_service
from config import Config

# --------------------------------------------------------------------------
# App factory / initialization
# --------------------------------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)

# Point the data-access layer at the real database file.
models.init_app(app.config["DATABASE_PATH"])

# JWT for the JSON API.
jwt = JWTManager(app)

# CORS only needs to apply to the JSON API surface.
CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)

# Email service.
email_service.init_app(app)

VALID_ROLES = ("patient", "doctor", "admin")


with app.app_context():
    models.init_db()
    models.seed_data(app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])


# --------------------------------------------------------------------------
# Helpers / decorators (session-based, for the HTML pages)
# --------------------------------------------------------------------------

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.get_by_id(user_id)


@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "app_name": "Meedicoapp", "config": app.config}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login", next=request.path))
            if user["role"] not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


admin_required = roles_required("admin")


# --------------------------------------------------------------------------
# Helpers / decorators (JWT-based, for the JSON API)
# --------------------------------------------------------------------------

def api_roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") not in roles:
                return jsonify(error="Forbidden: insufficient role"), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ==========================================================================
# WEB ROUTES (Bootstrap 5 server-rendered pages)
# ==========================================================================

@app.route("/")
def index():
    doctors = Doctor.list_all(active_only=True)
    return render_template("index.html", doctors=doctors)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Name, email and password are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif User.get_by_email(email):
            flash("An account with that email already exists.", "danger")
        else:
            user_id = User.create(name, email, password, phone, role="patient")
            email_service.send_welcome_email(email, name)
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.get_by_email(email)

        if not user or not User.verify_password(user, password):
            flash("Invalid email or password.", "danger")
        elif not user["is_active"]:
            flash("Your account has been deactivated. Contact the clinic admin.", "danger")
        else:
            session["user_id"] = user["id"]
            session["user_role"] = user["role"]
            session["user_name"] = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    appointments = Appointment.list_for_patient(user["id"])
    upcoming = [a for a in appointments if a["status"] in ("pending", "confirmed")]
    return render_template("dashboard.html", user=user, appointments=appointments, upcoming=upcoming)


@app.route("/book", methods=["GET", "POST"])
@roles_required("patient")
def book_appointment():
    doctors = Doctor.list_all(active_only=True)
    if request.method == "POST":
        doctor_id = request.form.get("doctor_id")
        appointment_date = request.form.get("appointment_date")
        appointment_time = request.form.get("appointment_time")
        reason = request.form.get("reason", "").strip()

        doctor = Doctor.get_by_id(doctor_id) if doctor_id else None
        if not doctor:
            flash("Please select a valid doctor.", "danger")
        elif not appointment_date or not appointment_time:
            flash("Please choose a date and time.", "danger")
        else:
            user = current_user()
            _, op_number = Appointment.create(
                user["id"], doctor_id, appointment_date, appointment_time, reason
            )
            email_service.send_booking_confirmation(
                user["email"], user["name"], doctor["name"],
                appointment_date, appointment_time, op_number,
            )
            flash(f"Appointment booked! Your OP number is {op_number}.", "success")
            return redirect(url_for("dashboard"))

    return render_template("book_appointment.html", doctors=doctors)


@app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    user = current_user()
    appt = Appointment.get_by_id(appointment_id)
    if not appt or (appt["patient_id"] != user["id"] and user["role"] != "admin"):
        flash("Appointment not found.", "danger")
    else:
        Appointment.update_status(appointment_id, "cancelled")
        email_service.send_status_update_email(
            appt["patient_email"], appt["patient_name"], appt["op_number"], "cancelled"
        )
        flash("Appointment cancelled.", "info")
    return redirect(request.referrer or url_for("dashboard"))


# --- Admin panel (role-based) --------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = Appointment.dashboard_stats()
    user_counts = User.count_by_role()
    recent_appointments = Appointment.list_all()[:8]
    return render_template(
        "admin_dashboard.html",
        stats=stats,
        user_counts=user_counts,
        recent_appointments=recent_appointments,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    role_filter = request.args.get("role") or None
    search = request.args.get("search") or None
    users = User.list_all(role=role_filter, search=search)
    return render_template("admin_users.html", users=users, role_filter=role_filter, search=search or "")


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_user(user_id):
    target = User.get_by_id(user_id)
    if not target:
        flash("User not found.", "danger")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role")
        is_active = request.form.get("is_active") == "on"

        if role not in VALID_ROLES:
            flash("Invalid role selected.", "danger")
        else:
            existing = User.get_by_email(email)
            if existing and existing["id"] != user_id:
                flash("That email is already used by another account.", "danger")
            else:
                User.update(user_id, name=name, email=email, phone=phone, role=role, is_active=is_active)
                flash("User updated successfully.", "success")
                return redirect(url_for("admin_users"))

    return render_template("admin_edit_user.html", target=target, roles=VALID_ROLES)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    admin = current_user()
    if user_id == admin["id"]:
        flash("You cannot delete your own admin account.", "danger")
    else:
        User.delete(user_id)
        flash("User deleted.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/appointments")
@admin_required
def admin_appointments():
    status_filter = request.args.get("status") or None
    appointments = Appointment.list_all(status=status_filter)
    return render_template("admin_appointments.html", appointments=appointments, status_filter=status_filter)


@app.route("/admin/appointments/<int:appointment_id>/status", methods=["POST"])
@admin_required
def admin_update_appointment_status(appointment_id):
    new_status = request.form.get("status")
    appt = Appointment.get_by_id(appointment_id)
    if not appt:
        flash("Appointment not found.", "danger")
    elif new_status not in ("pending", "confirmed", "cancelled", "completed"):
        flash("Invalid status.", "danger")
    else:
        Appointment.update_status(appointment_id, new_status)
        email_service.send_status_update_email(
            appt["patient_email"], appt["patient_name"], appt["op_number"], new_status
        )
        flash("Appointment status updated.", "success")
    return redirect(url_for("admin_appointments"))


@app.route("/admin/doctors", methods=["GET", "POST"])
@admin_required
def admin_doctors():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        department = request.form.get("department", "").strip()
        fee = request.form.get("fee") or 0
        available_days = request.form.get("available_days", "Mon-Sat")
        available_time = request.form.get("available_time", "09:00 - 17:00")

        if not name or not specialization:
            flash("Doctor name and specialization are required.", "danger")
        else:
            Doctor.create(name, specialization, department, float(fee), available_days, available_time)
            flash("Doctor added.", "success")
        return redirect(url_for("admin_doctors"))

    doctors = Doctor.list_all()
    return render_template("admin_doctors.html", doctors=doctors)


@app.route("/admin/doctors/<int:doctor_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_doctor(doctor_id):
    doctor = Doctor.get_by_id(doctor_id)
    if doctor:
        Doctor.update(doctor_id, is_active=0 if doctor["is_active"] else 1)
        flash("Doctor availability updated.", "success")
    return redirect(url_for("admin_doctors"))


@app.route("/admin/doctors/<int:doctor_id>/delete", methods=["POST"])
@admin_required
def admin_delete_doctor(doctor_id):
    Doctor.delete(doctor_id)
    flash("Doctor removed.", "info")
    return redirect(url_for("admin_doctors"))


# ==========================================================================
# JSON API (JWT + CORS) - /api/*
# ==========================================================================

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name"), data.get("email"), data.get("password")
    if not name or not email or not password:
        return jsonify(error="name, email and password are required"), 400
    if User.get_by_email(email):
        return jsonify(error="email already registered"), 409

    user_id = User.create(name, email, password, data.get("phone"), role="patient")
    email_service.send_welcome_email(email, name)
    return jsonify(message="registered", user_id=user_id), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email, password = data.get("email"), data.get("password")
    user = User.get_by_email(email or "")
    if not user or not User.verify_password(user, password or ""):
        return jsonify(error="invalid credentials"), 401
    if not user["is_active"]:
        return jsonify(error="account deactivated"), 403

    token = create_access_token(
        identity=str(user["id"]),
        additional_claims={"role": user["role"], "name": user["name"], "email": user["email"]},
    )
    return jsonify(access_token=token, role=user["role"], name=user["name"])


@app.route("/api/doctors", methods=["GET"])
def api_list_doctors():
    return jsonify(doctors=Doctor.list_all(active_only=True))


@app.route("/api/appointments", methods=["GET"])
@jwt_required()
def api_list_appointments():
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    if claims.get("role") == "admin":
        return jsonify(appointments=Appointment.list_all())
    return jsonify(appointments=Appointment.list_for_patient(user_id))


@app.route("/api/appointments", methods=["POST"])
@jwt_required()
def api_create_appointment():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    doctor_id = data.get("doctor_id")
    appointment_date = data.get("appointment_date")
    appointment_time = data.get("appointment_time")
    reason = data.get("reason", "")

    doctor = Doctor.get_by_id(doctor_id) if doctor_id else None
    if not doctor or not appointment_date or not appointment_time:
        return jsonify(error="doctor_id, appointment_date and appointment_time are required"), 400

    user = User.get_by_id(user_id)
    appt_id, op_number = Appointment.create(user_id, doctor_id, appointment_date, appointment_time, reason)
    email_service.send_booking_confirmation(
        user["email"], user["name"], doctor["name"], appointment_date, appointment_time, op_number
    )
    return jsonify(message="booked", appointment_id=appt_id, op_number=op_number), 201


@app.route("/api/appointments/<int:appointment_id>/cancel", methods=["POST"])
@jwt_required()
def api_cancel_appointment(appointment_id):
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    appt = Appointment.get_by_id(appointment_id)
    if not appt:
        return jsonify(error="not found"), 404
    if appt["patient_id"] != user_id and claims.get("role") != "admin":
        return jsonify(error="forbidden"), 403

    Appointment.update_status(appointment_id, "cancelled")
    email_service.send_status_update_email(
        appt["patient_email"], appt["patient_name"], appt["op_number"], "cancelled"
    )
    return jsonify(message="cancelled")


# --- Admin-only JSON API: manage users (update / delete), dashboard -------

@app.route("/api/admin/users", methods=["GET"])
@api_roles_required("admin")
def api_admin_list_users():
    return jsonify(users=User.list_all(role=request.args.get("role"), search=request.args.get("search")))


@app.route("/api/admin/users/<int:user_id>", methods=["PUT", "PATCH"])
@api_roles_required("admin")
def api_admin_update_user(user_id):
    data = request.get_json(silent=True) or {}
    if data.get("role") and data["role"] not in VALID_ROLES:
        return jsonify(error="invalid role"), 400
    updated = User.update(
        user_id,
        name=data.get("name"),
        email=data.get("email"),
        phone=data.get("phone"),
        role=data.get("role"),
        is_active=data.get("is_active"),
    )
    if not updated:
        return jsonify(error="user not found or no changes supplied"), 404
    return jsonify(message="updated")


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@api_roles_required("admin")
def api_admin_delete_user(user_id):
    requester_id = int(get_jwt_identity())
    if user_id == requester_id:
        return jsonify(error="cannot delete your own account"), 400
    if not User.delete(user_id):
        return jsonify(error="user not found"), 404
    return jsonify(message="deleted")


@app.route("/api/admin/dashboard", methods=["GET"])
@api_roles_required("admin")
def api_admin_dashboard():
    return jsonify(
        appointment_stats=Appointment.dashboard_stats(),
        user_counts=User.count_by_role(),
    )


# --------------------------------------------------------------------------
# JWT error handlers -> clean JSON responses
# --------------------------------------------------------------------------

@jwt.unauthorized_loader
def unauthorized_callback(reason):
    return jsonify(error="missing or invalid token", detail=reason), 401


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify(error="token expired"), 401


@jwt.invalid_token_loader
def invalid_token_callback(reason):
    return jsonify(error="invalid token", detail=reason), 422


# --------------------------------------------------------------------------
# Error pages
# --------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error="not found"), 404
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    if request.path.startswith("/api/"):
        return jsonify(error="forbidden"), 403
    flash("You do not have permission to do that.", "danger")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
