import pandas as pd
import streamlit as st

from db.sqlite_store import load_tabla_maestra_from_db


def init_session_state():
    # ------------------- SESSION STATE ------------------
    st.session_state.setdefault("tabla_maestra", pd.DataFrame())
    st.session_state.setdefault("uploaded_files_list", [])
    st.session_state.setdefault("form_ccte", "")
    st.session_state.setdefault("form_provincia", "")
    st.session_state.setdefault("form_localidad", "")
    st.session_state.setdefault("form_expediente", "")

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0


def ensure_tabla_maestra_loaded():
    # Carga persistente de tabla maestra desde SQLite
    if st.session_state["tabla_maestra"].empty:
        try:
            st.session_state["tabla_maestra"] = load_tabla_maestra_from_db()
        except Exception as e:
            st.warning(f"No se pudo cargar tabla desde archivosdata/rni.db: {e}")
