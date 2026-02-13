import sqlite3
import pandas as pd

DB_PATH = "archivosdata/rni.db"


conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
# Verificar si la columna Resultado_Pct existe
c.execute("PRAGMA table_info(mediciones_rni)")
columns = [col[1] for col in c.fetchall()]
if "Resultado_Pct" not in columns:
    print("Agregando columna Resultado_Pct a la tabla mediciones_rni...")
    c.execute("ALTER TABLE mediciones_rni ADD COLUMN Resultado_Pct REAL")
    conn.commit()

# Cargar toda la tabla de mediciones
df = pd.read_sql("SELECT rowid, * FROM mediciones_rni", conn)

# Calcular el porcentaje si existe la columna Resultado
if "Resultado" in df.columns:
    df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
    df["Resultado_Pct"] = (df["Resultado"] ** 2) / 3770 / 0.20021 * 100
    # Actualizar cada registro
    for _, row in df.iterrows():
        conn.execute(
            "UPDATE mediciones_rni SET Resultado_Pct = ? WHERE rowid = ?",
            (row["Resultado_Pct"], row["rowid"])
        )
    conn.commit()
    print("Actualización completada.")
else:
    print("No existe la columna Resultado en la tabla.")

conn.close()
