import sqlite3

conn = sqlite3.connect("d:/DeepScribe/abyss_writer/abyss_writer.db")
cursor = conn.cursor()

print("=== PROJECTS ===")
cursor.execute("SELECT id, title, genre, status FROM projects")
for row in cursor.fetchall():
    print(row)

print("\n=== CHARACTERS ===")
cursor.execute("SELECT id, project_id, name FROM characters")
for row in cursor.fetchall():
    print(row)

conn.close()
