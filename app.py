import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash


app = Flask(__name__)
app.secret_key = 'medicoapp_super_secret_key'
db_name = "database.db"


def get_connect():
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connect()
    cursor = conn.cursor()
   
    # Table 1: Doctors
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors(
            did INTEGER PRIMARY KEY AUTOINCREMENT,
            dname TEXT NOT NULL,
            contact INTEGER NOT NULL UNIQUE,
            wardno INTEGER NOT NULL DEFAULT 0,
            specialization TEXT NOT NULL
        )
    ''')
   
    # Table 2: OP Bookings with Doctor Foreign Key Link
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS op(
            pid INTEGER PRIMARY KEY AUTOINCREMENT,
            pname TEXT NOT NULL,
            age INTEGER NOT NULL,
            email TEXT NOT NULL,
            aadhaar TEXT NOT NULL,
            disease TEXT NOT NULL,
            since TEXT NOT NULL,
            symptoms TEXT,
            did INTEGER NOT NULL,
            SlDate TEXT NOT NULL,
            SlTime TEXT NOT NULL,
            FOREIGN KEY (did) REFERENCES doctors (did) ON DELETE CASCADE
        )
    ''')
   
    # Seed Initial Doctors if table is empty
    cursor.execute('SELECT COUNT(*) FROM doctors')
    if cursor.fetchone()[0] == 0:
        initial_doctors = [
            ('Dr. Sarah Jenkins', 9876543210, 101, 'General Surgery'),
            ('Dr. Rajesh Kumar', 9876543211, 204, 'Critical Care & Accident'),
            ('Dr. Emily Chen', 9876543212, 302, 'Neurology'),
            ('Dr. Michael Brown', 9876543213, 105, 'ENT Specialist'),
            ('Dr. Priya Nair', 9876543214, 401, 'Pediatric Care')
        ]
        cursor.executemany('''
            INSERT INTO doctors (dname, contact, wardno, specialization)
            VALUES (?, ?, ?, ?)
        ''', initial_doctors)
        conn.commit()
   
    conn.close()


# Home Page Route (Matching Wireframe)
@app.route('/')
def home():
    return render_template('home.html')


# OP Portal Dashboard Route
@app.route('/op')
def op():
    conn = get_connect()
    cursor = conn.cursor()
   
    # Fetch doctors for the dropdown
    cursor.execute('SELECT did, dname, specialization FROM doctors')
    doctors = cursor.fetchall()
   
    # Fetch existing bookings joined with doctor details
    cursor.execute('''
        SELECT op.*, doctors.dname, doctors.specialization
        FROM op
        JOIN doctors ON op.did = doctors.did
        ORDER BY op.pid DESC
    ''')
    bookings = cursor.fetchall()
    conn.close()
   
    return render_template('op_booking.html', doctors=doctors, bookings=bookings)


# Add / Update OP Booking Route
@app.route('/book_op', methods=['POST'])
def book_op():
    pid = request.form.get('bookingId')
    pname = request.form.get('patientName')
    age = request.form.get('age')
    email = request.form.get('email')
    aadhaar = request.form.get('aadhar')
    disease = request.form.get('disease')
    since = request.form.get('sufferedSince')
    symptoms = request.form.get('symptoms')
    did = request.form.get('did')
    sl_date = request.form.get('bookingDate')
    sl_time = request.form.get('bookingTime')


    try:
        conn = get_connect()
        cursor = conn.cursor()
       
        if pid:
            # Update Existing Record
            cursor.execute('''
                UPDATE op
                SET pname=?, age=?, email=?, aadhaar=?, disease=?, since=?, symptoms=?, did=?, SlDate=?, SlTime=?
                WHERE pid=?
            ''', (pname, age, email, aadhaar, disease, since, symptoms, did, sl_date, sl_time, pid))
            flash('OP Booking record updated successfully!', 'success')
        else:
            # Insert New Booking Record
            cursor.execute('''
                INSERT INTO op (pname, age, email, aadhaar, disease, since, symptoms, did, SlDate, SlTime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (pname, age, email, aadhaar, disease, since, symptoms, did, sl_date, sl_time))
            flash('New OP Registration created successfully!', 'success')
           
        conn.commit()
        conn.close()
    except sqlite3.Error as err:
        flash(f'Database operation failed: {str(err)}', 'danger')
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'danger')


    return redirect(url_for('op'))


# Delete OP Booking Route
@app.route('/delete_op/<int:pid>', methods=['POST'])
def delete_op(pid):
    try:
        conn = get_connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM op WHERE pid = ?', (pid,))
        conn.commit()
        conn.close()
        flash('OP Booking record deleted successfully.', 'warning')
    except sqlite3.Error as err:
        flash(f'Failed to delete record: {str(err)}', 'danger')
       
    return redirect(url_for('op'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=3500)
