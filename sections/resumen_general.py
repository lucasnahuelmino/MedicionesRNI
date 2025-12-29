from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.time_utils import (
    add_fechahora,
    calcular_tiempo_total_por_archivo,
    format_timedelta_long,
)

# Constante para % (la misma que venís usando)
K_DEN = 3770 * 0.20021


def render_resumen_general():
    st.header("📊 Resumen general de mediciones")

    df = st.session_state.get("tabla_maestra", pd.DataFrame()).copy()
    if df.empty:
        st.info("Aún no hay datos cargados. Importá mediciones desde el sidebar.")
        return

    # --------- Normalizaciones mínimas ---------
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")

    # --------- Filtros previos ---------
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        ccte_sel = "Todos"
        if "CCTE" in df.columns:
            opciones = ["Todos"] + sorted(df["CCTE"].dropna().unique().tolist())
            ccte_sel = st.selectbox("Filtrar CCTE", opciones, key="resumen_ccte")
            if ccte_sel != "Todos":
                df = df[df["CCTE"] == ccte_sel].copy()

    with c2:
        prov_sel = "Todas"
        if "Provincia" in df.columns:
            opciones = ["Todas"] + sorted(df["Provincia"].dropna().unique().tolist())
            prov_sel = st.selectbox("Filtrar Provincia", opciones, key="resumen_provincia")
            if prov_sel != "Todas":
                df = df[df["Provincia"] == prov_sel].copy()

    with c3:
        anio_sel = "Todos"
        if "Fecha" in df.columns:
            _f = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
            anios_disp = sorted(_f.dt.year.dropna().astype(int).unique().tolist(), reverse=True)
            if anios_disp:
                opciones = ["Todos"] + [str(a) for a in anios_disp]
                anio_sel = st.selectbox("Filtrar Año", opciones, key="resumen_anio")
                if anio_sel != "Todos":
                    df = df[_f.dt.year == int(anio_sel)].copy()

    if df.empty:
        st.warning("Con esos filtros no quedaron registros.")
        return

    # --------- Construir FechaHora robusta (sin apply por fila) ---------
    df = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")

    valid_fh = df["FechaHora"].notna().sum() if "FechaHora" in df.columns else 0
    st.caption(
        f"FechaHora válida: {valid_fh:,}/{len(df):,} "
        f"({(valid_fh/len(df)*100 if len(df) else 0):.1f}%)"
        .replace(",", ".")
    )

    # --------- Resumen por localidad (vectorizado y con bucles chicos) ---------
    # Columnas mínimas para agrupar
    needed = ["CCTE", "Provincia", "Localidad"]
    if not all(c in df.columns for c in needed):
        st.error("Faltan columnas necesarias (CCTE/Provincia/Localidad) en la tabla.")
        return

    # Base de agregados rápidos
    gb = df.groupby(["CCTE", "Provincia", "Localidad"], dropna=False)

    resumen = gb.agg(
        Mediciones=("Resultado", "size"),
        Resultado_Max_Vm=("Resultado", "max"),
        Inicio=("FechaHora", "min"),
        Fin=("FechaHora", "max"),
    ).reset_index()

    # % del máximo
    resumen["Resultado_Max_%"] = (resumen["Resultado_Max_Vm"] ** 2) / K_DEN * 100
    resumen.loc[resumen["Resultado_Max_Vm"].isna(), "Resultado_Max_%"] = pd.NA

    # Expedientes / Sondas (esto es lo más “caro”; lo hago controlado)
    if "Expediente" in df.columns:
        exp_map = gb["Expediente"].apply(
            lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(exp_map.rename("N° Expediente"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["N° Expediente"] = ""

    if "Sonda" in df.columns:
        sonda_map = gb["Sonda"].apply(
            lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
        resumen = resumen.merge(sonda_map.rename("Sonda utilizada"), on=["CCTE", "Provincia", "Localidad"], how="left")
    else:
        resumen["Sonda utilizada"] = ""

    # Tiempo trabajado por localidad
    # (este loop es por cantidad de localidades, no por filas -> mucho más liviano)
    tiempos = []
    for _, row in resumen[["CCTE", "Provincia", "Localidad"]].iterrows():
        ccte, prov, loc = row["CCTE"], row["Provincia"], row["Localidad"]
        g = df[(df["CCTE"] == ccte) & (df["Provincia"] == prov) & (df["Localidad"] == loc)]
        td = calcular_tiempo_total_por_archivo(g)
        tiempos.append(format_timedelta_long(td))

    resumen["Tiempo trabajado"] = tiempos

    # Formatos finales
    # (Inicio/Fin pueden quedar NaT si no hubo parseo de fecha/hora)
    if "Inicio" in resumen.columns:
        resumen["Inicio"] = pd.to_datetime(resumen["Inicio"], errors="coerce")
    if "Fin" in resumen.columns:
        resumen["Fin"] = pd.to_datetime(resumen["Fin"], errors="coerce")

    # Ordenar por pico max % (o V/m) descendente
    resumen = resumen.sort_values(["Resultado_Max_%", "Resultado_Max_Vm"], ascending=False)

    # Renombres “lindos”
    resumen = resumen.rename(columns={
        "Resultado_Max_Vm": "Resultado Max (V/m)",
        "Resultado_Max_%": "Resultado Max (%)",
    })

    # Mostrar
    st.dataframe(
        resumen[[
            "CCTE", "Provincia", "Localidad",
            "Inicio", "Fin",
            "Mediciones",
            "Tiempo trabajado",
            "Resultado Max (V/m)",
            "Resultado Max (%)",
            "N° Expediente",
            "Sonda utilizada",
        ]],
        width="stretch"
    )
