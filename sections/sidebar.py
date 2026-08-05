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

        # `is_selected` se calculaba pero antes nunca se usaba: todos los
        # botones del menú se veían exactamente iguales y no había forma de
        # saber en qué sección estabas. Ahora se usa `type` para que el botón
        # de la página activa se vea distinto (ver style.css).
        is_selected = pagina_actual == titulo
        if st.sidebar.button(
            seccion,
            key=f"btn_{seccion}",
            width='stretch',
            type="primary" if is_selected else "secondary",
        ):
            st.session_state["page"] = titulo
            # Bug: sin este rerun, el botón se dibuja con el `type` calculado
            # a partir del valor de "page" ANTES del click (el cambio recién
            # se reflejaba en el sidebar en la siguiente interacción, no en
            # esta). Forzamos el rerun ya mismo para que quede marcado el
            # botón correcto en el mismo click.
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()

    st.sidebar.markdown("---")

    # Filtros globales en expander (collapsible)
    if df is not None and not df.empty:
        with st.sidebar.expander("🔍 Filtros globales", expanded=False):
            render_global_filters_sidebar(df, sb=st)

    st.sidebar.markdown("---")
    st.sidebar.caption("v3.1 · ENACOM")