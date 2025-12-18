import streamlit as st

from db.sqlite_store import save_tabla_maestra_to_db


def eliminar_localidad(nombre_localidad: str):
    """Elimina una localidad completa de la tabla maestra."""
    if st.session_state["tabla_maestra"].empty:
        st.warning("⚠️ No hay datos cargados en la tabla maestra.")
        return

    df = st.session_state["tabla_maestra"]
    if "Localidad" not in df.columns:
        st.error("❌ No se encontró columna 'Localidad'.")
        return

    eliminados = len(df[df["Localidad"] == nombre_localidad])
    if eliminados == 0:
        st.info(f"ℹ️ No se encontró la localidad **{nombre_localidad}** en la tabla.")
        return

    st.session_state["tabla_maestra"] = df[df["Localidad"] != nombre_localidad]
    # >>> CAMBIO SQLITE: guardamos en DB
    save_tabla_maestra_to_db(st.session_state["tabla_maestra"])
    st.success(f"✅ Localidad **{nombre_localidad}** eliminada ({eliminados} registros).")
