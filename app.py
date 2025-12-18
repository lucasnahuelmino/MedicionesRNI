# ============================================================
# 📡 BASE DE DATOS DE MEDICIONES RNI - ENACOM
# ============================================================

import base64
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

from config import CSS_PATH, ASSETS
from state import init_session_state, ensure_tabla_maestra_loaded

from sections.sidebar_upload import render_sidebar
from sections.resumen_general import render_resumen_general
from sections.graficos import render_graficos
from sections.gestion_localidades import render_gestion_localidades
from sections.semaforo_mapa import render_semaforo, render_mapa
from sections.editor_localidad import render_editor_localidad
from sections.export_informes import render_export_informes
from sections.tabla_maestra import render_tabla_maestra


# ---------------------- CONFIG (SIEMPRE ARRIBA) ----------------------
st.set_page_config(page_title="Base de datos RNI - ENACOM v3.2", layout="wide")


# ---------------------- ESTILO ----------------------
if CSS_PATH.exists():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.warning("No se encontró styles/style.css — colocá el archivo para aplicar el tema institucional.")

# Extra mini para KPI cards (sin tocar tu CSS base)
st.markdown("""
<style>
.kpi-card{
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.75);
  border-radius: 14px;
  padding: 14px 14px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.06);
}
.kpi-title{ font-size: 0.85rem; opacity: 0.8; margin-bottom: 6px;}
.kpi-value{ font-size: 1.6rem; font-weight: 800; line-height: 1.1;}
.kpi-sub{ margin-top: 6px; font-size: 0.85rem; opacity: 0.85;}
</style>
""", unsafe_allow_html=True)


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


# ============================================================
# 🧭 NAV en Sidebar (botones tipo “ferretería”)
# ============================================================
st.session_state.setdefault("page", "Inicio")

# Si venías de una versión con “Exportar”, lo redirigimos a Gestión
if st.session_state.get("page") == "Exportar":
    st.session_state["page"] = "Gestión"

def goto(page_name: str):
    st.session_state["page"] = page_name

sb = st.sidebar
sb.markdown("### 🧭 Navegación")

colA, colB = sb.columns(2)
with colA:
    sb.button("🏠 Inicio", use_container_width=True, on_click=goto, args=("Inicio",))
    sb.button("📊 Resumen de localidades", use_container_width=True, on_click=goto, args=("Resumen",))
    sb.button("📈 Gráficos", use_container_width=True, on_click=goto, args=("Gráficos",))
with colB:
    sb.button("🧩 Gestión de localidades", use_container_width=True, on_click=goto, args=("Gestión",))
    sb.button("🗂️ Tabla maestra", use_container_width=True, on_click=goto, args=("Tabla",))

sb.markdown("---")

with sb.expander("📥 Carga / Administración de excels de mediciones", expanded=False):
    render_sidebar(sb=st)

sb.markdown("---")


# ============================================================
# 🏠 INICIO
# ============================================================
def render_inicio():
    st.markdown("## 🏠 Inicio")
    df = st.session_state["tabla_maestra"].copy()

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

    # Máximo
    max_row = None
    max_val = None
    if df["Resultado"].notna().any():
        i = df["Resultado"].idxmax()
        max_row = df.loc[i]
        max_val = max_row["Resultado"]

    # KPI grid
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
            unsafe_allow_html=True
        )

    kpi(c1, "Registros totales", f"{total_reg:,}".replace(",", "."), "Puntos medidos en la tabla")
    kpi(c2, "Localidades", f"{total_localidades:,}".replace(",", "."), "Cobertura territorial")
    kpi(c3, "Provincias", f"{total_provincias:,}".replace(",", "."), "Diversidad geográfica")
    kpi(c4, "CCTEs", f"{total_ccte:,}".replace(",", "."), f"Última carga: {ultima_carga.strftime('%d/%m/%Y %H:%M') if ultima_carga else 'N/D'}")

    st.markdown("")

    # Destacado del máximo
    if max_row is not None and pd.notna(max_val):
        localidad = max_row.get("Localidad", "N/D")
        provincia = max_row.get("Provincia", "N/D")
        ccte = max_row.get("CCTE", "N/D")
        exp = max_row.get("Expediente", "N/D")

        max_pct = max_val**2 / 3770 / 0.20021 * 100 if pd.notna(max_val) else None

        st.markdown("### 🌎 Pico máximo registrado")
        a, b, c, d = st.columns([2.2, 1.2, 1.2, 1.4])
        a.metric("Ubicación", f"{localidad} · {provincia}", help=f"CCTE: {ccte} | Expediente: {exp}")
        b.metric("Máximo (V/m)", f"{max_val:.2f}")
        c.metric("Máximo (%)", f"{max_pct:.2f}" if max_pct is not None else "N/A")
        d.metric("CCTE", str(ccte))

        st.markdown("---")

    # Top 5
    st.markdown("### 🔥 Top 5 resultados")
    top = df.dropna(subset=["Resultado"]).sort_values("Resultado", ascending=False).head(5)
    cols_show = [c for c in ["CCTE","Provincia","Localidad","Resultado","Expediente","Nombre Archivo"] if c in top.columns]
    st.dataframe(top[cols_show].reset_index(drop=True), width="stretch")

    # Mini histo
    st.markdown("### 📈 Distribución rápida de resultados (V/m)")
    fig = px.histogram(df.dropna(subset=["Resultado"]), x="Resultado", nbins=40, title="")
    fig.update_layout(height=320, template="plotly_white")
    st.plotly_chart(fig, width="stretch")


# ============================================================
# 🧩 ROUTER
# ============================================================
page = st.session_state["page"]

if page == "Inicio":
    render_inicio()

elif page == "Resumen":
    render_resumen_general()

elif page == "Gráficos":
    render_graficos()

elif page == "Gestión":
    # Un solo ctx, una sola verdad
    ctx = render_gestion_localidades()

    tabs = st.tabs(["📌 Vista", "🗺️ Mapa", "✏️ Editar", "🖨️ Exportar"])

    with tabs[0]:
        # render_gestion_localidades ya pinta su UI principal (tablas/infos)
        # Si en el futuro querés que gestión SOLO calcule ctx y no pinte nada,
        # lo ajustamos. Por ahora lo dejamos tal cual está.
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

elif page == "Tabla":
    render_tabla_maestra()


# ---------------------- FOOTER ----------------------
footer_html = """
<div class="enacom-footer">
  © ENACOM — Dirección Nacional de Control y Fiscalización · Base de datos Radiaciones No Ionizantes  
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)
