from datetime import datetime

import streamlit as st

from processing.excel_processor import procesar_archivos
from db.sqlite_store import insert_mediciones
from state import reset_tabla_maestra


# ============================================================
# UI
# ============================================================

def render_carga_excel():
    st.header("📥 Carga de mediciones RNI")

    with st.form("form_carga_excel", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            ccte = st.text_input("CCTE *")
            provincia = st.text_input("Provincia *")
            localidad = st.text_input("Localidad *")

        with col2:
            expediente = st.text_input("Expediente (opcional)")
            files = st.file_uploader(
                "Archivos Excel",
                type=["xlsx"],
                accept_multiple_files=True,
            )

        submitted = st.form_submit_button("🚀 Procesar y guardar")

    # ========================================================
    # VALIDACIONES
    # ========================================================

    if not submitted:
        return

    if not files:
        st.warning("Subí al menos un archivo Excel.")
        return

    if not all([ccte, provincia, localidad]):
        st.warning("CCTE, Provincia y Localidad son obligatorios.")
        return

    # ========================================================
    # PROCESAMIENTO
    # ========================================================

    with st.spinner("📊 Procesando archivos…"):
        df, resumen_df = procesar_archivos(
            files,
            ccte.strip(),
            provincia.strip(),
            localidad.strip(),
            expediente.strip(),
        )

    if df.empty:
        st.warning("No se generaron mediciones válidas.")
        return

    # Fecha de carga (una sola vez)
    df["FechaCarga"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ========================================================
    # DB
    # ========================================================

    with st.spinner("💾 Guardando en base de datos…"):
        insert_mediciones(df)

    # Recargar estado global desde SQLite
    reset_tabla_maestra()

    # ========================================================
    # FEEDBACK
    # ========================================================

    st.success("✅ Archivos procesados y guardados correctamente")

    st.subheader("📄 Resumen de carga")
    st.dataframe(resumen_df, width='stretch')

    st.caption(f"Total de registros insertados: {len(df)}")
