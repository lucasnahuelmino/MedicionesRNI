# sections/graficos.py
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from utils.time_utils import add_fechahora, calcular_tiempo_total_por_archivo
from state import get_df_filtrado_global
from state import global_filters_human_label

def render_graficos():
    st.header("📊 Tablero de comando")
    st.caption(global_filters_human_label())

    # 1) Traemos la tabla y aplicamos filtro GLOBAL (Año/CCTE/Provincia)
    df_all = st.session_state.get("tabla_maestra", pd.DataFrame())
    if df_all is None or df_all.empty:
        st.info("No hay datos cargados todavía.")
        return

    df0 = get_df_filtrado_global(df_all).copy()
    if df0.empty:
        st.warning("Con los filtros globales actuales no quedaron datos para graficar.")
        return

    # =========================
    # Controles de performance
    # =========================
    with st.expander("⚙️ Rendimiento (opcional)", expanded=False):
        MAX_FILAS = st.number_input(
            "Máx. filas para gráficos",
            min_value=50_000,
            max_value=2_000_000,
            value=400_000,
            step=50_000,
        )
        usar_muestra = st.toggle("Muestrear si excede", value=True)

    # =========================
    # Helpers
    # =========================
    def _to_num(s):
        return pd.to_numeric(s, errors="coerce")

    def _hours(td):
        try:
            return float(td.total_seconds()) / 3600.0
        except Exception:
            return 0.0

    # =========================
    # Preprocesado mínimo
    # =========================
    # Resultado numérico
    if "Resultado" in df0.columns:
        df0["Resultado"] = _to_num(df0["Resultado"])
    else:
        df0["Resultado"] = np.nan

    # FechaHora robusta si existen Fecha y Hora
    if "Fecha" in df0.columns and "Hora" in df0.columns:
        df0 = add_fechahora(df0, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
    else:
        df0["FechaHora"] = pd.NaT

    fh = pd.to_datetime(df0["FechaHora"], errors="coerce")
    df0["Fecha_dt"] = fh.dt.date
    df0["Mes"] = fh.dt.to_period("M").astype("string")

    # Resultado %
    df0["Resultado_pct"] = np.where(
        df0["Resultado"].notna(),
        (df0["Resultado"] ** 2) / 3770 / 0.20021 * 100,
        np.nan,
    )

    # Muestreo (si está gigante)
    df = df0
    if usar_muestra and len(df) > int(MAX_FILAS):
        df = df.sample(n=int(MAX_FILAS), random_state=42)
        st.info(
            f"Mostrando una muestra de {int(MAX_FILAS):,} filas para mantener fluidez."
            .replace(",", ".")
        )

    st.caption(f"Filas en análisis (con filtros globales): {len(df):,}".replace(",", "."))

    # =========================
    # KPIs
    # =========================
    total_reg = int(len(df))
    total_localidades = int(df["Localidad"].dropna().nunique()) if "Localidad" in df.columns else 0
    total_provincias = int(df["Provincia"].dropna().nunique()) if "Provincia" in df.columns else 0
    total_ccte = int(df["CCTE"].dropna().nunique()) if "CCTE" in df.columns else 0

    dias_medidos = int(df["Fecha_dt"].dropna().nunique()) if df["Fecha_dt"].notna().any() else 0
    horas_total = _hours(calcular_tiempo_total_por_archivo(df)) if total_reg else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Puntos", f"{total_reg:,}".replace(",", "."))
    k2.metric("Localidades", f"{total_localidades:,}".replace(",", "."))
    k3.metric("Provincias", f"{total_provincias:,}".replace(",", "."))
    k4.metric("CCTEs", f"{total_ccte:,}".replace(",", "."))
    k5.metric("Horas (estimadas)", f"{horas_total:.2f}")

    # =========================
    # Tabs del tablero
    # =========================
    tabs = st.tabs(["🧭 Operativo", "📈 Resultados", "🔥 Hotspots", "🧪 Calidad de datos"])

    # -------------------------------------------------
    # TAB 1: OPERATIVO
    # -------------------------------------------------
    with tabs[0]:
        st.markdown("#### Operación y cobertura")

        c1, c2 = st.columns(2)

        # Puntos por CCTE
        with c1:
            if "CCTE" in df.columns and df["CCTE"].notna().any():
                df_pie = df.groupby("CCTE").size().reset_index(name="Puntos")
                fig = px.pie(df_pie, names="CCTE", values="Puntos", title="Puntos medidos por CCTE")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Falta CCTE para este gráfico.")

        # Localidades por Provincia y CCTE
        with c2:
            if {"Provincia", "CCTE", "Localidad"}.issubset(df.columns):
                res = (
                    df.groupby(["Provincia", "CCTE"])["Localidad"]
                    .nunique()
                    .reset_index(name="Localidades")
                )
                fig = px.bar(
                    res,
                    x="Provincia",
                    y="Localidades",
                    color="CCTE",
                    barmode="group",
                    text="Localidades",
                    title="Localidades cubiertas por Provincia y CCTE",
                )
                fig.update_layout(xaxis={"categoryorder": "total descending"})
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Faltan columnas Provincia/CCTE/Localidad.")

        st.markdown("---")

        c3, c4 = st.columns(2)

        # Horas trabajadas por CCTE
        with c3:
            if "CCTE" in df.columns and df["CCTE"].notna().any():
                filas = []
                for ccte, g in df.groupby("CCTE"):
                    td = calcular_tiempo_total_por_archivo(g)
                    filas.append({"CCTE": str(ccte), "Horas": round(_hours(td), 2)})

                df_h = pd.DataFrame(filas).sort_values("Horas", ascending=False)
                fig = px.bar(df_h, x="CCTE", y="Horas", text="Horas", title="Horas trabajadas por CCTE")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No se puede calcular horas por CCTE.")

        # Días con medición por CCTE
        with c4:
            if "CCTE" in df.columns and df["Fecha_dt"].notna().any():
                dd = (
                    df.dropna(subset=["Fecha_dt"])
                    .groupby("CCTE")["Fecha_dt"].nunique()
                    .reset_index(name="Días con medición")
                    .sort_values("Días con medición", ascending=False)
                )
                fig = px.bar(dd, x="CCTE", y="Días con medición", text="Días con medición", title="Días con medición por CCTE")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No hay Fecha/Hora parseable para calcular días.")

        st.markdown("---")

        # Tendencia mensual
        if df["Mes"].notna().any():
            mes = df.groupby("Mes").size().reset_index(name="Puntos").sort_values("Mes")
            fig = px.line(mes, x="Mes", y="Puntos", markers=True, title="Tendencia mensual: puntos medidos")
            st.plotly_chart(fig, width="stretch")

    # -------------------------------------------------
    # TAB 2: RESULTADOS
    # -------------------------------------------------
    with tabs[1]:
        st.markdown("#### Niveles medidos (V/m y %)")

        c1, c2 = st.columns(2)

        with c1:
            base = df.dropna(subset=["Resultado"])
            if not base.empty:
                fig = px.histogram(base, x="Resultado", nbins=45, title="Distribución de Resultado (V/m)")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No hay Resultado numérico para graficar.")

        with c2:
            basep = df.dropna(subset=["Resultado_pct"])
            if not basep.empty:
                fig = px.histogram(basep, x="Resultado_pct", nbins=45, title="Distribución de Resultado (%)")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No hay Resultado % para graficar.")

        st.markdown("---")

        # Boxplot por CCTE (Resultado %)
        if "CCTE" in df.columns:
            basep = df.dropna(subset=["Resultado_pct", "CCTE"])
            if not basep.empty:
                fig = px.box(basep, x="CCTE", y="Resultado_pct", points="outliers", title="Outliers (Resultado %) por CCTE")
                st.plotly_chart(fig, width="stretch")

        # Top picos
        st.markdown("#### ⚡ Top picos (puntos individuales)")
        top = df.dropna(subset=["Resultado"]).sort_values("Resultado", ascending=False).head(10).copy()
        if not top.empty:
            top["Resultado %"] = top["Resultado_pct"].round(2)
            top = top.rename(columns={"Resultado": "Resultado V/m"})
            cols = [c for c in ["CCTE", "Provincia", "Localidad", "Resultado V/m", "Resultado %", "Expediente", "Nombre Archivo"] if c in top.columns]
            st.dataframe(top[cols].reset_index(drop=True), width="stretch")

    # -------------------------------------------------
    # TAB 3: HOTSPOTS
    # -------------------------------------------------
    with tabs[2]:
        st.markdown("#### Localidades “más altas” (por máximo registrado)")

        if "Localidad" not in df.columns:
            st.info("Falta columna Localidad.")
        else:
            base = df.dropna(subset=["Localidad", "Resultado_pct"]).copy()
            if base.empty:
                st.info("No hay datos suficientes para hotspots.")
            else:
                agg = (
                    base.groupby(["Localidad"], as_index=False)
                    .agg(
                        MaxPct=("Resultado_pct", "max"),
                        MaxVm=("Resultado", "max"),
                        CCTE=("CCTE", lambda x: ", ".join(sorted(pd.Series(x).dropna().astype(str).unique())[:3])),
                        Provincia=("Provincia", lambda x: ", ".join(sorted(pd.Series(x).dropna().astype(str).unique())[:3])),
                        Puntos=("Resultado_pct", "count"),
                    )
                    .sort_values("MaxPct", ascending=False)
                )

                topN = st.slider("Top N localidades", 5, 50, 10, step=5)
                view = agg.head(topN).copy()
                view["MaxPct"] = view["MaxPct"].round(2)
                view["MaxVm"] = view["MaxVm"].round(2)

                st.dataframe(view, width="stretch")

                fig = px.bar(
                    view.sort_values("MaxPct"),
                    x="MaxPct",
                    y="Localidad",
                    orientation="h",
                    title=f"Top {topN} localidades por máximo Resultado (%)",
                    hover_data=["Provincia", "CCTE", "Puntos", "MaxVm"],
                )
                st.plotly_chart(fig, width="stretch")

    # -------------------------------------------------
    # TAB 4: CALIDAD DE DATOS
    # -------------------------------------------------
    with tabs[3]:
        st.markdown("#### Salud del dataset (para evitar fantasmas)")

        total = len(df)

        miss_fh = int(pd.to_datetime(df["FechaHora"], errors="coerce").isna().sum()) if "FechaHora" in df.columns else total
        miss_lat = int(pd.to_numeric(df.get("Lat", pd.Series([np.nan] * total)), errors="coerce").isna().sum()) if total else 0
        miss_lon = int(pd.to_numeric(df.get("Lon", pd.Series([np.nan] * total)), errors="coerce").isna().sum()) if total else 0
        miss_res = int(pd.to_numeric(df.get("Resultado", pd.Series([np.nan] * total)), errors="coerce").isna().sum()) if total else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("FechaHora inválida", f"{miss_fh}/{total}".replace(",", "."))
        c2.metric("Lat faltante", f"{miss_lat}/{total}".replace(",", "."))
        c3.metric("Lon faltante", f"{miss_lon}/{total}".replace(",", "."))
        c4.metric("Resultado inválido", f"{miss_res}/{total}".replace(",", "."))

        st.markdown("---")

        # Duplicados de coordenadas
        if {"Lat", "Lon"}.issubset(df.columns):
            tmp = df.copy()
            tmp["Lat_n"] = pd.to_numeric(tmp["Lat"], errors="coerce")
            tmp["Lon_n"] = pd.to_numeric(tmp["Lon"], errors="coerce")
            tmp = tmp.dropna(subset=["Lat_n", "Lon_n"])
            if not tmp.empty:
                dup = tmp.duplicated(subset=["Lat_n", "Lon_n"]).sum()
                st.write(f"Coordenadas repetidas (Lat/Lon): **{int(dup):,}**".replace(",", "."))
                rep = (
                    tmp.groupby(["Lat_n", "Lon_n"]).size()
                    .reset_index(name="Repeticiones")
                    .sort_values("Repeticiones", ascending=False)
                    .head(10)
                )
                st.dataframe(rep, width="stretch")
            else:
                st.info("No hay coordenadas válidas para analizar duplicados.")
