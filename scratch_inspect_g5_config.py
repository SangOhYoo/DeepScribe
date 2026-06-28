import pymysql
import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    conn = pymysql.connect(host="127.0.0.1", user="root", password="gmlakddl", database="g5")
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT * FROM g5_config LIMIT 1")
    row = cur.fetchone()
    if row:
        print("Config row fields:")
        for k, v in sorted(row.items()):
            if v:
                print(f"  {k}: {v}")
    else:
        print("No rows in g5_config")
except Exception as e:
    print("Error:", e)
