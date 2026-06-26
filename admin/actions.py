import streamlit as st

from db.sqlite_store import (
    delete_by_localidad,
    load_tabla_maestra_from_db,
)


# ============================================================
# ACCIONES ADMINISTRATIVAS
# ============================================================

def eliminar_localidad(localidad: str, provincia: str | None = None, ccte: str | None = None):
    """Elimina una localidad de SQLite y fuerza refresco de caches/derivados.

    - Si la UI conoce Provincia y/o CCTE, se usan para evitar borrar de más.
    - Si solo se envía `localidad`, se borra por Localidad.
    """
    if not localidad:
        st.warning("No se seleccionó ninguna localidad.")
        return

    try:
        delete_by_localidad(localidad, provincia=provincia, ccte=ccte)

        # Recargar tabla completa desde DB y refrescar session_state
        df = load_tabla_maestra_from_db()
        st.session_state["tabla_maestra"] = df

        scope = []
        scope.append(f"Localidad='{localidad}'")
        if provincia:
            scope.append(f"Provincia='{provincia}'")
        if ccte:
            scope.append(f"CCTE='{ccte}'")

        st.success(f"Localidad eliminada correctamente ({', '.join(scope)}).")

    except Exception as e:
        st.error(f"Error al eliminar localidad '{localidad}': {e}")

