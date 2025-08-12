import sqlite3
import qrcode
import os
import urllib.parse

DB_FILE = "medicine.db"
QR_FOLDER = "static/qr_codes"
LOCAL_IP = ""
PORT = ""

os.makedirs(QR_FOLDER, exist_ok=True)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT name, manufacturer, batch_no FROM medicines")
records = cursor.fetchall()

for name, manufacturer, batch_no in records:
    encoded_name = urllib.parse.quote(name)
    encoded_manufacturer = urllib.parse.quote(manufacturer)
    encoded_batch = urllib.parse.quote(batch_no)

    file_name = f"{name.replace(' ', '_')}_{manufacturer.replace(' ', '_')}_{batch_no}.png"
    file_path = os.path.join(QR_FOLDER, file_name)

    if os.path.exists(file_path):
        print(f"⚠️ Skipping existing QR: {file_name}")
        continue

    qr_url = f"http://{LOCAL_IP}:{PORT}/verify/{encoded_name}/{encoded_manufacturer}/{encoded_batch}"
    img = qrcode.make(qr_url)
    img.save(file_path)
    print(f"✅ Generated QR: {file_path} -> {qr_url}")

conn.close()