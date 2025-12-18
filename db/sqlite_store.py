import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

DB_FILE = BASE_DIR / "archivosdata" / "rni.db"
TABLE_NAME = "mediciones_rni"   

EXPECTED_COLS = [
    "CCTE", "Provincia", "Localidad",
    "Resultado", "Fecha", "Hora",
    "Nombre Archivo", "Expediente",
    "Sonda", "Lat", "Lon",
    "FechaCarga",
]


def load_tabla_maestra_from_db() -> pd.DataFrame:
    """Carga mediciones desde SQLite. Si no existe, devuelve DF vacío."""
    if not DB_FILE.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(DB_FILE))
    try:
        # Si existe la tabla esperada, la leemos
        tablas = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';",
            conn
        )["name"].tolist()

        if TABLE_NAME not in tablas:
            return pd.DataFrame()

        df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)

        # Normalización robusta de columnas (por si venís con nombres raros)
        col_map = {}
        for c in df.columns:
            key = str(c).strip().lower().replace("ó", "o").replace("í", "i")
            if key == "ccte":
                col_map[c] = "CCTE"
            elif key == "provincia":
                col_map[c] = "Provincia"
            elif key == "localidad":
                col_map[c] = "Localidad"
            elif key in ("resultado", "resultado_con_incertidumbre"):
                col_map[c] = "Resultado"
            elif key == "fecha":
                col_map[c] = "Fecha"
            elif key in ("hora", "time"):
                col_map[c] = "Hora"
            elif key in ("nombrearchivo", "nombre_archivo", "archivo"):
                col_map[c] = "Nombre Archivo"
            elif key == "expediente":
                col_map[c] = "Expediente"
            elif key in ("sonda", "sonda_utilizada"):
                col_map[c] = "Sonda"
            elif key in ("lat", "latitud"):
                col_map[c] = "Lat"
            elif key in ("lon", "longitud"):
                col_map[c] = "Lon"
            elif key in ("fechacarga", "fecha_carga"):
                col_map[c] = "FechaCarga"

        if col_map:
            df = df.rename(columns=col_map)

        # Garantiza columnas esperadas
        for col in EXPECTED_COLS:
            if col not in df.columns:
                df[col] = np.nan

        return df

    finally:
        conn.close()


def _sanitize_for_sqlite(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte tipos problemáticos (Timestamp/datetime/date/time) a string."""
    if df is None or df.empty:
        return df

    out = df.copy()

    # Convertir columnas datetime64[ns] a texto ISO
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

    # Convertir objetos Timestamp sueltos o datetime/date/time dentro de columnas object
    def conv(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        if isinstance(x, pd.Timestamp):
            return x.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
        # python datetime/date/time
        if hasattr(x, "isoformat"):
            try:
                return x.isoformat(sep=" ")
            except TypeError:
                return x.isoformat()
        return x

    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].map(conv)

    return out


def save_tabla_maestra_to_db(df: pd.DataFrame):
    """Guarda toda la tabla en SQLite."""
    if df is None:
        return

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    df2 = _sanitize_for_sqlite(df)

    conn = sqlite3.connect(str(DB_FILE))
    try:
        df2.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    finally:
        conn.close()
