import sqlite3

try:
    conn = sqlite3.connect("d:/DeepScribe/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in database.db:")
    for t in tables:
        print("-", t[0])
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t[0]};")
            print("  Count:", cursor.fetchone()[0])
        except Exception as e:
            print("  Error counting:", e)
    conn.close()
except Exception as e:
    print("Error opening database.db:", e)
