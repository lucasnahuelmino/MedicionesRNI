# db/migrations.py
import sqlite3
from pathlib import Path

DB_PATH = Path("db/rni.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # -------------------------------
    # Tabla principal: mediciones
    # -------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mediciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ccte TEXT,
        provincia TEXT,
        localidad TEXT,
        expediente TEXT,
        resultado_vm REAL,
        porcentaje REAL,
        fecha_medicion DATE,
        anio INTEGER,
        mes INTEGER,
        fuente_archivo TEXT,
        fecha_carga DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Índices (performance real)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_med_ccte ON mediciones(ccte);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_med_prov ON mediciones(provincia);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_med_loc ON mediciones(localidad);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_med_anio ON mediciones(anio);")

    # -----------------------------------
    # Tabla resumen por localidad
    # -----------------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resumen_localidad (
        localidad TEXT,
        provincia TEXT,
        ccte TEXT,
        anio INTEGER,
        puntos INTEGER,
        max_vm REAL,
        max_pct REAL,
        prom_vm REAL,
        prom_pct REAL,
        ultima_medicion DATE,
        PRIMARY KEY (localidad, provincia, ccte, anio)
    );
    """)

    conn.commit()
    conn.close()
    print("✅ Migración completada correctamente.")

if __name__ == "__main__":
    migrate()
