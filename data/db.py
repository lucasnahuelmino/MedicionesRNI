# data/db.py
import sqlite3
import pandas as pd
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path("db/rni.db")


# -------------------------------------------------
# Conexión controlada (una por query)
# -------------------------------------------------
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# -------------------------------------------------
# CARGAS BASE
# -------------------------------------------------
def load_mediciones() -> pd.DataFrame:
    """Carga TODAS las mediciones (sin filtros)."""
    with get_conn() as conn:
        df = pd.read_sql("SELECT * FROM mediciones", conn)
    return df


def load_resumen_localidad(anio: int | None = None) -> pd.DataFrame:
    """Carga resumen por localidad (opcional por año)."""
    query = "SELECT * FROM resumen_localidad"
    params = []

    if anio is not None:
        query += " WHERE anio = ?"
        params.append(anio)

    with get_conn() as conn:
        df = pd.read_sql(query, conn, params=params)

    return df


# -------------------------------------------------
# FILTROS SQL (NO pandas)
# -------------------------------------------------
def load_mediciones_filtradas(
    ccte: list[str] | None = None,
    provincia: list[str] | None = None,
    anio: int | None = None,
) -> pd.DataFrame:
    where = []
    params = []

    if ccte:
        where.append(f"ccte IN ({','.join(['?'] * len(ccte))})")
        params.extend(ccte)

    if provincia:
        where.append(f"provincia IN ({','.join(['?'] * len(provincia))})")
        params.extend(provincia)

    if anio:
        where.append("anio = ?")
        params.append(anio)

    query = "SELECT * FROM mediciones"
    if where:
        query += " WHERE " + " AND ".join(where)

    with get_conn() as conn:
        df = pd.read_sql(query, conn, params=params)

    return df


# -------------------------------------------------
# KPIs DIRECTOS (sin DataFrame)
# -------------------------------------------------
def get_promedio_general(
    ccte: list[str] | None = None,
    provincia: list[str] | None = None,
    anio: int | None = None,
) -> float:
    where = []
    params = []

    if ccte:
        where.append(f"ccte IN ({','.join(['?'] * len(ccte))})")
        params.extend(ccte)

    if provincia:
        where.append(f"provincia IN ({','.join(['?'] * len(provincia))})")
        params.extend(provincia)

    if anio:
        where.append("anio = ?")
        params.append(anio)

    query = "SELECT AVG(porcentaje) FROM mediciones"
    if where:
        query += " WHERE " + " AND ".join(where)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        res = cur.fetchone()[0]

    return round(res or 0, 2)
