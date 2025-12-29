# sections/diagnostico.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


# ============================================================
# DB: toma la ruta real si existe en sqlite_store, si no fallback
# ============================================================
try:
    from db.sqlite_store import DB_FILE as _DB_FILE, TABLE_NAME as _TABLE_NAME
    DB_FILE = Path(_DB_FILE)
    TABLE_NAME = str(_TABLE_NAME)
except Exception:
    DB_FILE = Path("archivosdata") / "rni.db"
    TABLE_NAME = "mediciones_rni"


# ============================================================
# Helpers DB
# ============================================================
def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    q = "SELECT name FROM sqlite_master WHERE type='table' AND name=?;"
    cur = conn.execute(q, (table_name,))
    return cur.fetchone() is not None


def _safe_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int | float | str | None:
    try:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ============================================================
# Parseo suelto SOLO para diagnóstico de “parseabilidad”
# (No es para cálculo de horas; eso lo hace time_utils)
# ============================================================
def _parse_datetime_loose(fecha: pd.Series, hora: pd.Series) -> pd.Series:
    """
    Devuelve datetime (o NaT) parseando formatos típicos:
    Fecha: '20/03/2025', '2025-03-20', etc.
    Hora: '10:08:09 a.m.', '10:08:09', '22:10', etc.
    """
    if fecha is None or hora is None:
        return pd.Series(pd.NaT)

    f = pd.to_datetime(fecha.astype("string"), dayfirst=True, errors="coerce")

    h_raw = hora.astype("string").fillna("").str.strip().str.lower()

    # Limpieza suave: "a.m." -> "am", "p.m." -> "pm", quita puntos
    h_norm = (
        h_raw
        .str.replace(r"\s+", " ", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(" a m", " am", regex=False)
        .str.replace(" p m", " pm", regex=False)
    )

    # parse de hora (Pandas suele bancar "10:08:09 am")
    h = pd.to_datetime(h_norm, errors="coerce")

    # Combinar ISO string (sin apply)
    fecha_iso = f.dt.strftime("%Y-%m-%d")
    hora_iso = h.dt.strftime("%H:%M:%S")
    combo = pd.to_datetime(fecha_iso + " " + hora_iso, errors="coerce")

    # Si fecha u hora no parsean -> NaT
    combo = combo.where(f.notna() & h.notna(), pd.NaT)
    return combo


# ============================================================
# Filtros globales (opcionales). Si no existen, no rompe.
# ============================================================
def _try_get_global_filters() -> dict:
    """
    Si tenés state.py con filtros globales, los levanta.
    Si no existe o falla, devuelve filtros vacíos.
    """
    try:
        import state  # noqa
        if hasattr(state, "init_global_filters"):
            state.init_global_filters()
        gf = st.session_state.get("global_filters", {"ccte": [], "provincia": [], "anio": "Todos"})
        return gf if isinstance(gf, dict) else {"ccte": [], "provincia": [], "anio": "Todos"}
    except Exception:
        return {"ccte": [], "provincia": [], "anio": "Todos"}


def _filters_caption() -> str:
    gf = _try_get_global_filters()
    chips = []
    if gf.get("ccte"):
        chips.append(f"CCTE: {', '.join([str(x) for x in gf['ccte']])}")
    if gf.get("provincia"):
        chips.append(f"Prov: {', '.join([str(x) for x in gf['provincia']])}")
    if gf.get("anio") and gf["anio"] != "Todos":
        chips.append(f"Año: {gf['anio']}")
    return " · ".join(chips) if chips else "Mostrando: todo"


def _sql_where_from_global_filters() -> tuple[str, tuple]:
    """
    Arma WHERE SQL + params según filtros globales (si existen).
    Compatible con columnas textuales.
    """
    gf = _try_get_global_filters()

    clauses = []
    params: list = []

    # CCTE
    cctes = gf.get("ccte") or []
    if cctes:
        placeholders = ",".join(["?"] * len(cctes))
        clauses.append(f"CCTE IN ({placeholders})")
        params.extend([str(x) for x in cctes])

    # Provincia
    provs = gf.get("provincia") or []
    if provs:
        placeholders = ",".join(["?"] * len(provs))
        clauses.append(f"Provincia IN ({placeholders})")
        params.extend([str(x) for x in provs])

    # Año (si Fecha está dd/mm/yyyy o yyyy-mm-dd)
    anio = gf.get("anio", "Todos")
    if anio != "Todos":
        # Intento simple: matchear por substring del año
        # dd/mm/yyyy -> termina en yyyy
        # yyyy-mm-dd -> empieza con yyyy
        clauses.append("(Fecha LIKE ? OR Fecha LIKE ?)")
        params.extend([f"%/{anio}", f"{anio}-%"])

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    return where, tuple(params)


# ============================================================
# UI principal
# ============================================================
def render_diagnostico():
    st.header("🧪 Diagnóstico / Salud de datos")
    st.caption(_filters_caption())

    if not DB_FILE.exists():
        st.warning(f"No encuentro la base en: {DB_FILE}")
        return

    conn = sqlite3.connect(str(DB_FILE))
    try:
        if not _table_exists(conn, TABLE_NAME):
            st.warning(f"La tabla '{TABLE_NAME}' no existe dentro de {DB_FILE.name}.")
            return

        where, params = _sql_where_from_global_filters()

        # --- KPIs SQL (baratos) ---
        total_rows = _safe_scalar(conn, f"SELECT COUNT(*) FROM {TABLE_NAME} {where};", params) or 0
        if int(total_rows) == 0:
            st.info("La tabla existe, pero con los filtros actuales quedó vacía.")
            return

        distinct_loc = _safe_scalar(conn, f"SELECT COUNT(DISTINCT Localidad) FROM {TABLE_NAME} {where};", params) or 0
        distinct_prov = _safe_scalar(conn, f"SELECT COUNT(DISTINCT Provincia) FROM {TABLE_NAME} {where};", params) or 0
        distinct_ccte = _safe_scalar(conn, f"SELECT COUNT(DISTINCT CCTE) FROM {TABLE_NAME} {where};", params) or 0

        # FechaCarga MAX (si el formato no es ISO igual sirve como “indicador”)
        max_fechacarga = _safe_scalar(conn, f"SELECT MAX(FechaCarga) FROM {TABLE_NAME} {where};", params)

        # Conteos no vacíos (SQL)
        nn_fecha = _safe_scalar(
            conn,
            f"SELECT COUNT(*) FROM {TABLE_NAME} {where} AND Fecha IS NOT NULL AND TRIM(Fecha)<>'';"
            if where else
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE Fecha IS NOT NULL AND TRIM(Fecha)<>'';"
        , params) or 0

        nn_hora = _safe_scalar(
            conn,
            f"SELECT COUNT(*) FROM {TABLE_NAME} {where} AND Hora IS NOT NULL AND TRIM(Hora)<>'';"
            if where else
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE Hora IS NOT NULL AND TRIM(Hora)<>'';"
        , params) or 0

        nn_latlon = _safe_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            {where}
            {"AND" if where else "WHERE"} Lat IS NOT NULL AND TRIM(Lat)<>'' AND Lon IS NOT NULL AND TRIM(Lon)<>'';
            """,
            params
        ) or 0

        nn_ampm = _safe_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            {where}
            {"AND" if where else "WHERE"} Hora IS NOT NULL
              AND (LOWER(Hora) LIKE '%a.m.%'
                   OR LOWER(Hora) LIKE '%p.m.%'
                   OR LOWER(Hora) LIKE '% am%'
                   OR LOWER(Hora) LIKE '% pm%');
            """,
            params
        ) or 0

        # --- Muestra chica (para parseabilidad real sin matar RAM) ---
        SAMPLE_N = 8000
        sample_sql = f"""
            SELECT Fecha, Hora, Lat, Lon, Resultado
            FROM {TABLE_NAME}
            {where}
            LIMIT {SAMPLE_N};
        """
        sample = pd.read_sql(sample_sql, conn, params=params)

        if not sample.empty:
            dt = _parse_datetime_loose(sample.get("Fecha"), sample.get("Hora"))
            pct_dt_ok = float(dt.notna().mean() * 100.0)

            lat = pd.to_numeric(sample.get("Lat"), errors="coerce")
            lon = pd.to_numeric(sample.get("Lon"), errors="coerce")

            # rango amplio para no “castigar” cargas que vengan positivas
            lat_ok = lat.notna() & ((lat.between(-60, -15)) | (lat.abs().between(15, 60)))
            lon_ok = lon.notna() & ((lon.between(-80, -40)) | (lon.abs().between(40, 80)))
            pct_coords_ok = float((lat_ok & lon_ok).mean() * 100.0)

            res = pd.to_numeric(sample.get("Resultado"), errors="coerce")
            pct_res_ok = float(res.notna().mean() * 100.0)

            dup_coords = 0
            tmp = pd.DataFrame({"lat": lat.round(6), "lon": lon.round(6)}).dropna()
            if not tmp.empty:
                dup_coords = int(tmp.duplicated().sum())
        else:
            pct_dt_ok = pct_coords_ok = pct_res_ok = 0.0
            dup_coords = 0

        # --- UI KPIs ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Registros", f"{int(total_rows):,}".replace(",", "."))
        c2.metric("Localidades", f"{int(distinct_loc):,}".replace(",", "."))
        c3.metric("Provincias", f"{int(distinct_prov):,}".replace(",", "."))
        c4.metric("CCTEs", f"{int(distinct_ccte):,}".replace(",", "."))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Fecha no vacía (SQL)", f"{(nn_fecha/total_rows*100):.1f}%")
        c6.metric("Hora no vacía (SQL)", f"{(nn_hora/total_rows*100):.1f}%")
        c7.metric("Lat/Lon no vacías (SQL)", f"{(nn_latlon/total_rows*100):.1f}%")
        c8.metric("AM/PM detectado", f"{(nn_ampm/total_rows*100):.1f}%")

        c9, c10, c11, c12 = st.columns(4)
        c9.metric("FechaHora parseable (muestra)", f"{pct_dt_ok:.1f}%")
        c10.metric("Coords válidas (muestra)", f"{pct_coords_ok:.1f}%")
        c11.metric("Resultado numérico (muestra)", f"{pct_res_ok:.1f}%")
        c12.metric("Duplicados coords (muestra)", f"{dup_coords:,}".replace(",", "."))

        if max_fechacarga:
            st.caption(f"🕒 Última FechaCarga detectada (MAX): **{max_fechacarga}**")
        else:
            st.caption("🕒 Última FechaCarga detectada (MAX): **N/D**")

        st.markdown("---")

        # --- TOP 10 localidades por pico ---
        st.subheader("🔥 Top localidades por pico (máximo)")

        top_sql = f"""
            SELECT
              CCTE,
              Provincia,
              Localidad,
              MAX(CAST(Resultado AS REAL)) AS max_vm,
              COUNT(*) AS puntos
            FROM {TABLE_NAME}
            {where}
            {"AND" if where else "WHERE"} Resultado IS NOT NULL AND TRIM(Resultado)<>''

            GROUP BY CCTE, Provincia, Localidad
            ORDER BY max_vm DESC
            LIMIT 10;
        """
        top = pd.read_sql(top_sql, conn, params=params)
        if top.empty:
            st.info("No pude calcular el top (Resultado vacío o no numérico).")
        else:
            top["max_vm"] = pd.to_numeric(top["max_vm"], errors="coerce")
            top["Resultado Max (V/m)"] = top["max_vm"].round(2)
            top["Resultado Max (%)"] = ((top["max_vm"] ** 2) / 3770 / 0.20021 * 100).round(2)
            top = top.rename(columns={"puntos": "Puntos"})
            show = top[["CCTE", "Provincia", "Localidad", "Resultado Max (V/m)", "Resultado Max (%)", "Puntos"]]
            st.dataframe(show, width="stretch", hide_index=True)

        st.markdown("---")

        # --- Señales de problemas ---
        st.subheader("🧯 Señales de problemas comunes")

        problems = [
            ("Filas totales", int(total_rows)),
            ("Fecha vacía", int(total_rows - nn_fecha)),
            ("Hora vacía", int(total_rows - nn_hora)),
            ("Lat/Lon vacías", int(total_rows - nn_latlon)),
            ("Hora con AM/PM", int(nn_ampm)),
        ]
        dfp = pd.DataFrame(problems, columns=["Señal", "Conteo"]).sort_values("Conteo", ascending=False)
        st.dataframe(dfp, width="stretch", hide_index=True)

        with st.expander("🧠 Qué significa esto (rápido)", expanded=False):
            st.write(
                "- **FechaHora parseable baja** suele venir de Hora tipo `10:08:09 a.m.` o textos raros.\n"
                "- **Lat/Lon vacías** → mapa queda vacío o pesado.\n"
                "- **Muchos duplicados** no está “mal”, pero puede inflar el JSON del mapa si hay miles.\n"
                "- Para el futuro: al cargar, guardar `FechaHora` en ISO en DB evita dolores de 2026."
            )

    finally:
        conn.close()
