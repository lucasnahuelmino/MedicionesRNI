import sqlite3
import sys

DB = r"archivosdata/rni.db"

print("Checking DB:", DB)

try:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
except Exception as e:
    print("ERROR connecting to DB:", e)
    sys.exit(2)

def run(sql):
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        print("\nSQL:", sql)
        if not rows:
            print("(no rows)")
        else:
            for r in rows[:20]:
                print(r)
    except Exception as e:
        print("ERROR", e)

# Check table info
run("PRAGMA table_info(resumen_localidades);")
# Count rows
run("SELECT COUNT(*) FROM resumen_localidades;")
# Sample rows
run("SELECT CCTE, Provincia, Localidad, Mediciones, TiempoTrabajadoSegundos FROM resumen_localidades LIMIT 20;")

conn.close()
print('\nDB check finished')
