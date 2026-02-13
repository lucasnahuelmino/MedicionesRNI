import sqlite3

DB_PATH = "archivosdata/rni.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("PRAGMA table_info(mediciones_rni)")
columns = c.fetchall()
print("Columnas en mediciones_rni:")
for col in columns:
    print(col)
conn.close()
