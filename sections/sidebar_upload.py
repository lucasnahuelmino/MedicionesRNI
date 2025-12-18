from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit import rerun

from admin.actions import eliminar_localidad
from db.sqlite_store import save_tabla_maestra_to_db
from processing.excel_processor import procesar_archivos


def render_sidebar(sb=None):
    
    if sb is None:
        sb = st.sidebar

    # ============================================================
    # 📥 CARGA DE ARCHIVOS (SIDEBAR)
    # ============================================================

    sb.header("Cargar archivos")

    def reset_form():
        """Reinicia los campos del formulario lateral."""
        for key in ["uploaded_files_list", "form_localidad", "form_expediente", "form_ccte", "form_provincia"]:
            st.session_state[key] = "" if "list" not in key else []
        st.session_state["uploader_key"] += 1
        rerun()

    # --- Formulario lateral de carga ---
    with sb.form("carga_form", clear_on_submit=False):
        ccte = st.selectbox(
            "CCTE",
            ["CABA", "Buenos Aires", "Comodoro Rivadavia", "Córdoba", "Neuquén", "Posadas", "Salta"],
            key="form_ccte"
        )
        provincia = st.selectbox(
            "Provincia",
            ["Buenos Aires","CABA","Catamarca","Chaco","Chubut","Córdoba","Corrientes","Entre Ríos","Formosa","Jujuy",
             "La Pampa","La Rioja","Mendoza","Misiones","Neuquén","Río Negro","Salta","San Juan","San Luis","Santa Cruz",
             "Santa Fe","Santiago del Estero","Tierra del Fuego","Tucumán"],
            key="form_provincia"
        )
        localidad = st.text_input("Localidad", value=st.session_state["form_localidad"], key="form_localidad")
        expediente = st.text_input("Expediente", value=st.session_state["form_expediente"], key="form_expediente")
        files = st.file_uploader(
            "Seleccionar archivos Excel",
            accept_multiple_files=True,
            type=["xlsx"],
            key=f"form_files_{st.session_state['uploader_key']}"
        )
        submit = st.form_submit_button("Procesar archivos")

        if submit and files:
            df_proc, resumen_df = procesar_archivos(files, ccte, provincia, localidad, expediente)
            if not df_proc.empty:
                df_proc["FechaCarga"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["tabla_maestra"] = pd.concat([st.session_state["tabla_maestra"], df_proc], ignore_index=True)
                # >>> CAMBIO SQLITE: guardamos en DB
                save_tabla_maestra_to_db(st.session_state["tabla_maestra"])
                sb.success(f"{len(files)} archivos procesados y agregados.")
                sb.dataframe(resumen_df)
                st.session_state["uploader_key"] += 1
            else:
                sb.warning("No se procesaron archivos válidos.")

    sb.button("Restablecer formulario", on_click=reset_form)

    # ------------------- eliminar localidad ------------------
    if "tabla_maestra" in st.session_state and not st.session_state["tabla_maestra"].empty:
        localidades_unicas = sorted(st.session_state["tabla_maestra"]["Localidad"].dropna().unique().tolist())
        localidad_a_borrar = sb.selectbox("Seleccionar localidad a eliminar", [""] + localidades_unicas)

        if sb.button("❌ Eliminar localidad") and localidad_a_borrar:
            eliminar_localidad(localidad_a_borrar)
