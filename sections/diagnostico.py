# sections/diagnostico.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st


# Intentamos tomar la misma DB y tabla que usa tu app.
# Si por algún motivo cambia el import, caemos a defaults seguros.
try:
    from db.sqlite_store import DB_FILE as _DB_FILE, TABLE_NAME as _TABLE_NAME
    DB_FILE = Path(_DB_FILE)
    TABLE_NAME = str(_TABLE_NAME)
except Exception:
    DB_FILE = Path("archivosdata") / "rni.db"
    TABLE_NAME = "mediciones_rni"


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


def _parse_datetime_loose(fecha: pd.Series, hora: pd.Series) -> pd.Series:
    """
    Devuelve datetime (o NaT) parseando formatos típicos:
    Fecha: '20/03/2025', '2025-03-20', etc.
    Hora: '10:08:09 a.m.', '10:08:09', '22:10', etc.
    """
    f = pd.to_datetime(fecha.astype(str), dayfirst=True, errors="coerce")

    # Hora: normalizamos variantes "a.m." / "p.m."
    h_raw = hora.astype(str).str.strip().str.lower()
    # Limpieza suave
    h_norm = (
        h_raw.replace({"nan": ""})
        .str.replace(".", "", regex=False)     # a.m. -> am
        .str.replace(" a m", " am", regex=False)
        .str.replace(" p m", " pm", regex=False)
    )

    # Probamos parsear hora en datetime (solo hora)
    # Si viene con am/pm, pandas lo entiende bastante bien.
    h = pd.to_datetime(h_norm, errors="coerce")

    # Armamos datetime combinando fecha + hora
    # Usamos strings ISO para evitar apply() pesado
    fecha_iso = f.dt.strftime("%Y-%m-%d")
    hora_iso = h.dt.strftime("%H:%M:%S")

    combo = pd.to_datetime(fecha_iso + " " + hora_iso, errors="coerce")
    return combo


def render_diagnostico():
    st.header("🧪 Diagnóstico / Salud de datos")

    if not DB_FILE.exists():
        st.warning(f"No encuentro la base en: {DB_FILE}")
        return

    # --- Conexión DB ---
    conn = sqlite3.connect(str(DB_FILE))
    try:
        if not _table_exists(conn, TABLE_NAME):
            st.warning(f"La tabla '{TABLE_NAME}' no existe dentro de {DB_FILE.name}.")
            return

        # --- KPIs SQL (baratos) ---
        total_rows = _safe_scalar(conn, f"SELECT COUNT(*) FROM {TABLE_NAME};") or 0
        if total_rows == 0:
            st.info("La tabla existe pero está vacía.")
            return

        distinct_loc = _safe_scalar(conn, f"SELECT COUNT(DISTINCT Localidad) FROM {TABLE_NAME};") or 0
        distinct_prov = _safe_scalar(conn, f"SELECT COUNT(DISTINCT Provincia) FROM {TABLE_NAME};") or 0
        distinct_ccte = _safe_scalar(conn, f"SELECT COUNT(DISTINCT CCTE) FROM {TABLE_NAME};") or 0

        # FechaCarga suele ser TEXT. Si está en ISO, MAX funciona. Si no, lo mostramos como venga.
        max_fechacarga = _safe_scalar(conn, f"SELECT MAX(FechaCarga) FROM {TABLE_NAME};")

        # Conteos de no-null (SQL)
        nn_fecha = _safe_scalar(conn, f"SELECT COUNT(Fecha) FROM {TABLE_NAME} WHERE Fecha IS NOT NULL AND TRIM(Fecha)<>'';") or 0
        nn_hora = _safe_scalar(conn, f"SELECT COUNT(Hora) FROM {TABLE_NAME} WHERE Hora IS NOT NULL AND TRIM(Hora)<>'';") or 0
        nn_latlon = _safe_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            WHERE Lat IS NOT NULL AND TRIM(Lat)<>'' AND Lon IS NOT NULL AND TRIM(Lon)<>'';
            """
        ) or 0

        # “Señales” típicas de hora con AM/PM (SQL)
        nn_ampm = _safe_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            WHERE Hora IS NOT NULL
              AND (LOWER(Hora) LIKE '%a.m.%'
                   OR LOWER(Hora) LIKE '%p.m.%'
                   OR LOWER(Hora) LIKE '% am%'
                   OR LOWER(Hora) LIKE '% pm%');
            """
        ) or 0

        # --- Muestra chica para validar “parseabilidad real” (sin matar RAM) ---
        SAMPLE_N = 8000  # ajustable
        sample = pd.read_sql(
            f"""
            SELECT Fecha, Hora, Lat, Lon, Resultado
            FROM {TABLE_NAME}
            WHERE (Fecha IS NOT NULL OR Hora IS NOT NULL OR Lat IS NOT NULL OR Lon IS NOT NULL OR Resultado IS NOT NULL)
            LIMIT {SAMPLE_N};
            """,
            conn
        )

        # Parseos (muestra)
        if not sample.empty:
            dt = _parse_datetime_loose(sample.get("Fecha", pd.Series(dtype=object)),
                                       sample.get("Hora", pd.Series(dtype=object)))
            pct_dt_ok = float(dt.notna().mean() * 100.0)

            lat = pd.to_numeric(sample.get("Lat", pd.Series(dtype=object)), errors="coerce")
            lon = pd.to_numeric(sample.get("Lon", pd.Series(dtype=object)), errors="coerce")

            # Aceptamos coordenadas negativas (Argentina) o positivas (algunas cargas vienen así)
            lat_ok = lat.notna() & ((lat.between(-60, -15)) | (lat.abs().between(15, 60)))
            lon_ok = lon.notna() & ((lon.between(-80, -40)) | (lon.abs().between(40, 80)))
            pct_coords_ok = float((lat_ok & lon_ok).mean() * 100.0)

            # Resultado numérico (muestra)
            res = pd.to_numeric(sample.get("Resultado", pd.Series(dtype=object)), errors="coerce")
            pct_res_ok = float(res.notna().mean() * 100.0)

            # Duplicados de coordenadas (muestra) -> puede inflar JSON del mapa si son MUCHÍSIMOS
            dup_coords = 0
            if lat.notna().any() and lon.notna().any():
                tmp = pd.DataFrame({"lat": lat.round(6), "lon": lon.round(6)}).dropna()
                dup_coords = int(tmp.duplicated().sum())
        else:
            pct_dt_ok = 0.0
            pct_coords_ok = 0.0
            pct_res_ok = 0.0
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

        # Última carga
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
        WHERE Resultado IS NOT NULL AND TRIM(Resultado)<>''
        GROUP BY CCTE, Provincia, Localidad
        ORDER BY max_vm DESC
        LIMIT 10;
        """
        top = pd.read_sql(top_sql, conn)
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

        # --- Señales de problemas (compacto) ---
        st.subheader("🧯 Señales de problemas comunes")

        problems = []
        problems.append(("Filas totales", int(total_rows)))
        problems.append(("Fecha vacía", int(total_rows - nn_fecha)))
        problems.append(("Hora vacía", int(total_rows - nn_hora)))
        problems.append(("Lat/Lon vacías", int(total_rows - nn_latlon)))
        problems.append(("Hora con AM/PM", int(nn_ampm)))

        dfp = pd.DataFrame(problems, columns=["Señal", "Conteo"]).sort_values("Conteo", ascending=False)
        st.dataframe(dfp, width="stretch", hide_index=True)

        # Mini nota útil
        with st.expander("🧠 Qué significa esto (rápido)", expanded=False):
            st.write(
                "- **FechaHora parseable baja** suele venir de Hora tipo `10:08:09 a.m.` o textos raros.\n"
                "- **Lat/Lon vacías** → mapa explota o queda vacío.\n"
                "- **Muchos duplicados de coordenadas** no está “mal”, pero puede inflar el JSON del mapa si hay miles y miles.\n"
                "- Si querés precisión en parseo: normalizamos al cargar y guardamos en DB en formato ISO."
            )

    finally:
        conn.close()
