from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.time_utils import (
    add_fechahora,
    calcular_tiempo_total_por_archivo,
    format_timedelta_long,
)
from db.sqlite_store import load_resumen_from_cache
from state import get_df_filtrado_global, has_active_global_filters, render_active_filters_banner

# Constante para % (la misma que venís usando)
K_DEN = 3770 * 0.20021


def _calculate_resumen_optimized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula resumen VECTORIZADO (sin bucles por fila).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Construir FechaHora robusta (vectorizado)
    df = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")

    needed = ["CCTE", "Provincia", "Localidad"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()

    gb = df.groupby(["CCTE", "Provincia", "Localidad"], dropna=False)

    # Agregaciones vectorizadas
    resumen = gb.agg(
        Mediciones=("Resultado", "size"),
        Resultado_Max_Vm=("Resultado", "max"),
        Inicio=("FechaHora", "min"),
        Fin=("FechaHora", "max"),
    ).reset_index()

    # % máximo (vectorizado)
    resumen["Resultado_Max_%"] = (resumen["Resultado_Max_Vm"] ** 2) / K_DEN * 100
    resumen.loc[resumen["Resultado_Max_Vm"].isna(), "Resultado_Max_%"] = pd.NA

    # Expedientes / Sondas
    if "Expediente" in df.columns:
        exp_map = gb["Expediente"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(exp_map.rename("N° Expediente"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["N° Expediente"] = ""

    if "Sonda" in df.columns:
        sonda_map = gb["Sonda"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(sonda_map.rename("Sonda utilizada"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["Sonda utilizada"] = ""

    # Tiempo trabajado (loop por localidades, pero este bucle es por cantidad de localidades)
    tiempos = []
    for _, row in resumen[["CCTE", "Provincia", "Localidad"]].iterrows():
        ccte, prov, loc = row["CCTE"], row["Provincia"], row["Localidad"]
        g = df[(df["CCTE"] == ccte) & (df["Provincia"] == prov) & (df["Localidad"] == loc)]
        td = calcular_tiempo_total_por_archivo(g)
        tiempos.append(format_timedelta_long(td))

    resumen["Tiempo trabajado"] = tiempos

    # Formatos finales
    if "Inicio" in resumen.columns:
        resumen["Inicio"] = pd.to_datetime(resumen["Inicio"], errors="coerce")
    if "Fin" in resumen.columns:
        resumen["Fin"] = pd.to_datetime(resumen["Fin"], errors="coerce")

    # Ordenar por pico max %
    resumen = resumen.sort_values(["Resultado_Max_%", "Resultado_Max_Vm"], ascending=False)

    # Renombres
    resumen = resumen.rename(columns={
        "Resultado_Max_Vm": "Resultado Max (V/m)",
        "Resultado_Max_%": "Resultado Max (%)",
    })

    return resumen


def render_resumen_general():
    st.header("📊 Resumen general de mediciones")
    render_active_filters_banner()

    df = st.session_state.get("tabla_maestra", pd.DataFrame()).copy()
    df = get_df_filtrado_global(df)
    if df is None or df.empty:
        st.info("Aún no hay datos cargados. Importá mediciones desde el sidebar.")
        return

    # Normalizar Resultado
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")

    # Controles de filtro en cascada
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

    # Cargar resumen precalculado
    resumen_db = load_resumen_from_cache()
    
    # Normalizar columnas si resumen_db existe
    if not resumen_db.empty:
        resumen_db = resumen_db.copy()
        resumen_db["CCTE"] = resumen_db["CCTE"].astype(str).str.strip()
        resumen_db["Provincia"] = resumen_db["Provincia"].astype(str).str.strip()
        resumen_db["Localidad"] = resumen_db["Localidad"].astype(str).str.strip()

    # CCTE: sin restricción (todas las opciones disponibles)
    with c1:
        ccte_sel = "Todos"
        if not resumen_db.empty and "CCTE" in resumen_db.columns:
            opciones_ccte = ["Todos"] + sorted(resumen_db["CCTE"].dropna().unique().tolist())
        elif "CCTE" in df.columns:
            opciones_ccte = ["Todos"] + sorted(df["CCTE"].dropna().astype(str).unique().tolist())
        else:
            opciones_ccte = ["Todos"]
        ccte_sel = st.selectbox("Filtrar CCTE", opciones_ccte, key="resumen_ccte")

    # PROVINCIA: filtrada por CCTE seleccionado
    with c2:
        prov_sel = "Todas"
        if ccte_sel != "Todos" and not resumen_db.empty:
            # Filtrar resumen_db por CCTE y sacar provincias disponibles
            df_ccte = resumen_db[resumen_db["CCTE"] == ccte_sel]
            opciones_prov = ["Todas"] + sorted(df_ccte["Provincia"].dropna().unique().tolist())
        elif not resumen_db.empty and "Provincia" in resumen_db.columns:
            opciones_prov = ["Todas"] + sorted(resumen_db["Provincia"].dropna().unique().tolist())
        elif "Provincia" in df.columns:
            opciones_prov = ["Todas"] + sorted(df["Provincia"].dropna().astype(str).unique().tolist())
        else:
            opciones_prov = ["Todas"]
        prov_sel = st.selectbox("Filtrar Provincia", opciones_prov, key="resumen_provincia")

    # LOCALIDAD: filtrada por CCTE y Provincia seleccionados
    with c3:
        loc_sel = "Todas"
        if not resumen_db.empty:
            df_filtered = resumen_db.copy()
            if ccte_sel != "Todos":
                df_filtered = df_filtered[df_filtered["CCTE"] == ccte_sel]
            if prov_sel != "Todas":
                df_filtered = df_filtered[df_filtered["Provincia"] == prov_sel]
            if not df_filtered.empty and "Localidad" in df_filtered.columns:
                opciones_loc = ["Todas"] + sorted(df_filtered["Localidad"].dropna().unique().tolist())
            else:
                opciones_loc = ["Todas"]
        else:
            opciones_loc = ["Todas"]
        loc_sel = st.selectbox("Filtrar Localidad", opciones_loc, key="resumen_localidad")

    # AÑO: independiente de los filtros en cascada
    with c4:
        anio_sel = "Todos"
        if "Fecha" in df.columns:
            _f = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
            anios_disp = sorted(_f.dt.year.dropna().astype(int).unique().tolist(), reverse=True)
            if anios_disp:
                opciones = ["Todos"] + [str(a) for a in anios_disp]
                anio_sel = st.selectbox("Filtrar Año", opciones, key="resumen_anio")

    # Si se pide filtrar por año, creamos df filtrado por año (no usamos cache)
    if anio_sel != "Todos":
        if "Fecha" in df.columns:
            _f = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
            df = df[_f.dt.year == int(anio_sel)].copy()

    # Si hay filtros globales activos, evitamos cache agregado (mezcla años/filtros).
    hay_filtros_globales = has_active_global_filters()

    # Si hay cache en DB y no se filtró por año local ni hay filtros globales, la usamos
    resumen = pd.DataFrame()
    if anio_sel == "Todos" and not resumen_db.empty and not hay_filtros_globales:
        resumen = resumen_db.copy()
        # Aplicar filtros en cascada
        if ccte_sel != "Todos":
            resumen = resumen[resumen["CCTE"] == ccte_sel]
        if prov_sel != "Todas":
            resumen = resumen[resumen["Provincia"] == prov_sel]
        if loc_sel != "Todas":
            resumen = resumen[resumen["Localidad"] == loc_sel]

        # Convertir segundos a texto legible
        if "TiempoTrabajadoSegundos" in resumen.columns:
            resumen["Tiempo trabajado"] = resumen["TiempoTrabajadoSegundos"].apply(
                lambda s: format_timedelta_long(pd.Timedelta(seconds=int(s))) if pd.notna(s) else "0 s"
            )

        # Renombrar columnas para compatibilidad con la vista
        resumen = resumen.rename(columns={
            "Resultado_Max_Vm": "Resultado Max (V/m)",
            "Resultado_Max_Pct": "Resultado Max (%)",
            "Expedientes": "N° Expediente",
            "Sondas": "Sonda utilizada",
            "FechaInicio": "Inicio",
            "FechaFin": "Fin",
        })

    # Si no usamos cache (anio filtrado o cache vacío), calculamos dinámicamente
    if resumen.empty:
        resumen = _calculate_resumen_optimized(df)

    if resumen.empty:
        st.warning("No se pudo generar el resumen.")
        return

    # Mostrar columnas en orden
    cols = [
        "CCTE", "Provincia", "Localidad",
        "Inicio", "Fin",
        "Mediciones",
        "Tiempo trabajado",
        "Resultado Max (V/m)",
        "Resultado Max (%)",
        "N° Expediente",
        "Sonda utilizada",
    ]

    # Asegurar que existan las columnas solicitadas
    cols = [c for c in cols if c in resumen.columns]

    st.dataframe(resumen[cols], width="stretch")