import pandas as pd
import streamlit as st

from utils.time_utils import (
    calcular_tiempo_total_por_archivo,
    format_timedelta_long,
    add_fechahora,
)


def render_gestion_localidades():
    st.header("📊 Gestión de Localidades")

    df_base = st.session_state.get("tabla_maestra", pd.DataFrame()).copy()

    columnas_necesarias = {"CCTE", "Provincia", "Localidad"}
    if df_base.empty or not columnas_necesarias.issubset(df_base.columns):
        st.info(
            "Todavía no hay datos suficientes (o faltan columnas CCTE/Provincia/Localidad) para gestionar localidades. "
            "Cargá mediciones nuevas."
        )
        df_filtrado_prov = pd.DataFrame()
        localidad_seleccionada = ""
        provincia_filtro = "Todas"
        ccte_filtro = "Todos"
    else:
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        with col1:
            lista_ccte = sorted(df_base["CCTE"].dropna().unique().tolist())
            ccte_filtro = st.selectbox("Filtrar CCTE", ["Todos"] + lista_ccte, key="gestion_ccte")
            df_filtrado_ccte = df_base.copy() if ccte_filtro == "Todos" else df_base[df_base["CCTE"] == ccte_filtro].copy()

        with col2:
            lista_prov = sorted(df_filtrado_ccte["Provincia"].dropna().unique().tolist())
            provincia_filtro = st.selectbox("Filtrar Provincia", ["Todas"] + lista_prov, key="gestion_provincia")
            df_filtrado_prov = df_filtrado_ccte.copy() if provincia_filtro == "Todas" else df_filtrado_ccte[df_filtrado_ccte["Provincia"] == provincia_filtro].copy()

        with col4:
            año_filtro = "Todos"
            if not df_filtrado_prov.empty and "Fecha" in df_filtrado_prov.columns:
                _años = pd.to_datetime(df_filtrado_prov["Fecha"], dayfirst=True, errors="coerce").dt.year
                df_filtrado_prov["_Año"] = _años
                años_disponibles = sorted(df_filtrado_prov["_Año"].dropna().astype(int).unique().tolist(), reverse=True)
                opciones_año = ["Todos"] + [str(a) for a in años_disponibles]
                año_filtro = st.selectbox("📅 Año", opciones_año, index=0, key="gestion_año")
                if año_filtro != "Todos":
                    df_filtrado_prov = df_filtrado_prov[df_filtrado_prov["_Año"] == int(año_filtro)]
                df_filtrado_prov = df_filtrado_prov.drop(columns=["_Año"])

        with col3:
            localidades_cargadas = df_filtrado_prov["Localidad"].dropna().unique().tolist() if not df_filtrado_prov.empty else []
            localidad_seleccionada = st.selectbox(
                "Seleccionar Localidad",
                [""] + sorted(localidades_cargadas),
                key="gestion_localidad"
            )

    # Subset final
    if localidad_seleccionada:
        df_localidad = df_filtrado_prov[df_filtrado_prov["Localidad"] == localidad_seleccionada].copy()
    else:
        df_localidad = df_filtrado_prov.copy()

    # Normalizar Resultado (por las dudas)
    if "Resultado" in df_localidad.columns:
        df_localidad["Resultado"] = pd.to_numeric(df_localidad["Resultado"], errors="coerce")

    # ✅ FechaHora robusta (parsea "20/03/2025" + "10:08:09 a.m.")
    df_localidad = add_fechahora(df_localidad, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")

    # Caption seguro (si está vacío, no rompe)
    if "FechaHora" in df_localidad.columns and not df_localidad.empty:
        faltan = int(df_localidad["FechaHora"].isna().sum())
        total = int(len(df_localidad))
        st.caption(f"FechaHora inválida: {faltan}/{total} ({(faltan/total*100 if total else 0):.1f}%)")

    # ---------------- Datos generales ----------------
    if localidad_seleccionada:
        provincia_real = (
            df_localidad["Provincia"].iloc[0]
            if "Provincia" in df_localidad.columns and not df_localidad.empty
            else "N/A"
        )
        titulo_scope = f"la localidad {localidad_seleccionada}, {provincia_real}"
    elif provincia_filtro != "Todas":
        titulo_scope = f"{provincia_filtro}"
    elif ccte_filtro != "Todos":
        titulo_scope = f"CCTE {ccte_filtro}"
    else:
        titulo_scope = "todo el país"

    st.subheader(f"Mediciones RNI de {titulo_scope}")

    tiempo_total_localidad = calcular_tiempo_total_por_archivo(df_localidad)
    total_puntos = len(df_localidad)
    max_resultado = df_localidad["Resultado"].max() if "Resultado" in df_localidad.columns else None
    max_resultado_pct = (max_resultado**2) / 3770 / 0.20021 * 100 if pd.notna(max_resultado) else None
    sondas = df_localidad["Sonda"].dropna().unique().tolist() if "Sonda" in df_localidad.columns else []

    st.write(f"Cantidad total de puntos medidos: {total_puntos}")
    st.write(f"Máximo Resultado (V/m): {max_resultado}")
    st.write(f"Máximo Resultado (%): {max_resultado_pct:.2f}" if max_resultado_pct is not None else "Máximo Resultado (%): N/A")
    st.write(f"Sonda utilizada: {', '.join(sondas) if sondas else 'N/A'}")
    st.write(f"Tiempo total de mediciones: {format_timedelta_long(tiempo_total_localidad)}")

    # ---------------- Resumen por día y mes ----------------
    if "FechaHora" not in df_localidad.columns or df_localidad.empty:
        return {
            "df_base": df_base,
            "df_filtrado_prov": df_filtrado_prov if "df_filtrado_prov" in locals() else pd.DataFrame(),
            "df_localidad": df_localidad,
            "localidad_seleccionada": localidad_seleccionada,
            "provincia_filtro": provincia_filtro,
            "ccte_filtro": ccte_filtro,
            "titulo_scope": titulo_scope,
            "max_resultado": max_resultado,
            "max_resultado_pct": max_resultado_pct,
        }

    df_localidad["FechaHora"] = pd.to_datetime(df_localidad["FechaHora"], errors="coerce")
    df_localidad = df_localidad.dropna(subset=["FechaHora"]).copy()
    if df_localidad.empty:
        st.warning("No se pudo armar FechaHora con los datos disponibles (Fecha/Hora vienen en formatos no parseables).")
        return {
            "df_base": df_base,
            "df_filtrado_prov": df_filtrado_prov if "df_filtrado_prov" in locals() else pd.DataFrame(),
            "df_localidad": df_localidad,
            "localidad_seleccionada": localidad_seleccionada,
            "provincia_filtro": provincia_filtro,
            "ccte_filtro": ccte_filtro,
            "titulo_scope": titulo_scope,
            "max_resultado": max_resultado,
            "max_resultado_pct": max_resultado_pct,
        }

    df_localidad["Fecha"] = df_localidad["FechaHora"].dt.date
    df_localidad["Mes"] = df_localidad["FechaHora"].dt.to_period("M").astype(str)

    # --- Resumen diario ---
    def resumen_por_dia(df_dia):
        tiempo_total = calcular_tiempo_total_por_archivo(df_dia)
        inicio_dt = df_dia["FechaHora"].min()
        fin_dt = df_dia["FechaHora"].max()
        return {
            "Hora de inicio": inicio_dt.strftime("%H:%M:%S") if pd.notna(inicio_dt) else "-",
            "Hora de fin": fin_dt.strftime("%H:%M:%S") if pd.notna(fin_dt) else "-",
            "Tiempo total trabajado": format_timedelta_long(tiempo_total),
            "Cantidad de puntos medidos": len(df_dia),
            "Localidades trabajadas (por día)": ", ".join(sorted(df_dia["Localidad"].dropna().unique())),
        }

    filas_resumen_dias = []
    for fecha, g_dia in df_localidad.groupby("Fecha"):
        info = resumen_por_dia(g_dia)
        info["Fecha de medición"] = fecha
        filas_resumen_dias.append(info)

    resumen_dias = pd.DataFrame(filas_resumen_dias)
    if not resumen_dias.empty:
        resumen_dias = resumen_dias[
            [
                "Fecha de medición",
                "Hora de inicio",
                "Hora de fin",
                "Tiempo total trabajado",
                "Cantidad de puntos medidos",
                "Localidades trabajadas (por día)",
            ]
        ]

    # --- Resumen mensual base ---
    resumen_mensual = df_localidad.groupby("Mes").agg({
        "FechaHora": ["min", "max"],
        "Localidad": lambda x: ", ".join(sorted(x.dropna().unique())),
        "Resultado": "count"
    }).reset_index()
    resumen_mensual.columns = ["Mes", "Hora inicio", "Hora fin", "Localidades trabajadas", "Cantidad puntos"]

    # Horas trabajadas por mes (NUM + TEXTO)
    def td_to_hours(td):
        try:
            return float(td.total_seconds()) / 3600.0
        except Exception:
            return 0.0

    filas_tiempo_mes = []
    for mes, g_mes in df_localidad.groupby("Mes"):
        td_mes = calcular_tiempo_total_por_archivo(g_mes)
        filas_tiempo_mes.append({
            "Mes": str(mes),
            "Horas trabajadas num": td_to_hours(td_mes),
            "Horas trabajadas": format_timedelta_long(td_mes),
        })
    tiempo_por_mes = pd.DataFrame(filas_tiempo_mes)

    resumen_mensual = resumen_mensual.merge(tiempo_por_mes, on="Mes", how="left")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📅 Resumen Diario", "🗓️ Resumen Mensual", "📊 Gráfico"])

    with tab1:
        st.markdown(f"### ⏱️ Tiempo trabajado por día en {titulo_scope}")
        st.dataframe(resumen_dias, width="stretch")

    with tab2:
        st.markdown(f"### 📅 Mediciones Totales por mes en {titulo_scope}")
        st.dataframe(resumen_mensual, width="stretch")

    with tab3:
        if not resumen_mensual.empty:
            st.markdown(f"### 📊 Gráfico mensual de mediciones y tiempo trabajado en {titulo_scope}")

            import plotly.graph_objects as go

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=resumen_mensual["Mes"].astype(str),
                y=resumen_mensual["Cantidad puntos"],
                name="Cantidad puntos",
                yaxis="y1",
                text=resumen_mensual["Cantidad puntos"],
                textposition="auto",
                hovertext=resumen_mensual["Localidades trabajadas"],
                hovertemplate="<b>%{x}</b><br>Puntos: %{y}<br>Localidades: %{hovertext}"
            ))

            fig.add_trace(go.Scatter(
                x=resumen_mensual["Mes"].astype(str),
                y=resumen_mensual["Horas trabajadas num"].fillna(0),
                name="Horas trabajadas",
                yaxis="y2",
                mode="lines+markers",
            ))

            fig.update_layout(
                xaxis=dict(title="Mes"),
                yaxis=dict(title="Cantidad de puntos", side="left"),
                yaxis2=dict(title="Horas trabajadas", overlaying="y", side="right"),
                legend=dict(x=0.01, y=0.99),
                template="plotly_white",
                height=450
            )

            st.plotly_chart(fig, width="stretch")

    return {
        "df_base": df_base,
        "df_filtrado_prov": df_filtrado_prov if "df_filtrado_prov" in locals() else pd.DataFrame(),
        "df_localidad": df_localidad,
        "localidad_seleccionada": localidad_seleccionada,
        "provincia_filtro": provincia_filtro,
        "ccte_filtro": ccte_filtro,
        "titulo_scope": titulo_scope,
        "max_resultado": max_resultado,
        "max_resultado_pct": max_resultado_pct,
    }
