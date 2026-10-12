"""
models.py
---------
Data-access layer for the Meedicoapp OP-Booking system.

No ORM is used here on purpose: every model is a thin wrapper around raw
sqlite3 cursors/queries so the SQL is fully visible and easy to audit.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_PATH = "meedicoapp.db"


def init_app(database_path: str):
    """Called once from app.py to point every model at the real db file."""
    global DATABASE_PATH
    DATABASE_PATH = database_path


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_cursor(commit=False):
    """Yield a cursor, optionally committing + always closing the connection."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    finally:
        conn.close()


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    phone           TEXT,
    role            TEXT NOT NULL DEFAULT 'patient'
                        CHECK (role IN ('patient', 'doctor', 'admin')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER UNIQUE,
    name            TEXT NOT NULL,
    specialization  TEXT NOT NULL,
    department      TEXT,
    fee             REAL NOT NULL DEFAULT 0,
    available_days  TEXT DEFAULT 'Mon-Sat',
    available_time  TEXT DEFAULT '09:00 - 17:00',
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id          INTEGER NOT NULL,
    doctor_id           INTEGER NOT NULL,
    appointment_date    TEXT NOT NULL,
    appointment_time    TEXT NOT NULL,
    reason              TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
    op_number           TEXT UNIQUE,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments (patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments (doctor_id);
"""


def init_db():
    """Create tables (idempotent) - safe to call on every app start."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def seed_data(admin_email, admin_password):
    """Insert a default admin + a couple of sample doctors, only if empty."""
    now = datetime.utcnow().isoformat()
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT COUNT(*) as c FROM users")
        if cur.fetchone()["c"] == 0:
            cur.execute(
                """INSERT INTO users (name, email, password_hash, phone, role, is_active, created_at)
                   VALUES (?, ?, ?, ?, 'admin', 1, ?)""",
                ("Site Administrator", admin_email, generate_password_hash(admin_password), "0000000000", now),
            )

        cur.execute("SELECT COUNT(*) as c FROM doctors")
        if cur.fetchone()["c"] == 0:
            sample_doctors = [
                ("Dr. Ananya Rao", "General Medicine", "OPD-1", 300, "Mon-Sat", "09:00 - 13:00"),
                ("Dr. Kiran Mehta", "Cardiology", "OPD-2", 700, "Mon-Fri", "10:00 - 16:00"),
                ("Dr. Sara Thomas", "Pediatrics", "OPD-3", 400, "Mon-Sat", "09:00 - 12:00"),
                ("Dr. Vikram Singh", "Orthopedics", "OPD-4", 600, "Tue-Sat", "11:00 - 17:00"),
            ]
            for d in sample_doctors:
                cur.execute(
                    """INSERT INTO doctors
                       (name, specialization, department, fee, available_days, available_time, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                    (*d, now),
                )


# --------------------------------------------------------------------------
# User model
# --------------------------------------------------------------------------

class User:
    @staticmethod
    def create(name, email, password, phone=None, role="patient"):
        now = datetime.utcnow().isoformat()
        password_hash = generate_password_hash(password)
        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO users (name, email, password_hash, phone, role, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (name, email.lower().strip(), password_hash, phone, role, now),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(user_id):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return row_to_dict(cur.fetchone())

    @staticmethod
    def get_by_email(email):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
            return row_to_dict(cur.fetchone())

    @staticmethod
    def verify_password(user_row, password):
        return check_password_hash(user_row["password_hash"], password)

    @staticmethod
    def list_all(role=None, search=None):
        query = "SELECT id, name, email, phone, role, is_active, created_at FROM users WHERE 1=1"
        params = []
        if role:
            query += " AND role = ?"
            params.append(role)
        if search:
            query += " AND (name LIKE ? OR email LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])
        query += " ORDER BY created_at DESC"
        with get_cursor() as cur:
            cur.execute(query, params)
            return rows_to_list(cur.fetchall())

    @staticmethod
    def update(user_id, name=None, email=None, phone=None, role=None, is_active=None):
        fields, params = [], []
        if name is not None:
            fields.append("name = ?"); params.append(name)
        if email is not None:
            fields.append("email = ?"); params.append(email.lower().strip())
        if phone is not None:
            fields.append("phone = ?"); params.append(phone)
        if role is not None:
            fields.append("role = ?"); params.append(role)
        if is_active is not None:
            fields.append("is_active = ?"); params.append(1 if is_active else 0)
        if not fields:
            return False
        params.append(user_id)
        with get_cursor(commit=True) as cur:
            cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
            return cur.rowcount > 0

    @staticmethod
    def update_password(user_id, new_password):
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), user_id),
            )
            return cur.rowcount > 0

    @staticmethod
    def delete(user_id):
        """Deletes a user. Their appointments cascade-delete with them."""
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cur.rowcount > 0

    @staticmethod
    def count_by_role():
        with get_cursor() as cur:
            cur.execute("SELECT role, COUNT(*) as c FROM users GROUP BY role")
            return {r["role"]: r["c"] for r in cur.fetchall()}


# --------------------------------------------------------------------------
# Doctor model
# --------------------------------------------------------------------------

class Doctor:
    @staticmethod
    def create(name, specialization, department=None, fee=0, available_days="Mon-Sat",
               available_time="09:00 - 17:00", user_id=None):
        now = datetime.utcnow().isoformat()
        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO doctors
                   (user_id, name, specialization, department, fee, available_days, available_time,
                    is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (user_id, name, specialization, department, fee, available_days, available_time, now),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(doctor_id):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
            return row_to_dict(cur.fetchone())

    @staticmethod
    def list_all(active_only=False):
        query = "SELECT * FROM doctors"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name ASC"
        with get_cursor() as cur:
            cur.execute(query)
            return rows_to_list(cur.fetchall())

    @staticmethod
    def update(doctor_id, **fields):
        allowed = {"name", "specialization", "department", "fee", "available_days",
                   "available_time", "is_active"}
        set_clauses, params = [], []
        for key, value in fields.items():
            if key in allowed and value is not None:
                set_clauses.append(f"{key} = ?")
                params.append(value)
        if not set_clauses:
            return False
        params.append(doctor_id)
        with get_cursor(commit=True) as cur:
            cur.execute(f"UPDATE doctors SET {', '.join(set_clauses)} WHERE id = ?", params)
            return cur.rowcount > 0

    @staticmethod
    def delete(doctor_id):
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
            return cur.rowcount > 0


# --------------------------------------------------------------------------
# Appointment model
# --------------------------------------------------------------------------

class Appointment:
    @staticmethod
    def _generate_op_number():
        return "OP" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

    @staticmethod
    def create(patient_id, doctor_id, appointment_date, appointment_time, reason=""):
        now = datetime.utcnow().isoformat()
        op_number = Appointment._generate_op_number()
        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO appointments
                   (patient_id, doctor_id, appointment_date, appointment_time, reason,
                    status, op_number, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (patient_id, doctor_id, appointment_date, appointment_time, reason, op_number, now),
            )
            return cur.lastrowid, op_number

    @staticmethod
    def get_by_id(appointment_id):
        query = """
            SELECT a.*, u.name AS patient_name, u.email AS patient_email,
                   d.name AS doctor_name, d.specialization
            FROM appointments a
            JOIN users u ON u.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id
            WHERE a.id = ?
        """
        with get_cursor() as cur:
            cur.execute(query, (appointment_id,))
            return row_to_dict(cur.fetchone())

    @staticmethod
    def list_for_patient(patient_id):
        query = """
            SELECT a.*, d.name AS doctor_name, d.specialization
            FROM appointments a
            JOIN doctors d ON d.id = a.doctor_id
            WHERE a.patient_id = ?
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """
        with get_cursor() as cur:
            cur.execute(query, (patient_id,))
            return rows_to_list(cur.fetchall())

    @staticmethod
    def list_all(status=None):
        query = """
            SELECT a.*, u.name AS patient_name, u.email AS patient_email,
                   d.name AS doctor_name, d.specialization
            FROM appointments a
            JOIN users u ON u.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
        with get_cursor() as cur:
            cur.execute(query, params)
            return rows_to_list(cur.fetchall())

    @staticmethod
    def update_status(appointment_id, status):
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
            return cur.rowcount > 0

    @staticmethod
    def delete(appointment_id):
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
            return cur.rowcount > 0

    @staticmethod
    def dashboard_stats():
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM appointments")
            total = cur.fetchone()["c"]
            cur.execute("SELECT status, COUNT(*) as c FROM appointments GROUP BY status")
            by_status = {r["status"]: r["c"] for r in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) as c FROM appointments WHERE appointment_date = date('now')"
            )
            today = cur.fetchone()["c"]
        return {"total": total, "by_status": by_status, "today": today}
