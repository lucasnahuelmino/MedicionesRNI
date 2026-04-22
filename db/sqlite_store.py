import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DB_DIR = BASE_DIR / "archivosdata"
DB_PATH = DB_DIR / "rni.db"

TABLE_MEDICIONES = "mediciones_rni"

# Aliases para compatibilidad
DB_FILE = DB_PATH
TABLE_NAME = TABLE_MEDICIONES


# ============================================================
# CORE
# ============================================================

def _get_connection():
    DB_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ============================================================
# CREATE TABLE
# ============================================================

def ensure_table_exists():
    conn = _get_connection()
    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_MEDICIONES} (
                CCTE TEXT,
                Provincia TEXT,
                Localidad TEXT,
                Resultado REAL,
                Resultado_Pct REAL,
                Fecha TEXT,
                Hora TEXT,
                Nombre_Archivo TEXT,
                Expediente TEXT,
                Sonda TEXT,
                Lat REAL,
                Lon REAL,
                FechaCarga TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# INSERT
# ============================================================

def insert_mediciones(df: pd.DataFrame, update_resumen: bool = True):
    """
    Inserta mediciones en bloque.
    Ultra rápido.
    """
    if df is None or df.empty:
        return

    ensure_table_exists()

    df = df.copy()

    # Normalizar nombres
    df = df.rename(
        columns={
            "Nombre Archivo": "Nombre_Archivo",  # normalizar internamente
        }
    )

    # Orden fijo (importantísimo para performance)

    # Calcular columna Resultado_Pct
    df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
    df["Resultado_Pct"] = (df["Resultado"] ** 2) / 3770 / 0.20021 * 100

    columnas = [
        "CCTE",
        "Provincia",
        "Localidad",
        "Resultado",
        "Resultado_Pct",
        "Fecha",
        "Hora",
        "Nombre_Archivo",
        "Expediente",
        "Sonda",
        "Lat",
        "Lon",
        "FechaCarga",
    ]

    for col in columnas:
        if col not in df.columns:
            df[col] = None

    df = df[columnas]

    # Normalizar campos clave: limpiar espacios y convertir valores vacíos a NULL
    for _c in ["CCTE", "Provincia", "Localidad"]:
        if _c in df.columns:
            df[_c] = df[_c].astype(str).replace({"nan": ""}).str.strip().replace({"": None})

    # Convertir todo a python native
    df = df.where(pd.notnull(df), None)


    # Renombrar de vuelta para coincidir con columnas reales de la DB
    df = df.rename(columns={"Nombre_Archivo": "Nombre Archivo"})

    db_columns = [
        "CCTE", "Provincia", "Localidad", "Resultado", "Resultado_Pct",
        "Fecha", "Hora", "Nombre Archivo", "Expediente", "Sonda",
        "Lat", "Lon", "FechaCarga",
    ]
    cols_presentes = [c for c in db_columns if c in df.columns]
    placeholders = ", ".join(["?"] * len(cols_presentes))
    col_names = ", ".join([f'"{c}"' for c in cols_presentes])
    records = list(df[cols_presentes].itertuples(index=False, name=None))

    conn = _get_connection()
    try:
        conn.executemany(
            f'INSERT INTO {TABLE_MEDICIONES} ({col_names}) VALUES ({placeholders})',
            records,
        )
        conn.commit()
    finally:
        conn.close()

    # Actualizar caché de resumen luego de insertar nuevas mediciones (opcional)
    if update_resumen:
        try:
            rebuild_resumen_cache()
            # rebuild_graficos_cache se llama dentro de rebuild_resumen_cache
            # Invalida el cache de carga de datos para forzar refresco en próximo rerun
            load_tabla_maestra_from_db.clear()
            load_resumen_from_cache.clear()
        except Exception:
            # No hacemos fallar la inserción si el rebuild falla
            pass


# ============================================================
# LOAD (CON CACHE USANDO ST.CACHE_DATA)
# ============================================================

@st.cache_data
def load_tabla_maestra_from_db() -> pd.DataFrame:
    """
    Carga TODA la tabla desde SQLite.
    Cacheada para evitar lecturas repetidas.
    """
    if not DB_PATH.exists():
        return pd.DataFrame()

    conn = _get_connection()
    try:
        df = pd.read_sql(
            f"SELECT * FROM {TABLE_MEDICIONES}",
            conn,
        )
    finally:
        conn.close()

    # Volver a nombres humanos
    df = df.rename(columns={"Nombre_Archivo": "Nombre Archivo"})

    return df


# ============================================================
# DELETE
# ============================================================

def delete_by_localidad(localidad: str):
    conn = _get_connection()
    try:
        conn.execute(
            f"DELETE FROM {TABLE_MEDICIONES} WHERE Localidad = ?",
            (localidad,),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# SAVE (Reemplaza toda la tabla)
# ============================================================

def save_tabla_maestra_to_db(df: pd.DataFrame):
    """
    Guarda la tabla completa en SQLite.
    Reemplaza todos los registros existentes.
    """
    if df is None or df.empty:
        return

    ensure_table_exists()

    # Limpiar tabla existente
    conn = _get_connection()
    try:
        conn.execute(f"DELETE FROM {TABLE_MEDICIONES}")
        conn.commit()
    finally:
        conn.close()

    # Insertar nuevos registros
    # Insert sin reconstruir aún (reconstruiremos una sola vez abajo)
    insert_mediciones(df, update_resumen=False)

    # Reconstruir la tabla de resumen una vez
    rebuild_resumen_cache()


# ============================================================
# CACHE RESUMEN (para evitar recálculos)
# ============================================================

def _ensure_resumen_table_exists():
    """Crea tabla de caché de resumen si no existe."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resumen_localidades (
                CCTE TEXT,
                Provincia TEXT,
                Localidad TEXT,
                Mediciones INTEGER,
                Resultado_Max_Vm REAL,
                Resultado_Max_Pct REAL,
                FechaInicio TEXT,
                FechaFin TEXT,
                Expedientes TEXT,
                Sondas TEXT,
                TiempoTrabajadoSegundos INTEGER,
                PRIMARY KEY (CCTE, Provincia, Localidad)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def clear_resumen_cache():
    """Limpia el caché de resumen."""
    _ensure_resumen_table_exists()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM resumen_localidades")
        conn.commit()
    finally:
        conn.close()
    # Invalida el cache de carga
    load_resumen_from_cache.clear()


@st.cache_data
def load_resumen_from_cache() -> pd.DataFrame:
    """Carga el resumen precalculado desde el caché.
    Cacheada para evitar lecturas repetidas de la tabla resumen_localidades.
    """
    if not DB_PATH.exists():
        return pd.DataFrame()

    _ensure_resumen_table_exists()
    conn = _get_connection()
    try:
        df = pd.read_sql("SELECT * FROM resumen_localidades", conn)
    finally:
        conn.close()

    if df.empty:
        return df

    # Convertir fechas
    for col in ["FechaInicio", "FechaFin"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def rebuild_resumen_cache(df: pd.DataFrame | None = None):
    """Reconstruye la tabla `resumen_localidades` a partir de la tabla de mediciones.

    Si se provee `df`, lo usa; sino carga toda la tabla desde DB.
    """
    # Importar utilidades sólo cuando se necesitan (evita problemas de import circular)
    from utils.time_utils import add_fechahora, calcular_tiempo_total_por_archivo

    if df is None:
        df = load_tabla_maestra_from_db()

    if df is None or df.empty:
        # limpiar cache si no hay datos
        clear_resumen_cache()
        return

    # Normalizar columnas necesarias
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")

    # Normalizar claves para agrupar: quitar espacios y estableces None para vacíos
    for _c in ["CCTE", "Provincia", "Localidad"]:
        if _c in df.columns:
            df[_c] = df[_c].astype(str).replace({"nan": ""}).str.strip().replace({"": None})

    # Construir FechaHora robusta
    df = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")

    gb = df.groupby(["CCTE", "Provincia", "Localidad"], dropna=False)

    resumen = gb.agg(
        Mediciones=("Resultado", "size"),
        Resultado_Max_Vm=("Resultado", "max"),
        FechaInicio=("FechaHora", "min"),
        FechaFin=("FechaHora", "max"),
    ).reset_index()

    # % máximo
    resumen["Resultado_Max_Pct"] = (resumen["Resultado_Max_Vm"] ** 2) / (3770 * 0.20021) * 100
    resumen.loc[resumen["Resultado_Max_Vm"].isna(), "Resultado_Max_Pct"] = None

    # Expedientes y sondas
    if "Expediente" in df.columns:
        exp_map = gb["Expediente"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(exp_map.rename("Expedientes"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["Expedientes"] = ""

    if "Sonda" in df.columns:
        sonda_map = gb["Sonda"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(sonda_map.rename("Sondas"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["Sondas"] = ""

    # Tiempo trabajado (en segundos) - bucle por cantidad de localidades (normalmente pequeño)
    tiempos_seg = []
    for _, row in resumen[["CCTE", "Provincia", "Localidad"]].iterrows():
        ccte, prov, loc = row["CCTE"], row["Provincia"], row["Localidad"]
        g = df[(df["CCTE"] == ccte) & (df["Provincia"] == prov) & (df["Localidad"] == loc)]
        td = calcular_tiempo_total_por_archivo(g)
        try:
            segs = int(td.total_seconds())
        except Exception:
            segs = 0
        tiempos_seg.append(segs)

    resumen["TiempoTrabajadoSegundos"] = tiempos_seg

    # Guardar en DB (reemplaza contenido de resumen_localidades)
    _ensure_resumen_table_exists()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM resumen_localidades")
        records = []
        for _, r in resumen.iterrows():
            records.append(
                (
                    r.get("CCTE"),
                    r.get("Provincia"),
                    r.get("Localidad"),
                    int(r.get("Mediciones") or 0),
                    None if pd.isna(r.get("Resultado_Max_Vm")) else float(r.get("Resultado_Max_Vm")),
                    None if pd.isna(r.get("Resultado_Max_Pct")) else float(r.get("Resultado_Max_Pct")),
                    None if pd.isna(r.get("FechaInicio")) else str(r.get("FechaInicio")),
                    None if pd.isna(r.get("FechaFin")) else str(r.get("FechaFin")),
                    r.get("Expedientes") or "",
                    r.get("Sondas") or "",
                    int(r.get("TiempoTrabajadoSegundos") or 0),
                )
            )

        conn.executemany(
            """
            INSERT OR REPLACE INTO resumen_localidades (
                CCTE, Provincia, Localidad, Mediciones, Resultado_Max_Vm, Resultado_Max_Pct,
                FechaInicio, FechaFin, Expedientes, Sondas, TiempoTrabajadoSegundos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
    finally:
        conn.close()
    
    # Invalida el cache para forzar refresco en próximo acceso
    load_resumen_from_cache.clear()
    
    # También reconstruir cache de gráficos
    try:
        rebuild_graficos_cache(df)
    except Exception:
        pass


# ============================================================
# GRÁFICOS CACHE: Tablas precomputadas para tablero de comando
# ============================================================

def _ensure_graficos_tables_exist():
    """Crea las tablas de cache para gráficos si no existen."""
    conn = _get_connection()
    try:
        # Tabla resumen por CCTE
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graficos_ccte_summary (
                CCTE TEXT PRIMARY KEY,
                Puntos INTEGER,
                HorasSegundos INTEGER,
                DiasConMedicion INTEGER
            )
            """
        )
        
        # Tabla Provincia-CCTE con cantidad de localidades
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graficos_provincia_ccte (
                Provincia TEXT,
                CCTE TEXT,
                NumLocalidades INTEGER,
                PRIMARY KEY (Provincia, CCTE)
            )
            """
        )
        
        # Tabla resumen mensual
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graficos_mensual (
                Mes TEXT PRIMARY KEY,
                Puntos INTEGER
            )
            """
        )
        
        # Tabla hotspots por localidad
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graficos_hotspots (
                Localidad TEXT PRIMARY KEY,
                Provincia TEXT,
                CCTE TEXT,
                ResultadoMaxVm REAL,
                ResultadoMaxPct REAL,
                Puntos INTEGER
            )
            """
        )
        
        conn.commit()
    finally:
        conn.close()


@st.cache_data
def load_graficos_ccte_summary() -> pd.DataFrame:
    """Carga resumen por CCTE desde cache."""
    _ensure_graficos_tables_exist()
    conn = _get_connection()
    try:
        df = pd.read_sql("SELECT * FROM graficos_ccte_summary", conn)
    finally:
        conn.close()
    return df


@st.cache_data
def load_graficos_provincia_ccte() -> pd.DataFrame:
    """Carga resumen Provincia-CCTE desde cache."""
    _ensure_graficos_tables_exist()
    conn = _get_connection()
    try:
        df = pd.read_sql("SELECT * FROM graficos_provincia_ccte", conn)
    finally:
        conn.close()
    return df


@st.cache_data
def load_graficos_mensual() -> pd.DataFrame:
    """Carga resumen mensual desde cache."""
    _ensure_graficos_tables_exist()
    conn = _get_connection()
    try:
        df = pd.read_sql("SELECT * FROM graficos_mensual ORDER BY Mes", conn)
    finally:
        conn.close()
    return df


@st.cache_data
def load_graficos_hotspots() -> pd.DataFrame:
    """Carga hotspots desde cache."""
    _ensure_graficos_tables_exist()
    conn = _get_connection()
    try:
        df = pd.read_sql("SELECT * FROM graficos_hotspots ORDER BY ResultadoMaxPct DESC", conn)
    finally:
        conn.close()
    return df


def rebuild_graficos_cache(df: pd.DataFrame | None = None):
    """Reconstruye todas las tablas de cache de gráficos.
    
    Si se provee `df`, lo usa; sino carga toda la tabla desde DB.
    """
    from utils.time_utils import add_fechahora, calcular_tiempo_total_por_archivo
    
    if df is None:
        df = load_tabla_maestra_from_db()
    
    if df is None or df.empty:
        return
    
    # Normalizar claves
    for col in ["CCTE", "Provincia", "Localidad"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": ""}).str.strip().replace({"": None})
    
    # Construir FechaHora
    df = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
    
    # Normalizar Resultado
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
    
    # Fecha para agrupación
    df["Fecha_dt"] = pd.to_datetime(df["FechaHora"], errors="coerce").dt.date
    df["Mes"] = pd.to_datetime(df["FechaHora"], errors="coerce").dt.to_period("M").astype(str)
    
    _ensure_graficos_tables_exist()
    conn = _get_connection()
    try:
        # 1. CCTE Summary
        ccte_data = []
        for ccte, g in df.groupby("CCTE", dropna=False):
            if pd.isna(ccte):
                continue
            td = calcular_tiempo_total_por_archivo(g)
            horas_seg = int(td.total_seconds())
            dias = int(g["Fecha_dt"].dropna().nunique())
            puntos = len(g)
            ccte_data.append((str(ccte), puntos, horas_seg, dias))
        
        conn.execute("DELETE FROM graficos_ccte_summary")
        if ccte_data:
            conn.executemany(
                "INSERT INTO graficos_ccte_summary (CCTE, Puntos, HorasSegundos, DiasConMedicion) VALUES (?, ?, ?, ?)",
                ccte_data
            )
        
        # 2. Provincia-CCTE
        prov_ccte_data = []
        for (prov, ccte), g in df.groupby(["Provincia", "CCTE"], dropna=False):
            if pd.isna(prov) or pd.isna(ccte):
                continue
            num_loc = int(g["Localidad"].dropna().nunique())
            prov_ccte_data.append((str(prov), str(ccte), num_loc))
        
        conn.execute("DELETE FROM graficos_provincia_ccte")
        if prov_ccte_data:
            conn.executemany(
                "INSERT INTO graficos_provincia_ccte (Provincia, CCTE, NumLocalidades) VALUES (?, ?, ?)",
                prov_ccte_data
            )
        
        # 3. Mensual
        mes_data = []
        for mes, g in df.groupby("Mes", dropna=False):
            if pd.isna(mes):
                continue
            puntos = len(g)
            mes_data.append((str(mes), puntos))
        
        conn.execute("DELETE FROM graficos_mensual")
        if mes_data:
            conn.executemany(
                "INSERT INTO graficos_mensual (Mes, Puntos) VALUES (?, ?)",
                mes_data
            )
        
        # 4. Hotspots por localidad
        df_hot = df.dropna(subset=["Resultado", "Localidad"]).copy()
        hotspots_data = []
        for loc, g in df_hot.groupby("Localidad"):
            max_vm = g["Resultado"].max()
            max_pct = (max_vm ** 2) / 3770 / 0.20021 * 100 if pd.notna(max_vm) else None
            puntos = len(g)
            prov = g["Provincia"].iloc[0] if "Provincia" in g.columns and not g.empty else None
            ccte = g["CCTE"].iloc[0] if "CCTE" in g.columns and not g.empty else None
            
            hotspots_data.append((str(loc), str(prov) if prov else None, str(ccte) if ccte else None, 
                                 float(max_vm) if pd.notna(max_vm) else None,
                                 float(max_pct) if pd.notna(max_pct) else None, puntos))
        
        conn.execute("DELETE FROM graficos_hotspots")
        if hotspots_data:
            conn.executemany(
                """INSERT INTO graficos_hotspots 
                   (Localidad, Provincia, CCTE, ResultadoMaxVm, ResultadoMaxPct, Puntos) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                hotspots_data
            )
        
        conn.commit()
    finally:
        conn.close()
    
    # Invalida caches
    load_graficos_ccte_summary.clear()
    load_graficos_provincia_ccte.clear()
    load_graficos_mensual.clear()
    load_graficos_hotspots.clear()