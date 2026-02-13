import streamlit as st

from db.sqlite_store import (
    delete_by_localidad,
    load_tabla_maestra_from_db,
)


# ============================================================
# ACCIONES ADMINISTRATIVAS
# ============================================================

def eliminar_localidad(localidad: str):
    """
    Elimina todas las mediciones de una localidad
    tanto de SQLite como del session_state.
    """
    if not localidad:
        st.warning("No se seleccionó ninguna localidad.")
        return

    try:
        # 1️⃣ Borrar de DB
        delete_by_localidad(localidad)

        # 2️⃣ Recargar tabla completa desde DB
        df = load_tabla_maestra_from_db()
        st.session_state["tabla_maestra"] = df

        st.success(f"Localidad '{localidad}' eliminada correctamente.")

    except Exception as e:
        st.error(f"Error al eliminar localidad '{localidad}': {e}")
