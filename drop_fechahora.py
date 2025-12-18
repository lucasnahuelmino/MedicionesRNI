import sqlite3

conn = sqlite3.connect("archivosdata/rni.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(mediciones_rni)")
cols = [r[1] for r in cur.fetchall()]
print("Antes:", cols)

if "FechaHora" in cols:
    cur.execute("ALTER TABLE mediciones_rni DROP COLUMN FechaHora")
    conn.commit()

cur.execute("PRAGMA table_info(mediciones_rni)")
print("Después:", [r[1] for r in cur.fetchall()])

conn.close()
