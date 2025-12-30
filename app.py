# ============================================================
# 📡 BASE DE DATOS DE MEDICIONES RNI - ENACOM
# ============================================================

import base64
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from config import CSS_PATH, ASSETS
from state import (
    init_session_state,
    ensure_tabla_maestra_loaded,
    render_global_filters_sidebar,
    get_df_filtrado_global,
)

from sections.sidebar_upload import render_sidebar
from sections.resumen_general import render_resumen_general
from sections.graficos import render_graficos
from sections.gestion_localidades import render_gestion_localidades
from sections.semaforo_mapa import render_semaforo, render_mapa
from sections.editor_localidad import render_editor_localidad
from sections.export_informes import render_export_informes
from sections.diagnostico import render_diagnostico


# ---------------------- CONFIG (SIEMPRE ARRIBA) ----------------------
st.set_page_config(page_title="Base de datos RNI - ENACOM", layout="wide")


# ---------------------- ESTILO ----------------------
if CSS_PATH.exists():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.warning("No se encontró styles/style.css — colocá el archivo para aplicar el tema institucional.")


# ---------------------- HEADER institucional ----------------------
logo_path = ASSETS / "enacom_logo.png"


def img_to_base64(path: Path) -> str | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"


logo_data = img_to_base64(logo_path)
logo_src = logo_data if logo_data else "https://via.placeholder.com/150x50?text=ENACOM"

header_html = f"""
<div class="enacom-header-card">
  <div class="enacom-header-left">
    <div class="title">Base de datos de Radiaciones No Ionizantes</div>
    <div class="subtitle">Sistema de mediciones RNI de Argentina</div>
  </div>
  <div class="enacom-header-right">
    <img src="{logo_src}" alt="ENACOM logo"/>
  </div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)


# ------------------- SESSION STATE ------------------
init_session_state()
ensure_tabla_maestra_loaded()


df_all = st.session_state.get("tabla_maestra", pd.DataFrame())
render_global_filters_sidebar(df_all, sb=st.sidebar)
st.sidebar.markdown("---")


# ============================================================
# 🧭 NAV en Sidebar
# ============================================================
st.session_state.setdefault("page", "Inicio")

if st.session_state.get("page") == "Exportar":
    st.session_state["page"] = "Gestión"


def goto(page_name: str):
    st.session_state["page"] = page_name


sb = st.sidebar
sb.markdown("### Navegación")

colA, colB = sb.columns(2)
with colA:
    sb.button("Inicio", width='stretch', on_click=goto, args=("Inicio",))
    sb.button("Resumen de localidades", width='stretch', on_click=goto, args=("Resumen",))
    sb.button("Gráficos", width='stretch', on_click=goto, args=("Gráficos",))
with colB:
    sb.button("Gestión de localidades", width='stretch', on_click=goto, args=("Gestión",))
    sb.button("Diagnóstico", width='stretch', on_click=goto, args=("Diagnóstico",))

sb.markdown("---")

with sb.expander("Carga / Administración de nuevas mediciones", expanded=False):
    # se renderiza dentro del expander (aunque internamente uses st.*)
    render_sidebar(sb=st)

sb.markdown("---")


# ============================================================
# 🏠 INICIO
# ============================================================
def render_inicio():
    st.markdown("## 🏠 Inicio")
    df = get_df_filtrado_global(st.session_state["tabla_maestra"]).copy()

    if df.empty:
        st.info("Aún no hay datos cargados. Usá **📥 Carga / Administración** en el sidebar para importar mediciones.")
        return

    df["Resultado"] = pd.to_numeric(df.get("Resultado", np.nan), errors="coerce")

    total_reg = len(df)
    total_localidades = df["Localidad"].dropna().nunique() if "Localidad" in df.columns else 0
    total_provincias = df["Provincia"].dropna().nunique() if "Provincia" in df.columns else 0
    total_ccte = df["CCTE"].dropna().nunique() if "CCTE" in df.columns else 0

    ultima_carga = None
    if "FechaCarga" in df.columns:
        _fc = pd.to_datetime(df["FechaCarga"], errors="coerce")
        if _fc.notna().any():
            ultima_carga = _fc.max()

    max_row = None
    max_val = None
    if df["Resultado"].notna().any():
        i = df["Resultado"].idxmax()
        max_row = df.loc[i]
        max_val = max_row["Resultado"]

    c1, c2, c3, c4 = st.columns(4)

    def kpi(col, title, value, sub=""):
        col.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-title">{title}</div>
              <div class="kpi-value">{value}</div>
              <div class="kpi-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    kpi(c1, "Registros totales", f"{total_reg:,}".replace(",", "."), "Puntos medidos en la tabla")
    kpi(c2, "Localidades", f"{total_localidades:,}".replace(",", "."), "Cobertura territorial")
    kpi(c3, "Provincias", f"{total_provincias:,}".replace(",", "."), "Diversidad geográfica")
    kpi(c4, "CCTEs", f"{total_ccte:,}".replace(",", "."),
        f"Última carga: {ultima_carga.strftime('%d/%m/%Y %H:%M') if ultima_carga else 'N/D'}",
    )
    st.markdown("---")

    # ============================================================
    # ✅ KPI mini por CCTE (ordenado) — BA y CABA siempre
    # ============================================================
    st.subheader("🏢 Mediciones por Centro de Comprobación Técnica de Emisiones")

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

            kpi_mini(
                col,
                f"{ccte_name}",
                f"{puntos:,}".replace(",", "."),
                sub,
            )

        cols = st.columns(7)
        for i, ccte_name in enumerate(CCTE_TARJETAS[:7]):
            ccte_card(cols[i], ccte_name)

    else:
        st.info("No hay columna CCTE para armar KPIs por centro.")

    st.markdown("---")
     
    # ------------------- Destacado del máximo -------------------
    if max_row is not None and pd.notna(max_val):
        localidad = max_row.get("Localidad", "N/D")
        provincia = max_row.get("Provincia", "N/D")
        ccte = max_row.get("CCTE", "N/D")
        exp = max_row.get("Expediente", "N/D")

        max_pct = (max_val**2 / 3770 / 0.20021 * 100) if pd.notna(max_val) else None

        st.markdown("### 🌎 Pico máximo registrado")
        a, b, c, d = st.columns([2.2, 1.2, 1.2, 1.4])
        a.metric("Ubicación", f"{localidad} · {provincia}", help=f"CCTE: {ccte} | Expediente: {exp}")
        b.metric("Máximo (V/m)", f"{max_val:.2f}")
        c.metric("Máximo (%)", f"{max_pct:.2f}" if max_pct is not None else "N/A")
        d.metric("CCTE", str(ccte))
        st.markdown("---")

    # ------------------- Top 5 localidades en CARDS -------------------
    st.markdown("### 🔥 Top 5 localidades (máximo registrado)")

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

    # ------------------- Mini histograma -------------------
    st.markdown("### 📈 Distribución rápida de resultados (V/m)")
    df_hist = df.dropna(subset=["Resultado"]).copy()
    if not df_hist.empty:
        fig = px.histogram(df_hist, x="Resultado", nbins=40, title="")
        fig.update_layout(height=320, template="plotly_white")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No hay resultados válidos para graficar.")


# ============================================================
# 🧩 ROUTER
# ============================================================
page = st.session_state.get("page", "Inicio")

if page == "Inicio":
    render_inicio()

elif page == "Resumen":
    render_resumen_general()

elif page == "Gráficos":
    render_graficos()

elif page == "Gestión":

    ctx = render_gestion_localidades()

    tabs = st.tabs(["📌 Vista", "🗺️ Mapa", "✏️ Editar", "🖨️ Exportar"])

    with tabs[0]:

        st.caption("")

    with tabs[1]:
        render_semaforo(ctx.get("max_resultado_pct"), ctx.get("df_localidad"))
        render_mapa(ctx.get("df_localidad"))

    with tabs[2]:
        render_editor_localidad(ctx.get("localidad_seleccionada"), ctx.get("df_localidad"))

    with tabs[3]:
        render_export_informes(
            df_localidad=ctx.get("df_localidad"),
            df_filtrado_prov=ctx.get("df_filtrado_prov"),
            localidad_seleccionada=ctx.get("localidad_seleccionada"),
            titulo_scope=ctx.get("titulo_scope"),
        )

elif page == "Diagnóstico":
    render_diagnostico()

# ---------------------- FOOTER ----------------------
footer_html = """
<div class="enacom-footer">
  © ENACOM — Dirección Nacional de Control y Fiscalización · Base de datos Radiaciones No Ionizantes
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)
