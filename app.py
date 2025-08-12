from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import csv
import os
import qrcode
import urllib.parse
from functools import wraps

app = Flask(__name__)
app.secret_key = 'k9ZjJkLZ7BzQipmW5HKdAfPqxT13V8EzrYl6tW2cB0E=' #Change if needed

IP = ""
Port = ""
DB_FILE = "medicine.db"
CSV_FILE = "medicines.csv"
QR_FOLDER = "static/qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

USERNAME = 'admin'
PASSWORD = 'secret123'

#Login
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash("🔒 Please log in first.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

#DB connection
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

#Sync CSV
def sync_csv_from_db():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM medicines").fetchall()
    conn.close()
    with open(CSV_FILE, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "manufacturer", "batch_no", "expiry_date"])
        for row in rows:
            writer.writerow([row["name"], row["manufacturer"], row["batch_no"], row["expiry_date"]])

#Initialize DB if needed
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

#Admin (Protected)
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

            with open(CSV_FILE, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([name, manufacturer, batch_no, expiry_date])

            encoded_name = urllib.parse.quote(name)
            encoded_manufacturer = urllib.parse.quote(manufacturer)
            encoded_batch = urllib.parse.quote(batch_no)
            qr_data = f"http://{IP}:{Port}/verify/{encoded_name}/{encoded_manufacturer}/{encoded_batch}"
            img = qrcode.make(qr_data)
            filename = f"{name.replace(' ', '_')}_{manufacturer.replace(' ', '_')}_{batch_no.replace(' ', '_')}.png"
            img.save(os.path.join(QR_FOLDER, filename))

            message = "✅ Medicine added and QR code generated."
        except sqlite3.IntegrityError:
            message = "⚠️ This record already exists!"
        finally:
            conn.close()
    return render_template("admin.html", message=message)

#Delete (Protected)
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
    sync_csv_from_db()

    filename = f"{decoded[0].replace(' ', '_')}_{decoded[1].replace(' ', '_')}_{decoded[2].replace(' ', '_')}.png"
    path = os.path.join(QR_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)

    return redirect(url_for('view_medicines'))

#Public View
@app.route('/view_medicines')
def view_medicines():
    sync_csv_from_db()
    conn = get_db_connection()
    medicines = conn.execute("SELECT * FROM medicines").fetchall()
    conn.close()
    return render_template("view_medicines.html", medicines=medicines)

#QR Verify Route
@app.route('/verify/<name>/<manufacturer>/<batch_no>')
def verify(name, manufacturer, batch_no):
    decoded = (
        urllib.parse.unquote(name),
        urllib.parse.unquote(manufacturer),
        urllib.parse.unquote(batch_no),
    )
    conn = get_db_connection()
    row = conn.execute("""
        SELECT * FROM medicines WHERE name=? AND manufacturer=? AND batch_no=?
    """, decoded).fetchone()
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
    app.run(host=IP, port=Port, debug=True)