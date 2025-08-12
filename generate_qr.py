import sqlite3
import qrcode
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

DB_FILE = "medicine.db"
QR_FOLDER = "static/qr_codes"
HOST = os.getenv('APP_HOST', '0.0.0.0')
PORT = os.getenv('APP_PORT', '5000')
SERVER_DOMAIN = os.getenv('SERVER_NAME', f'127.0.0.1:{PORT}')

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

    qr_url = f"http://{SERVER_DOMAIN}/verify/{encoded_name}/{encoded_manufacturer}/{encoded_batch}"
    img = qrcode.make(qr_url)
    img.save(file_path)
    print(f"✅ Generated QR: {file_path} -> {qr_url}")

conn.close()