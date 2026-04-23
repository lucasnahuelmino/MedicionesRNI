# sections/graficos.py
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from state import get_df_filtrado_global
from utils.time_utils import add_fechahora, calcular_tiempo_total_por_archivo

from db.sqlite_store import (
    load_graficos_ccte_summary,
    load_graficos_provincia_ccte,
    load_graficos_mensual,
    load_graficos_hotspots,
)

def render_graficos():
    st.header("📊 Tablero de comando")


    # 1) Cargar datos precacheados desde DB (sin cálculos en tiempo real)
    df_ccte = load_graficos_ccte_summary()
    df_prov_ccte = load_graficos_provincia_ccte()
    df_mensual = load_graficos_mensual()
    df_hotspots = load_graficos_hotspots()

    gf = st.session_state.get("global_filters", {})
    hay_filtros_globales = bool(gf.get("ccte") or gf.get("provincia") or (gf.get("anio") and gf.get("anio") != "Todos"))

    if hay_filtros_globales:
        df_all = st.session_state.get("tabla_maestra", pd.DataFrame())
        df_filtered = get_df_filtrado_global(df_all).copy() if df_all is not None else pd.DataFrame()

        if not df_filtered.empty:
            if "Resultado" in df_filtered.columns:
                df_filtered["Resultado"] = pd.to_numeric(df_filtered["Resultado"], errors="coerce")

            df_with_time = add_fechahora(df_filtered.copy(), fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
            df_with_time["Mes"] = pd.to_datetime(df_with_time["FechaHora"], errors="coerce").dt.to_period("M").astype(str)

            # CCTE summary
            ccte_rows = []
            for ccte, g in df_with_time.groupby("CCTE", dropna=False):
                if pd.isna(ccte):
                    continue
                td = calcular_tiempo_total_por_archivo(g)
                ccte_rows.append(
                    {
                        "CCTE": str(ccte),
                        "Puntos": int(len(g)),
                        "HorasSegundos": int(td.total_seconds()),
                        "DiasConMedicion": int(pd.to_datetime(g["FechaHora"], errors="coerce").dt.date.nunique()),
                    }
                )
            df_ccte = pd.DataFrame(ccte_rows)

            # Provincia-CCTE
            if all(c in df_with_time.columns for c in ["Provincia", "CCTE", "Localidad"]):
                df_prov_ccte = (
                    df_with_time.groupby(["Provincia", "CCTE"], dropna=False)["Localidad"]
                    .nunique()
                    .reset_index(name="NumLocalidades")
                )
            else:
                df_prov_ccte = pd.DataFrame()

            # Mensual
            if "Mes" in df_with_time.columns:
                df_mensual = df_with_time.groupby("Mes", dropna=False).size().reset_index(name="Puntos")
                df_mensual = df_mensual[df_mensual["Mes"].notna()]
                df_mensual = df_mensual.sort_values("Mes")
            else:
                df_mensual = pd.DataFrame()

            # Hotspots
            if "Resultado" in df_with_time.columns and "Localidad" in df_with_time.columns:
                df_hot = df_with_time.dropna(subset=["Resultado", "Localidad"]).copy()
                if not df_hot.empty:
                    idx = df_hot.groupby("Localidad")["Resultado"].idxmax()
                    df_hotspots = df_hot.loc[idx, ["Localidad", "Provincia", "CCTE", "Resultado"]].copy()
                    df_hotspots = df_hotspots.rename(columns={"Resultado": "ResultadoMaxVm"})
                    df_hotspots["ResultadoMaxPct"] = (df_hotspots["ResultadoMaxVm"] ** 2) / 3770 / 0.20021 * 100
                    puntos_loc = df_hot.groupby("Localidad").size().rename("Puntos")
                    df_hotspots = df_hotspots.merge(puntos_loc, on="Localidad", how="left")
                else:
                    df_hotspots = pd.DataFrame()
            else:
                df_hotspots = pd.DataFrame()
    
    if df_ccte.empty and df_prov_ccte.empty and df_mensual.empty:
        st.info("No hay datos de graficos cacheados. Importa mediciones para generar cache.")
        return

    # =========================
    # Helpers
    # =========================
    def _hours(segs):
        try:
            return float(segs) / 3600.0
        except Exception:
            return 0.0

    # =========================
    # KPIs (desde cache)
    # =========================
    total_reg = int(df_ccte["Puntos"].sum()) if not df_ccte.empty else 0
    total_localidades = int(df_hotspots["Localidad"].nunique()) if not df_hotspots.empty else 0
    total_provincias = int(df_prov_ccte["Provincia"].nunique()) if not df_prov_ccte.empty else 0
    total_ccte = int(df_ccte["CCTE"].nunique()) if not df_ccte.empty else 0
    horas_total = _hours(df_ccte["HorasSegundos"].sum()) if not df_ccte.empty else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Puntos", f"{total_reg:,}".replace(",", "."))
    k2.metric("Localidades", f"{total_localidades:,}".replace(",", "."))
    k3.metric("Provincias", f"{total_provincias:,}".replace(",", "."))
    k4.metric("CCTEs", f"{total_ccte:,}".replace(",", "."))
    k5.metric("Horas (estimadas)", f"{horas_total:.2f}")

    # =========================
    # Tabs del tablero
    # =========================
    tabs = st.tabs(["Operativo", "Resultados"])

    # -------------------------------------------------
    # TAB 1: OPERATIVO
    # -------------------------------------------------
    with tabs[0]:
        st.markdown("#### Operacion y cobertura")

        c1, c2 = st.columns(2)

        # Puntos por CCTE (desde cache)
        with c1:
            if not df_ccte.empty:
                fig = px.pie(df_ccte, names="CCTE", values="Puntos", title="Puntos medidos por CCTE")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Sin datos para este grafico.")

        # Localidades por Provincia y CCTE (desde cache)
        with c2:
            if not df_prov_ccte.empty:
                fig = px.bar(
                    df_prov_ccte,
                    x="Provincia",
                    y="NumLocalidades",
                    color="CCTE",
                    barmode="group",
                    text="NumLocalidades",
                    title="Localidades cubiertas por Provincia y CCTE",
                )
                fig.update_layout(xaxis={"categoryorder": "total descending"})
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Sin datos para este grafico.")

        st.markdown("---")

        c3, c4 = st.columns(2)

        # Horas trabajadas por CCTE (desde cache)
        with c3:
            if not df_ccte.empty:
                df_h = df_ccte[["CCTE", "HorasSegundos"]].copy()
                df_h["Horas"] = df_h["HorasSegundos"].apply(_hours)
                df_h = df_h.sort_values("Horas", ascending=False)
                fig = px.bar(df_h, x="CCTE", y="Horas", text="Horas", title="Horas trabajadas por CCTE")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Sin datos disponibles.")

        # Dias con medicion por CCTE (desde cache)
        with c4:
            if not df_ccte.empty:
                df_d = df_ccte[["CCTE", "DiasConMedicion"]].sort_values("DiasConMedicion", ascending=False)
                fig = px.bar(df_d, x="CCTE", y="DiasConMedicion", text="DiasConMedicion", title="Dias con medicion por CCTE")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Sin datos disponibles.")

        st.markdown("---")

        # Tendencia mensual (desde cache)
        if not df_mensual.empty:
            fig = px.line(df_mensual, x="Mes", y="Puntos", markers=True, title="Tendencia mensual: puntos medidos")
            st.plotly_chart(fig, width='stretch')

    # -------------------------------------------------
    # TAB 2: RESULTADOS
    # -------------------------------------------------
    with tabs[1]:
        st.markdown("#### Niveles medidos y picos")
        
        # Para distribuciones, cargar datos completos (necesario para histogramas)
        df_all = st.session_state.get("tabla_maestra", pd.DataFrame())
        if df_all is None or df_all.empty:
            st.info("No hay datos cargados para ver distribuciones detalladas.")
        else:
            df_filtered = get_df_filtrado_global(df_all).copy()
            if not df_filtered.empty:
                # Normalizar Resultado
                if "Resultado" in df_filtered.columns:
                    df_filtered["Resultado"] = pd.to_numeric(df_filtered["Resultado"], errors="coerce")
                
                # Resultado %
                df_filtered["Resultado_pct"] = np.where(
                    df_filtered["Resultado"].notna(),
                    (df_filtered["Resultado"] ** 2) / 3770 / 0.20021 * 100,
                    np.nan,
                )
                
                c1, c2 = st.columns(2)
                
                with c1:
                    base = df_filtered.dropna(subset=["Resultado"])
                    if not base.empty:
                        fig = px.histogram(base, x="Resultado", nbins=45, title="Distribucion de Resultado (V/m)")
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.info("Sin datos numericos.")
                
                with c2:
                    basep = df_filtered.dropna(subset=["Resultado_pct"])
                    if not basep.empty:
                        fig = px.histogram(basep, x="Resultado_pct", nbins=45, title="Distribucion de Resultado (%)")
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.info("Sin datos %.")
                
                st.markdown("---")
                
                # Boxplot por CCTE (Resultado %)
                if "CCTE" in df_filtered.columns:
                    basep = df_filtered.dropna(subset=["Resultado_pct", "CCTE"])
                    if not basep.empty:
                        fig = px.box(basep, x="CCTE", y="Resultado_pct", points="outliers", title="Outliers (Resultado %) por CCTE")
                        st.plotly_chart(fig, width='stretch')
                
                # Top picos
                st.markdown("#### Top 10 picos (puntos individuales)")
                top = df_filtered.dropna(subset=["Resultado"]).sort_values("Resultado", ascending=False).head(10).copy()
                if not top.empty:
                    top["Resultado %"] = top["Resultado_pct"].round(2)
                    top = top.rename(columns={"Resultado": "Resultado V/m"})
                    cols = [c for c in ["CCTE", "Provincia", "Localidad", "Resultado V/m", "Resultado %", "Expediente", "Nombre Archivo"] if c in top.columns]
                    st.dataframe(top[cols].reset_index(drop=True), width='stretch')

    