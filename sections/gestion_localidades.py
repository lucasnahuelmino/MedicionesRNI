import pandas as pd
import streamlit as st

from utils.time_utils import (
    calcular_tiempo_total_por_archivo,
    format_timedelta_long,
    add_fechahora,
)
from db.sqlite_store import load_resumen_from_cache, load_tabla_maestra_from_db
from state import get_df_filtrado_global, has_active_global_filters, render_active_filters_banner


def render_gestion_localidades():
    st.header("📊 Gestión de Localidades")
    render_active_filters_banner()

    df_tabla_maestra = load_tabla_maestra_from_db()
    df_tabla_maestra = get_df_filtrado_global(df_tabla_maestra)

    # Cargar resumen desde cache (evita recalculos)
    # Nota: si el cache está incompleto (p.ej. no incluye ciertas provincias), la UI no mostrará localidades.
    # Para evitar ese problema, en esta sección recalculamos desde la tabla maestra salvo que el cache tenga datos.
    resumen_db = load_resumen_from_cache()

    # Normalizar columnas si resumen existe
    if not resumen_db.empty:
        resumen_db = resumen_db.copy()
        resumen_db["CCTE"] = resumen_db["CCTE"].astype(str).str.strip()
        resumen_db["Provincia"] = resumen_db["Provincia"].astype(str).str.strip()
        resumen_db["Localidad"] = resumen_db["Localidad"].astype(str).str.strip()


    hay_filtros_globales = has_active_global_filters()

    if hay_filtros_globales:
        if df_tabla_maestra is None or df_tabla_maestra.empty:
            resumen_db = pd.DataFrame()
        else:
            df_tmp = df_tabla_maestra.copy()
            if "Resultado" in df_tmp.columns:
                df_tmp["Resultado"] = pd.to_numeric(df_tmp["Resultado"], errors="coerce")
            df_tmp = add_fechahora(df_tmp, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")

            gb = df_tmp.groupby(["CCTE", "Provincia", "Localidad"], dropna=False)
            resumen_db = gb.agg(
                Mediciones=("Resultado", "size"),
                Resultado_Max_Vm=("Resultado", "max"),
                FechaInicio=("FechaHora", "min"),
                FechaFin=("FechaHora", "max"),
            ).reset_index()

            resumen_db["Resultado_Max_Pct"] = (resumen_db["Resultado_Max_Vm"] ** 2) / (3770 * 0.20021) * 100
            resumen_db.loc[resumen_db["Resultado_Max_Vm"].isna(), "Resultado_Max_Pct"] = None

            exp_map = gb["Expediente"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str))))) if "Expediente" in df_tmp.columns else None
            sond_map = gb["Sonda"].apply(lambda x: ", ".join(sorted(set(x.dropna().astype(str))))) if "Sonda" in df_tmp.columns else None

            if exp_map is not None:
                resumen_db = resumen_db.merge(exp_map.rename("Expedientes"), on=["CCTE", "Provincia", "Localidad"], how="left")
            else:
                resumen_db["Expedientes"] = ""
            if sond_map is not None:
                resumen_db = resumen_db.merge(sond_map.rename("Sondas"), on=["CCTE", "Provincia", "Localidad"], how="left")
            else:
                resumen_db["Sondas"] = ""

            tiempos_seg = []
            for _, row in resumen_db[["CCTE", "Provincia", "Localidad"]].iterrows():
                g = df_tmp[
                    (df_tmp["CCTE"] == row["CCTE"])
                    & (df_tmp["Provincia"] == row["Provincia"])
                    & (df_tmp["Localidad"] == row["Localidad"])
                ]
                td = calcular_tiempo_total_por_archivo(g)
                try:
                    tiempos_seg.append(int(td.total_seconds()))
                except Exception:
                    tiempos_seg.append(0)
            resumen_db["TiempoTrabajadoSegundos"] = tiempos_seg

    # Contexto a retornar
    ctx = {
        "localidad_seleccionada": None,
        "df_localidad": None,
        "max_resultado_pct": None,
    }

    if resumen_db.empty:
        st.info(
            "No hay datos disponibles en el resumen. "
            "Cargá mediciones nuevas desde la sección de Carga de Excel."
        )
        return ctx

    # Filtros en cascada usando la tabla resumen
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        lista_ccte = sorted(resumen_db["CCTE"].dropna().unique().tolist())
        ccte_filtro = st.selectbox("Filtrar CCTE", ["Todos"] + lista_ccte, key="gestion_ccte")
        if ccte_filtro != "Todos":
            resumen_filtrado = resumen_db[resumen_db["CCTE"] == ccte_filtro].copy()
        else:
            resumen_filtrado = resumen_db.copy()

    with col2:
        lista_prov = sorted(resumen_filtrado["Provincia"].dropna().unique().tolist())
        provincia_filtro = st.selectbox("Filtrar Provincia", ["Todas"] + lista_prov, key="gestion_provincia")
        if provincia_filtro != "Todas":
            resumen_filtrado = resumen_filtrado[resumen_filtrado["Provincia"] == provincia_filtro].copy()

    with col3:
        localidades_disponibles = sorted(resumen_filtrado["Localidad"].dropna().unique().tolist())
        localidad_seleccionada = st.selectbox(
            "Seleccionar Localidad",
            [""] + localidades_disponibles,
            key="gestion_localidad"
        )

    with col4:
        st.write("")  # Placeholder para alineamiento

    # Filtros locales de esta página (además de los globales del sidebar).
    filtros_locales = []
    if ccte_filtro != "Todos":
        filtros_locales.append(f"CCTE: {ccte_filtro}")
    if provincia_filtro != "Todas":
        filtros_locales.append(f"Prov: {provincia_filtro}")
    if localidad_seleccionada:
        filtros_locales.append(f"Localidad: {localidad_seleccionada}")
    if filtros_locales:
        st.caption("📌 Filtro local de esta página: " + " · ".join(filtros_locales))

    # Mostrar datos de resumen de la tabla resumen_localidades
    if localidad_seleccionada:
        # Si hay localidad seleccionada, mostrar resumen y detalles diarios/mensuales
        fila_resumen = resumen_filtrado[resumen_filtrado["Localidad"] == localidad_seleccionada]
        
        if fila_resumen.empty:
            st.warning("No hay datos para esa localidad.")
            return ctx

        fila = fila_resumen.iloc[0]
        provincia_real = fila.get("Provincia", "N/A")
        ccte_real = fila.get("CCTE", "N/A")
        titulo_scope = f"la localidad {localidad_seleccionada}, {provincia_real} (CCTE: {ccte_real})"
        
        st.subheader(f"Mediciones RNI de {titulo_scope}")
        
        # Mostrar datos generales desde la tabla resumen (sin recalcular)
        mediciones = fila.get("Mediciones", 0)
        max_vm = fila.get("Resultado_Max_Vm", None)
        max_pct = fila.get("Resultado_Max_Pct", None)
        temp_trabajado_seg = fila.get("TiempoTrabajadoSegundos", 0)
        sondas = fila.get("Sondas", "")
        expedientes = fila.get("Expedientes", "")
        fecha_inicio = fila.get("FechaInicio", None)
        fecha_fin = fila.get("FechaFin", None)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Cantidad de puntos", int(mediciones))
        with col2:
            st.metric("Máx (V/m)", f"{max_vm:.2f}" if pd.notna(max_vm) else "N/A")
        with col3:
            st.metric("Máx (%)", f"{max_pct:.2f}" if pd.notna(max_pct) else "N/A")
        with col4:
            tiempo_txt = format_timedelta_long(pd.Timedelta(seconds=int(temp_trabajado_seg)))
            st.metric("Tiempo total", tiempo_txt)
        with col5:
            st.metric("Período", f"{fecha_inicio.date() if pd.notna(fecha_inicio) else 'N/A'} a {fecha_fin.date() if pd.notna(fecha_fin) else 'N/A'}")
        
        st.write(f"**Sondas utilizadas:** {sondas if sondas else 'N/A'}")
        st.write(f"**Expedientes:** {expedientes if expedientes else 'N/A'}")
        
        # Actualizar contexto con datos de esta localidad seleccionada
        ctx["localidad_seleccionada"] = localidad_seleccionada
        ctx["max_resultado_pct"] = max_pct if pd.notna(max_pct) else 0
        ctx["titulo_scope"] = titulo_scope
        
        # Si el usuario quiere ver detalles diarios/mensuales, cargar datos detallados SOLO de esa localidad
        if st.checkbox("Mostrar resúmenes diarios y mensuales:", key="show_detailed_resumen"):
            if not df_tabla_maestra.empty:
                # Filtrar solo esta localidad
                df_localidad = df_tabla_maestra[
                    (df_tabla_maestra["CCTE"] == ccte_real) &
                    (df_tabla_maestra["Provincia"] == provincia_real) &
                    (df_tabla_maestra["Localidad"] == localidad_seleccionada)
                ].copy()
                
                # Actualizar contexto con df_localidad
                ctx["df_localidad"] = df_localidad
                
                if not df_localidad.empty:
                    # Normalizar Resultado
                    if "Resultado" in df_localidad.columns:
                        df_localidad["Resultado"] = pd.to_numeric(df_localidad["Resultado"], errors="coerce")
                    
                    # Construir FechaHora
                    df_localidad = add_fechahora(df_localidad, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
                    
                    if "FechaHora" in df_localidad.columns:
                        df_localidad["FechaHora"] = pd.to_datetime(df_localidad["FechaHora"], errors="coerce")
                        df_localidad = df_localidad.dropna(subset=["FechaHora"]).copy()
                        
                        if not df_localidad.empty:
                            df_localidad["Fecha"] = df_localidad["FechaHora"].dt.date
                            df_localidad["Mes"] = df_localidad["FechaHora"].dt.to_period("M").astype(str)
                            
                            # Resumen diario
                            def resumen_por_dia(df_dia):
                                tiempo_total = calcular_tiempo_total_por_archivo(df_dia)
                                inicio_dt = df_dia["FechaHora"].min()
                                fin_dt = df_dia["FechaHora"].max()
                                return {
                                    "Hora de inicio": inicio_dt.strftime("%H:%M:%S") if pd.notna(inicio_dt) else "-",
                                    "Hora de fin": fin_dt.strftime("%H:%M:%S") if pd.notna(fin_dt) else "-",
                                    "Tiempo total trabajado": format_timedelta_long(tiempo_total),
                                    "Cantidad de puntos medidos": len(df_dia),
                                }
                            
                            filas_resumen_dias = []
                            for fecha, g_dia in df_localidad.groupby("Fecha"):
                                info = resumen_por_dia(g_dia)
                                info["Fecha de medición"] = fecha
                                filas_resumen_dias.append(info)
                            
                            resumen_dias = pd.DataFrame(filas_resumen_dias)
                            if not resumen_dias.empty:
                                resumen_dias = resumen_dias[
                                    ["Fecha de medición", "Hora de inicio", "Hora de fin", "Tiempo total trabajado", "Cantidad de puntos medidos"]
                                ]
                            
                            # Resumen mensual
                            resumen_mensual = df_localidad.groupby("Mes").agg({
                                "FechaHora": ["min", "max"],
                                "Resultado": "count"
                            }).reset_index()
                            resumen_mensual.columns = ["Mes", "Hora inicio", "Hora fin", "Cantidad puntos"]
                            
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
                            
                            # Mostrar en tabs
                            tab1, tab2, tab3 = st.tabs(["📅 Resumen Diario", "🗓️ Resumen Mensual", "📊 Gráfico"])
                            
                            with tab1:
                                st.markdown(f"### ⏱️ Tiempo trabajado por día")
                                st.dataframe(resumen_dias, width="stretch")
                            
                            with tab2:
                                st.markdown(f"### 📅 Mediciones por mes")
                                st.dataframe(resumen_mensual, width="stretch")
                            
                            with tab3:
                                if not resumen_mensual.empty:
                                    st.markdown(f"### 📊 Gráfico mensual")
                                    import plotly.graph_objects as go
                                    fig = go.Figure()
                                    fig.add_trace(go.Bar(
                                        x=resumen_mensual["Mes"].astype(str),
                                        y=resumen_mensual["Cantidad puntos"],
                                        name="Cantidad puntos",
                                        yaxis="y1",
                                        text=resumen_mensual["Cantidad puntos"],
                                        textposition="auto",
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
                                    st.plotly_chart(fig, width='stretch')
    
    else:
        # Si NO hay localidad seleccionada, mostrar tabla resumen de filtro aplicado
        titulo_scope = "todas las localidades"
        if provincia_filtro != "Todas":
            titulo_scope = f"provincias {provincia_filtro}"
        if ccte_filtro != "Todos":
            titulo_scope = f"CCTE {ccte_filtro}"
        
        st.subheader(f"Resumen de mediciones de {titulo_scope}")
        
        # Mostrar tabla resumen directamente desde resumen_db (sin recalcular)
        cols_mostrar = ["CCTE", "Provincia", "Localidad", "Mediciones", "Resultado_Max_Vm", "Resultado_Max_Pct", "TiempoTrabajadoSegundos"]
        cols_existentes = [c for c in cols_mostrar if c in resumen_filtrado.columns]
        resumen_vista = resumen_filtrado[cols_existentes].copy()
        
        # Renombrar columnas para vista
        resumen_vista = resumen_vista.rename(columns={
            "Resultado_Max_Vm": "Máx (V/m)",
            "Resultado_Max_Pct": "Máx (%)",
            "TiempoTrabajadoSegundos": "Tiempo Trabajado (segundos)",
            "Mediciones": "Puntos Medidos"
        })
        
        st.dataframe(resumen_vista, width="stretch")
        st.info("Selecciona una localidad arriba para ver detalles diarios/mensuales.")


        ctx["titulo_scope"] = titulo_scope
        if not df_tabla_maestra.empty:
            df_prov_ccte = df_tabla_maestra.copy()
            if ccte_filtro != "Todos" and "CCTE" in df_prov_ccte.columns:
                df_prov_ccte = df_prov_ccte[df_prov_ccte["CCTE"] == ccte_filtro]
            if provincia_filtro != "Todas" and "Provincia" in df_prov_ccte.columns:
                df_prov_ccte = df_prov_ccte[df_prov_ccte["Provincia"] == provincia_filtro]
            ctx["df_filtrado_prov"] = df_prov_ccte

    return ctx