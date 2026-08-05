from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np

from utils.time_utils import add_fechahora, calcular_tiempo_total_por_archivo


def render_highlight_global(df: pd.DataFrame = None):
    """Renderiza dashboard de inicio con KPIs y visualizaciones clave."""
    
    # Función auxiliar para títulos de sección
    def section_title(emoji: str, text: str, level: str = "h2"):
        color = "#003b7a"  # ENACOM blue
        if level == "h2":
            return st.markdown(
                f"""
                <div style="margin: 20px 0 12px 0; padding: 12px 16px; background: linear-gradient(135deg, rgba(0,59,122,0.08), rgba(0,112,209,0.06)); border-left: 4px solid {color}; border-radius: 8px;">
                  <h2 style="margin: 0; color: {color}; font-size: 1.35rem; font-weight: 800;">{emoji} {text}</h2>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:  # h3
            return st.markdown(
                f"""
                <div style="margin: 16px 0 12px 0; padding: 10px 14px; background: rgba(0,59,122,0.05); border-left: 3px solid {color}; border-radius: 6px;">
                  <h3 style="margin: 0; color: {color}; font-size: 1.1rem; font-weight: 700;">{emoji} {text}</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    # Usar df filtrado si se proporciona, sino usar tabla_maestra
    if df is None or df.empty:
        if "tabla_maestra" in st.session_state and not st.session_state["tabla_maestra"].empty:
            df = st.session_state["tabla_maestra"].copy()
        else:
            return
    else:
        df = df.copy()

    # Normalizaciones base para todos los bloques (siempre sobre DF ya filtrado globalmente)
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")

    # Fecha/hora para métricas operativas (días/horas/tendencia mensual)
    df_time = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
    df_time["_dia"] = pd.to_datetime(df_time.get("FechaHora"), errors="coerce").dt.date
    df_time["Mes"] = pd.to_datetime(df_time.get("FechaHora"), errors="coerce").dt.to_period("M").astype(str)

    # Resumen por CCTE basado en datos filtrados
    ccte_rows = []
    if "CCTE" in df_time.columns:
        for ccte, g in df_time.groupby("CCTE", dropna=False):
            if pd.isna(ccte):
                continue
            td = calcular_tiempo_total_por_archivo(g)
            ccte_rows.append(
                {
                    "CCTE": str(ccte),
                    "Puntos": int(len(g)),
                    "HorasSegundos": int(td.total_seconds()),
                    "DiasConMedicion": int(g["_dia"].dropna().nunique()),
                }
            )
    df_ccte = pd.DataFrame(ccte_rows)

    # Tendencia mensual basada en datos filtrados
    if "Mes" in df_time.columns:
        df_mensual = df_time[df_time["Mes"].notna()].groupby("Mes").size().reset_index(name="Puntos")
    else:
        df_mensual = pd.DataFrame()

    # Resumen simple para contadores de cobertura
    df_resumen = pd.DataFrame()
    if not df.empty:
        cols = [c for c in ["Localidad", "Provincia", "CCTE"] if c in df.columns]
        if cols:
            df_resumen = df[cols].dropna(how="all").drop_duplicates()

    # ============================================================
    # SECCIÓN 1: Valor máximo registrado (highlight principal)
    # ============================================================
    section_title("🌎", "Valor máximo registrado en Argentina")

    df_norm = df.copy()
    
    if not df_norm.empty and df_norm["Resultado"].notna().any():
        idx_max = df_norm["Resultado"].idxmax()
        fila_max = df_norm.loc[idx_max]

        localidad_top = fila_max.get("Localidad", "N/A")
        resultado_top = fila_max["Resultado"]
        resultado_top_pct = resultado_top**2 / 3770 / 0.20021 * 100 if pd.notna(resultado_top) else None
        provincia_top = fila_max.get("Provincia", "N/A")
        ccte_top = fila_max.get("CCTE", "N/A")

        col1, col2, col3, col4, col5 = st.columns(5)

        def kpi_card(col, title, value, sub_html=""):
            col.markdown(
                f"""
                <div class="kpi-card" style="text-align:center;">
                  <div class="kpi-title">{title}</div>
                  <div class="kpi-value">{value}</div>
                  <div class="kpi-sub">{sub_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Formatear valores con seguridad
        loc_txt = str(localidad_top) if localidad_top is not None else "N/A"
        vm_txt = f"{float(resultado_top):.2f} V/m" if resultado_top is not None and pd.notna(resultado_top) else "N/A"
        pct_txt = f"{float(resultado_top_pct):.2f} %" if resultado_top_pct is not None and pd.notna(resultado_top_pct) else "N/A"
        prov_txt = str(provincia_top) if provincia_top is not None else "N/A"
        ccte_txt = str(ccte_top) if ccte_top is not None else "N/A"

        kpi_card(col1, "Localidad", loc_txt)
        kpi_card(col2, "Provincia", prov_txt)
        kpi_card(col3, "Máximo registrado (V/m)", vm_txt)
        kpi_card(col4, "Máximo registrado (%)", pct_txt)
        kpi_card(col5, "CCTE", ccte_txt)

    # ============================================================
    # SECCIÓN 2: KPIs generales (desde cache)
    # ============================================================
    st.markdown("---")
    section_title("📊", "Indicadores clave")

    # Calcular KPIs
    total_puntos = int(df_ccte["Puntos"].sum()) if not df_ccte.empty else 0
    total_localidades = int(df_resumen["Localidad"].nunique()) if not df_resumen.empty else 0
    total_provincias = int(df_resumen["Provincia"].nunique()) if not df_resumen.empty else 0
    total_cctes = int(df_ccte["CCTE"].nunique()) if not df_ccte.empty else 0
    
    # Calcular horas totales
    def _hours(segs):
        try:
            return float(segs) / 3600.0
        except:
            return 0.0
    
    total_horas = _hours(df_ccte["HorasSegundos"].sum()) if not df_ccte.empty else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        col1.markdown(
            f"""
            <div class="kpi-card" style="text-align: center;">
              <div class="kpi-title">📍 Total Puntos</div>
              <div class="kpi-value">{total_puntos:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col2:
        col2.markdown(
            f"""
            <div class="kpi-card" style="text-align: center;">
              <div class="kpi-title">🏘️ Localidades</div>
              <div class="kpi-value">{total_localidades:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col3:
        col3.markdown(
            f"""
            <div class="kpi-card" style="text-align: center;">
              <div class="kpi-title">📍 Provincias</div>
              <div class="kpi-value">{total_provincias:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col4:
        col4.markdown(
            f"""
            <div class="kpi-card" style="text-align: center;">
              <div class="kpi-title">📡 CCTEs</div>
              <div class="kpi-value">{total_cctes:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col5:
        col5.markdown(
            f"""
            <div class="kpi-card" style="text-align: center;">
              <div class="kpi-title">⏱️ Horas (est.)</div>
              <div class="kpi-value">{total_horas:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ============================================================
    # SECCIÓN 2B: KPIs mini por CCTE
    # ============================================================
    st.markdown("---")
    section_title("🏢", "Mediciones por Centro de Comprobación Técnica de Emisiones", level="h3")

    if "CCTE" in df.columns:
        base = df.copy()
        base["CCTE"] = base["CCTE"].astype(str)
        
        FIJOS = ["Buenos Aires", "CABA"]
        
        conteo = (
            base["CCTE"].dropna().astype(str).str.strip()
            .value_counts()
            .to_dict()
        )

        cctes_unicos = {c.strip() for c in base["CCTE"].dropna().astype(str).tolist() if c.strip()}
        for f in FIJOS:
            cctes_unicos.add(f)

        cctes_ordenados = sorted(
            list(cctes_unicos),
            key=lambda x: (-conteo.get(x, 0), str(x).lower())
        )

        CCTE_TARJETAS = cctes_ordenados[:7]

        def kpi_mini(col, title, value, sub_html=""):
            col.markdown(
                f"""
                <div class="kpi-card kpi-mini">
                  <div class="kpi-title">{title}</div>
                  <div class="kpi-value">{value}</div>
                  <div class="kpi-sub">{sub_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        base["Resultado"] = pd.to_numeric(base.get("Resultado", np.nan), errors="coerce")

        def ccte_card(col, ccte_name: str):
            g = base[base["CCTE"].astype(str).str.strip().str.lower() == str(ccte_name).strip().lower()].copy()
            puntos = int(len(g))
            pico_vm = None
            pico_pct = None
            pico_loc = "N/D"

            if puntos > 0 and g["Resultado"].notna().any():
                j = g["Resultado"].idxmax()
                rmax = g.loc[j]
                pico_vm = float(rmax["Resultado"]) if pd.notna(rmax["Resultado"]) else None
                pico_pct = (pico_vm ** 2) / 3770 / 0.20021 * 100 if pico_vm is not None else None
                pico_loc = str(rmax.get("Localidad", "N/D"))
            
            vm_txt = f"{pico_vm:.2f} V/m" if pico_vm is not None else "—"
            pct_txt = f"{pico_pct:.2f} %" if pico_pct is not None else "—"
            sub = f"{vm_txt} · {pct_txt}<br><span style='opacity:.85'>{pico_loc}</span>"
            kpi_mini(col, f"{ccte_name}", f"{puntos:,}".replace(",", "."), sub)

        cols = st.columns(7)
        for i, ccte_name in enumerate(CCTE_TARJETAS[:7]):
            ccte_card(cols[i], ccte_name)
    else:
        st.info("No hay columna CCTE para armar KPIs por centro.")

    # ============================================================
    # SECCIÓN 3: Distribución y tendencias
    # ============================================================
    st.markdown("---")
    section_title("📈", "Análisis de cobertura y tendencias")

    col1, col2 = st.columns(2)

    # Gráfico 1: Puntos por CCTE (pie)
    with col1:
        if not df_ccte.empty:
            fig = px.pie(
                df_ccte,
                names="CCTE",
                values="Puntos",
                title="Distribución de puntos medidos por CCTE",
                hole=0.3,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, width='stretch')

    # Gráfico 2: Tendencia mensual
    with col2:
        if not df_mensual.empty:
            fig = px.bar(
                df_mensual,
                x="Mes",
                y="Puntos",
                title="Tendencia mensual de mediciones",
                labels={"Puntos": "Cantidad de puntos", "Mes": "Mes"},
                text="Puntos",
            )
            fig.update_traces(textposition="auto")
            fig.update_layout(xaxis={"categoryorder": "total descending"})
            st.plotly_chart(fig, width='stretch')

    # ============================================================
    # SECCIÓN 4: Top 5 localidades en tarjetas
    # ============================================================
    st.markdown("---")
    section_title("🔥", "Top 5 localidades (máximo registrado)", level="h3")

    if "Localidad" in df.columns and "Resultado" in df.columns:
        df_toploc = df.dropna(subset=["Resultado", "Localidad"]).copy()

        if not df_toploc.empty:
            idx = df_toploc.groupby("Localidad")["Resultado"].idxmax()
            top_loc = df_toploc.loc[idx].copy()
            top_loc = top_loc.sort_values("Resultado", ascending=False).head(5)

            top_loc["Resultado %"] = (top_loc["Resultado"] ** 2) / 3770 / 0.20021 * 100
            top_loc["Resultado %"] = pd.to_numeric(top_loc["Resultado %"], errors="coerce").round(2)
            top_loc["Resultado"] = pd.to_numeric(top_loc["Resultado"], errors="coerce").round(2)

            cols = st.columns(5)
            for i, (_, r) in enumerate(top_loc.iterrows(), start=1):
                loc = str(r.get("Localidad", "N/D"))
                prov = str(r.get("Provincia", "N/D"))
                ccte = str(r.get("CCTE", "N/D"))
                vm = r.get("Resultado", np.nan)
                pct = r.get("Resultado %", np.nan)

                vm_txt = f"{vm:.2f} V/m" if pd.notna(vm) else "N/A"
                pct_txt = f"{pct:.2f} %" if pd.notna(pct) else "N/A"

                card_html = f"""
                <div class="top-card">
                  <div class="top-rank">#{i}</div>
                  <div class="top-loc">{loc}</div>
                  <div class="top-meta">{prov}</div>
                  <div class="top-meta">CCTE: {ccte}</div>
                  <div class="top-val">{vm_txt}</div>
                  <div class="top-pct">Resultado: {pct_txt}</div>
                </div>
                """
                cols[i - 1].markdown(card_html, unsafe_allow_html=True)

            with st.expander("Ver detalle en tabla", expanded=False):
                top_show = top_loc.copy().rename(columns={"Resultado": "Resultado V/m"})
                cols_show = [
                    c for c in [
                        "CCTE", "Provincia", "Localidad",
                        "Resultado V/m", "Resultado %",
                        "Expediente", "Nombre Archivo"
                    ]
                    if c in top_show.columns
                ]
                st.dataframe(top_show[cols_show].reset_index(drop=True), width='stretch')
        else:
            st.info("No hay localidades con Resultado válido para armar el Top 5.")
    else:
        st.info("Faltan columnas necesarias (Localidad/Resultado) para armar el Top 5.")

    # ============================================================
    # SECCIÓN 5: Estadísticas por CCTE
    # ============================================================
    st.markdown("---")
    section_title("📡", "Estadísticas por Centro de Control")

    if not df_ccte.empty:
        df_ccte_stat = df_ccte.copy()
        df_ccte_stat["Horas"] = df_ccte_stat["HorasSegundos"].apply(_hours)
        df_ccte_stat = df_ccte_stat[["CCTE", "Puntos", "DiasConMedicion", "Horas"]].copy()
        df_ccte_stat = df_ccte_stat.sort_values("Puntos", ascending=False)
        df_ccte_stat = df_ccte_stat.rename(columns={
            "Puntos": "Puntos medidos",
            "DiasConMedicion": "Días con actividad",
            "Horas": "Horas trabajadas",
        })

        # Formatear números
        df_ccte_stat["Puntos medidos"] = df_ccte_stat["Puntos medidos"].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_ccte_stat["Horas trabajadas"] = df_ccte_stat["Horas trabajadas"].apply(lambda x: f"{x:.1f}")

        # Mostrar estadísticas como tarjetas (grid)
        if not df_ccte_stat.empty:
            cards = df_ccte_stat.to_dict(orient="records")
            cols_per_row = 7
            for i, r in enumerate(cards):
                if i % cols_per_row == 0:
                    cols = st.columns(cols_per_row)
                c = cols[i % cols_per_row]
                ccte_name = r.get("CCTE", "N/D")
                puntos = r.get("Puntos medidos", "0")
                dias = r.get("Días con actividad", "0")
                horas = r.get("Horas trabajadas", "0")

                card_html = f"""
                <div class="kpi-card ccte-card" style="padding:10px;">
                  <div class="kpi-title">{ccte_name}</div>
                  <div style="font-size:1.25rem; font-weight:700; margin-top:6px;">{puntos}</div>
                  <div class="kpi-sub" style="margin-top:6px; opacity:.9">{dias} · {horas} hrs</div>
                </div>
                """
                c.markdown(card_html, unsafe_allow_html=True)

            # Si hay muchas filas, ofrecer la tabla completa en un expander
            if len(df_ccte_stat) > cols_per_row * 3:
                with st.expander(f"Ver tabla completa ({len(df_ccte_stat)})", expanded=False):
                    st.dataframe(df_ccte_stat, width='stretch')
        else:
            st.info("No hay estadísticas por CCTE para mostrar.")

    # ============================================================
    # SECCIÓN 7: Promedio general
    # ============================================================
    section_title("📊", "Promedio general", level="h3")
    
    # Calcular promedio
    if "Resultado" in df.columns:
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
        if df["Resultado"].notna().any():
            vm_prom = df["Resultado"].dropna().mean()
            pct_prom = (vm_prom**2 / 3770 / 0.20021) * 100
        else:
            vm_prom = 0
            pct_prom = 0
    else:
        vm_prom = 0
        pct_prom = 0
    
    # Mostrar promedio en formato tarjeta
    col1, col2 = st.columns(2)
    
    with col1:
        col1.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-title">Promedio V/m</div>
              <div class="kpi-value">{vm_prom:.2f}</div>
              <div class="kpi-sub">Valor físico promedio</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col2:
        col2.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-title">Promedio %</div>
              <div class="kpi-value">{pct_prom:.2f}</div>
              <div class="kpi-sub">Porcentaje del límite normativo</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    st.markdown("---")