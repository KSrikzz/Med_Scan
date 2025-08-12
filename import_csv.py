import sqlite3
import csv
import os

DB_FILE = "medicine.db"
CSV_FILE = "medicines.csv"

if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE medicines (
    name TEXT,
    manufacturer TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    PRIMARY KEY (name, manufacturer, batch_no)
)
""")

with open(CSV_FILE, "r") as file:
    reader = csv.reader(file)
    for row in reader:
        if len(row) == 4:
            try:
                cursor.execute("""
                    INSERT INTO medicines (name, manufacturer, batch_no, expiry_date)
                    VALUES (?, ?, ?, ?)
                """, row)
            except sqlite3.IntegrityError:
                print(f"⚠️ Duplicate skipped: {row}")
conn.commit()
conn.close()
print("✅ Data imported successfully!")