"""Fallback exporter: dumps every table in northlight.db to CSV for Power BI
Get Data > Folder/Text-CSV, in case you don't want to set up a SQLite ODBC driver."""
import sqlite3, csv, os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "northlight.db")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "csv_export")
os.makedirs(OUT_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [r[0] for r in cur.fetchall()]

for table in tables:
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(os.path.join(OUT_DIR, f"{table}.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f"{table}: {len(rows):,} rows")

conn.close()
