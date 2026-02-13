import streamlit as st
from state import render_global_filters_sidebar
import pandas as pd


def render_sidebar(df: pd.DataFrame = None):
    """Renderiza menú de navegación y filtros globales."""
    st.sidebar.title("📡 RNI – ENACOM")

    # Navegación con botones estilizados
    st.sidebar.markdown("### Navegación")
    
    secciones = [
        "INICIO",
        "RESUMEN",
        "GRÁFICOS",
        "GESTIÓN",
        "MAPA",
        "CARGA",
    ]
    
    pagina_actual = st.session_state.get("page", "Inicio")
    
    for seccion in secciones:
        # Mapear mayúsculas a título para comparación
        titulo = seccion
        if seccion == "INICIO":
            titulo = "Inicio"
        elif seccion == "RESUMEN":
            titulo = "Resumen"
        elif seccion == "GRÁFICOS":
            titulo = "Gráficos"
        elif seccion == "GESTIÓN":
            titulo = "Gestión"
        elif seccion == "MAPA":
            titulo = "Mapa"
        elif seccion == "CARGA":
            titulo = "Carga"
        
        # Crear botón con clase CSS personalizada
        is_selected = pagina_actual == titulo
        if st.sidebar.button(
            seccion,
            key=f"btn_{seccion}",
            width='stretch',
        ):
            st.session_state["page"] = titulo

    st.sidebar.markdown("---")

    # Filtros globales en expander (collapsible)
    if df is not None and not df.empty:
        with st.sidebar.expander("🔍 Filtros globales", expanded=False):
            render_global_filters_sidebar(df, sb=st)

    st.sidebar.markdown("---")
    st.sidebar.caption("v3.1 · ENACOM")
