from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3
import csv
import os
import qrcode
import urllib.parse
import hashlib
import io
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-dev-secret-key-change-me')

HOST = os.getenv('APP_HOST', '0.0.0.0')
PORT = int(os.getenv('APP_PORT', 5000))
SERVER_DOMAIN = os.getenv('SERVER_NAME', f'127.0.0.1:{PORT}')

DB_FILE = "medicine.db"
QR_FOLDER = "static/qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret123')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash("🔒 Please log in first.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# DB connection
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Helper to compute verification batch hash for DPDP compliance (no PII logged)
def get_batch_hash(name, manufacturer, batch_no):
    data = f"{name}:{manufacturer}:{batch_no}"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

# Initialize DB if needed
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            name TEXT,
            manufacturer TEXT,
            batch_no TEXT,
            expiry_date TEXT,
            PRIMARY KEY(name, manufacturer, batch_no)
        )
    ''')
    # Verification logs table storing only cryptographic hashes (DPDP Act compliance)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_hash TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['user'] = USERNAME
            return redirect(url_for('admin'))
        else:
            flash("❌ Invalid credentials.")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("✅ Logged out successfully.")
    return redirect(url_for('login'))

# Admin (Protected)
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    message = ""
    if request.method == 'POST':
        name = request.form['name']
        manufacturer = request.form['manufacturer']
        batch_no = request.form['batch_no']
        expiry_date = request.form['expiry_date']

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO medicines (name, manufacturer, batch_no, expiry_date)
                VALUES (?, ?, ?, ?)
            """, (name, manufacturer, batch_no, expiry_date))
            conn.commit()

            encoded_name = urllib.parse.quote(name)
            encoded_manufacturer = urllib.parse.quote(manufacturer)
            encoded_batch = urllib.parse.quote(batch_no)
            qr_data = f"http://{SERVER_DOMAIN}/verify/{encoded_name}/{encoded_manufacturer}/{encoded_batch}"
            img = qrcode.make(qr_data)
            filename = f"{name.replace(' ', '_')}_{manufacturer.replace(' ', '_')}_{batch_no.replace(' ', '_')}.png"
            img.save(os.path.join(QR_FOLDER, filename))

            message = "✅ Medicine added and QR code generated."
        except sqlite3.IntegrityError:
            message = "⚠️ This record already exists!"
        finally:
            conn.close()
    return render_template("admin.html", message=message)

# Delete (Protected)
@app.route('/delete_medicine/<name>/<manufacturer>/<batch_no>', methods=['POST'])
@login_required
def delete_medicine(name, manufacturer, batch_no):
    decoded = (
        urllib.parse.unquote(name),
        urllib.parse.unquote(manufacturer),
        urllib.parse.unquote(batch_no),
    )
    conn = get_db_connection()
    conn.execute("DELETE FROM medicines WHERE name=? AND manufacturer=? AND batch_no=?", decoded)
    conn.commit()
    conn.close()

    filename = f"{decoded[0].replace(' ', '_')}_{decoded[1].replace(' ', '_')}_{decoded[2].replace(' ', '_')}.png"
    path = os.path.join(QR_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)

    return redirect(url_for('view_medicines'))

# Public View
@app.route('/view_medicines')
def view_medicines():
    conn = get_db_connection()
    medicines = conn.execute("SELECT * FROM medicines").fetchall()
    conn.close()
    return render_template("view_medicines.html", medicines=medicines)

# Dedicated CSV Export Endpoint
@app.route('/export_csv')
@login_required
def export_csv():
    conn = get_db_connection()
    rows = conn.execute("SELECT name, manufacturer, batch_no, expiry_date FROM medicines").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "manufacturer", "batch_no", "expiry_date"])
    for row in rows:
        writer.writerow([row["name"], row["manufacturer"], row["batch_no"], row["expiry_date"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=medicines_export.csv"}
    )

# QR Verify Route (Indian DPDP Act Compliant)
@app.route('/verify/<name>/<manufacturer>/<batch_no>')
def verify(name, manufacturer, batch_no):
    decoded_name = urllib.parse.unquote(name)
    decoded_mfr = urllib.parse.unquote(manufacturer)
    decoded_batch = urllib.parse.unquote(batch_no)

    # Log only SHA-256 hash of verification payload for compliance and minimal audit trail
    batch_hash = get_batch_hash(decoded_name, decoded_mfr, decoded_batch)
    conn = get_db_connection()
    conn.execute("INSERT INTO verification_logs (batch_hash) VALUES (?)", (batch_hash,))
    conn.commit()

    row = conn.execute("""
        SELECT * FROM medicines WHERE name=? AND manufacturer=? AND batch_no=?
    """, (decoded_name, decoded_mfr, decoded_batch)).fetchone()
    conn.close()

    if row:
        return render_template("medicine.html", name=row["name"], manufacturer=row["manufacturer"],
                               batch_no=row["batch_no"], expiry=row["expiry_date"])
    else:
        return "<h2>❌ Medicine not found!</h2>"

@app.route('/')
def home():
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(host=HOST, port=PORT, debug=True)