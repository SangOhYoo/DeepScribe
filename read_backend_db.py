import sqlite3

try:
    conn = sqlite3.connect("backend/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in backend/database.db:", tables)
    
    # Check if there is a projects or similar table
    for (tname,) in tables:
        if "project" in tname.lower() or "character" in tname.lower():
            cursor.execute(f"SELECT * FROM {tname};")
            rows = cursor.fetchall()
            print(f"Table {tname} has {len(rows)} rows.")
            for row in rows[:5]:
                print("  ", row)
except Exception as e:
    print("Error:", e)
