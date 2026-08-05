# ============================================================
# 📡 BASE DE DATOS DE MEDICIONES RNI - ENACOM
# ============================================================

import base64
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import CSS_PATH, ASSETS
from state import (
    init_session_state,
    ensure_tabla_maestra_loaded,
    get_df_filtrado_global,
)


# ---------------------- CONFIG ----------------------
st.set_page_config(
    page_title="Base de datos RNI - ENACOM",
    layout="wide",
)

# ---------------------- ESTILO ----------------------
if CSS_PATH.exists():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.warning("No se encontró styles/style.css")

# ---------------------- HEADER ----------------------
def img_to_base64(path: Path) -> str | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"

logo_path = ASSETS / "enacom_logo.png"
logo_src = img_to_base64(logo_path) or "https://via.placeholder.com/150x50?text=ENACOM"

st.markdown(
    f"""
    <div class="enacom-header-card">
      <div class="enacom-header-left">
        <div class="title">Base de datos de Radiaciones No Ionizantes</div>
        <div class="subtitle">Sistema de mediciones RNI de Argentina</div>
      </div>
      <div class="enacom-header-right">
        <img src="{logo_src}" alt="ENACOM logo"/>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------- STATE ----------------------
init_session_state()
ensure_tabla_maestra_loaded()

# !!!! CAMBIO: Solo cargamos df_all (lo usamos después) y solo calculamos df_filtrado si es necesario
df_all = st.session_state.get("tabla_maestra", pd.DataFrame())

# ---------------------- SIDEBAR (FAST) ----------------------
from sections.sidebar import render_sidebar
render_sidebar(df_all)

# !!!! CAMBIO: El router está ARRIBA del cache, así que lazy imports funcionan correctamente
# ---------------------- ROUTER ----------------------
page = st.session_state.get("page", "Inicio")

# ============================================================
# 🏠 INICIO
# ============================================================
if page == "Inicio":
    from sections.highlight_global import render_highlight_global
    from state import render_active_filters_banner
    render_active_filters_banner()
    df_filtrado = get_df_filtrado_global(df_all)  # Solo calcula aquí si se necesita
    render_highlight_global(df_filtrado)

# ============================================================
# 📊 RESUMEN
# ============================================================
elif page == "Resumen":
    from sections.resumen_general import render_resumen_general
    render_resumen_general()

# ============================================================
# 📈 GRÁFICOS
# ============================================================
elif page == "Gráficos":
    from sections.graficos import render_graficos
    render_graficos()

# ============================================================
# 🧩 GESTIÓN DE LOCALIDADES
# ============================================================
elif page == "Gestión":
    from sections.gestion_localidades import render_gestion_localidades
    from sections.editor_localidad import render_editor_localidad
    from sections.export_informes import render_export_informes

    ctx = render_gestion_localidades()

    if ctx is None:
        ctx = {
            "localidad_seleccionada": None,
            "df_localidad": None,
            "max_resultado_pct": None,
        }

    tabs = st.tabs(["✏️ Editar", "🖨️ Exportar"])

    with tabs[0]:
        render_editor_localidad(
            ctx.get("localidad_seleccionada") if ctx else None,
            ctx.get("df_localidad") if ctx else None,
        )

    with tabs[1]:
        render_export_informes(
            df_localidad=ctx.get("df_localidad"),
            df_filtrado_prov=ctx.get("df_filtrado_prov"),
            localidad_seleccionada=ctx.get("localidad_seleccionada"),
            titulo_scope=ctx.get("titulo_scope"),
        )

# ============================================================
# 📥 CARGA EXCEL
# ============================================================
# 🗺️ MAPA INTERACTIVO
# ============================================================
elif page == "Mapa":
    from sections.semaforo_mapa import (render_mapa_global,
        render_semaforo_global,
    )
    from db.sqlite_store import load_resumen_from_cache
    from state import render_active_filters_banner

    st.header("🗺️ Mapa de cobertura RNI")
    render_active_filters_banner(
        extra="el mapa tiene su propio toggle abajo para aplicarlos o no"
    )
    
    # Cargar datos de resumen para mostrar todas las localidades
    df_resumen = load_resumen_from_cache()
    
    if not df_resumen.empty:
        render_semaforo_global()
        render_mapa_global()
    else:
        st.info("No hay datos disponibles para mostrar en el mapa.")

# ============================================================
# 📥 CARGA EXCEL
# ============================================================
elif page == "Carga":
    from sections.carga_excel import render_carga_excel
    render_carga_excel()

# ---------------------- FOOTER ----------------------
st.markdown(
    """
    <div class="enacom-footer">
      © ENACOM — Dirección Nacional de Control y Fiscalización ·
      Base de datos Radiaciones No Ionizantes
    </div>
    """,
    unsafe_allow_html=True,
)