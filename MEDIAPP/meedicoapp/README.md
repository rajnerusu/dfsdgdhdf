# Meedicoapp — OP Booking System

A full-stack Flask application for booking outpatient (OP) hospital
appointments, with a role-based admin panel, JWT-secured JSON API, CORS,
and email notifications.

## Features

- **Patient portal**: register/login, browse doctors, book OP appointments,
  view/cancel appointments, receive email confirmations.
- **Role-based Admin Panel** (`/admin`):
  - Dashboard with live stats (total/pending/confirmed appointments, user counts)
  - **Manage users** — update details/role/active-status, and **delete** users
  - Manage doctors (add / activate / deactivate / delete)
  - Manage appointments (filter by status, update status → triggers email)
- **JSON API** under `/api/*`, secured with **JWT** (Flask-JWT-Extended) and
  **CORS** enabled, so a mobile app or SPA can talk to the same backend.
- **Email service** (`email_service.py`) — SMTP-based; if no SMTP
  credentials are configured it safely falls back to printing emails to the
  console, so the app runs out of the box with zero setup.
- **SQLite** database accessed via raw `sqlite3` cursors in `models.py`
  (no ORM) — schema, seed data, and CRUD are all explicit SQL.
- **Bootstrap 5** UI (via CDN) — responsive, no build step required.

## Project structure

```
meedicoapp/
├── app.py                 # Flask app, all routes (web + /api JSON), JWT, CORS
├── models.py               # SQLite schema + User/Doctor/Appointment data access (raw cursors)
├── email_service.py         # SMTP email service with console fallback
├── config.py                 # Central configuration (env-driven)
├── requirements.txt
├── .env.example
├── templates/
│   ├── base.html             # Shared Bootstrap 5 layout, navbar, flash messages
│   ├── index.html            # Public homepage / doctor listing
│   ├── login.html / register.html
│   ├── dashboard.html         # Patient dashboard
│   ├── book_appointment.html
│   ├── admin_dashboard.html   # Admin stats
│   ├── admin_users.html / admin_edit_user.html   # Role-based user management
│   ├── admin_appointments.html
│   ├── admin_doctors.html
│   ├── _admin_sidebar.html    # Shared admin nav
│   └── 404.html
└── static/
    ├── css/style.css
    └── js/main.js
```

## Setup

```bash
cd meedicoapp
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app runs at **http://localhost:5000**. On first run it automatically:
- creates `meedicoapp.db` and all tables,
- seeds a default **admin** account and 4 sample doctors.

### Default admin login
```
Email:    admin@meedicoapp.com
Password: Admin@123
```
(Change these via the `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment
variables before first run in production.)

## Configuration

Copy `.env.example` to `.env` and adjust as needed (SMTP credentials, JWT
secret, CORS origins, etc.). To auto-load it, `pip install python-dotenv`
(already in requirements.txt) and add near the top of `app.py`:

```python
from dotenv import load_dotenv
load_dotenv()
```

If `MAIL_USERNAME` / `MAIL_PASSWORD` are left blank, emails are printed to
the console instead of sent — handy for local demos.

## JSON API quick reference

| Method | Endpoint                          | Auth         | Description                        |
|--------|------------------------------------|--------------|-------------------------------------|
| POST   | `/api/auth/register`               | none         | Create a patient account            |
| POST   | `/api/auth/login`                  | none         | Returns a JWT access token          |
| GET    | `/api/doctors`                     | none         | List active doctors                 |
| GET    | `/api/appointments`                | JWT          | List own (or all, if admin) appts   |
| POST   | `/api/appointments`                | JWT          | Book an appointment                 |
| POST   | `/api/appointments/<id>/cancel`    | JWT          | Cancel own (or any, if admin) appt  |
| GET    | `/api/admin/users`                 | JWT (admin)  | List all users                      |
| PUT    | `/api/admin/users/<id>`            | JWT (admin)  | **Update** a user                   |
| DELETE | `/api/admin/users/<id>`            | JWT (admin)  | **Delete** a user                   |
| GET    | `/api/admin/dashboard`             | JWT (admin)  | Aggregate stats                     |

Example:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@meedicoapp.com","password":"Admin@123"}'

curl http://localhost:5000/api/admin/users \
  -H "Authorization: Bearer <access_token>"
```

## Notes on security for production

- Change `SECRET_KEY` and `JWT_SECRET_KEY` to strong random values.
- Set `CORS_ORIGINS` to your actual front-end domain(s) instead of `*`.
- Put the app behind HTTPS and a real WSGI server (gunicorn/uwsgi + nginx).
- Consider moving passwords/session cookies to `Secure`/`HttpOnly` settings
  and enabling rate limiting on `/api/auth/login`.
