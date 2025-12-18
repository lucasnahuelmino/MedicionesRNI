import streamlit as st


def render_tabla_maestra():
    # ============================================================
    # 📊 TABLA MAESTRA
    # ============================================================

    st.header("📊 Tabla Maestra de Mediciones RNI")

    if st.session_state["tabla_maestra"].empty:
        st.info("La tabla maestra está vacía. Cargá archivos a la izquierda.")
    else:
        total_registros = len(st.session_state["tabla_maestra"])
        st.caption(f"🗂️ Registros totales: **{total_registros:,}**")
        with st.expander("📂 Mostrar / Ocultar tabla maestra", expanded=False):
            df_maestra = st.session_state["tabla_maestra"].copy().dropna(axis=1, how="all")
            st.dataframe(df_maestra.reset_index(drop=True), width="stretch")
            if st.button("💾 Exportar tabla a Excel"):
                df_maestra.to_excel("tabla_maestra.xlsx", index=False)
                with open("tabla_maestra.xlsx", "rb") as f:
                    st.download_button("⬇️ Descargar Excel", data=f, file_name="tabla_maestra.xlsx")
