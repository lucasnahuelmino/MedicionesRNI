from datetime import datetime

import pandas as pd
import streamlit as st

from processing.excel_processor import process_excel
from db.sqlite_store import insert_mediciones, load_tabla_maestra_from_db
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

    if submitted:
        if not files:
            st.warning("Subí al menos un archivo Excel.")
        elif not all([ccte, provincia, localidad]):
            st.warning("CCTE, Provincia y Localidad son obligatorios.")
        else:
            _procesar_y_guardar(files, ccte.strip(), provincia.strip(), localidad.strip(), expediente.strip())

    # Si una carga anterior quedó pendiente de confirmación (por duplicados
    # detectados), la mostramos acá afuera del form para que los botones de
    # confirmar/cancelar funcionen entre reruns.
    if st.session_state.get("carga_excel_pendiente"):
        _render_confirmacion_duplicados()


def _procesar_y_guardar(files, ccte, provincia, localidad, expediente):
    # ========================================================
    # DETECCIÓN DE DUPLICADOS (antes de procesar)
    # Compara nombre de archivo + CCTE + Localidad contra lo ya cargado,
    # para no insertar el mismo archivo dos veces sin avisar.
    # ========================================================
    df_existente = load_tabla_maestra_from_db()
    nombres_nuevos = {f.name for f in files}
    ya_cargados = set()
    if not df_existente.empty and "Nombre Archivo" in df_existente.columns:
        mask = (df_existente["CCTE"] == ccte) & (df_existente["Localidad"] == localidad)
        ya_cargados = set(df_existente.loc[mask, "Nombre Archivo"].astype(str).unique())
    duplicados = sorted(nombres_nuevos & ya_cargados)

    # ========================================================
    # PROCESAMIENTO ARCHIVO POR ARCHIVO, CON BARRA DE PROGRESO
    # Antes se procesaban todos los archivos de una sola vez dentro de un
    # único spinner, sin feedback de avance, y si UN archivo tenía un
    # problema (ej. columna faltante) fallaba TODO el lote sin guardar
    # nada, incluso los archivos válidos. Ahora se procesa uno por uno,
    # se muestra el avance, y un archivo con error no descarta al resto.
    # ========================================================
    dfs = []
    resumenes = []
    errores = []

    progreso = st.progress(0, text="Procesando archivos…")
    for i, file in enumerate(files, start=1):
        progreso.progress(i / len(files), text=f"Procesando {file.name} ({i}/{len(files)})…")
        try:
            df_file = process_excel(
                file,
                {"ccte": ccte, "provincia": provincia, "localidad": localidad, "expediente": expediente},
            )
            dfs.append(df_file)
            resumenes.append({
                "archivo": file.name,
                "expediente": df_file["Expediente"].iloc[0] if not df_file.empty else None,
                "total_mediciones": len(df_file),
                "max_resultado": df_file["Resultado"].max() if "Resultado" in df_file.columns else None,
                "ya_cargado_antes": file.name in duplicados,
            })
        except Exception as e:
            errores.append((file.name, str(e)))
    progreso.empty()

    if errores:
        with st.expander(f"⚠️ {len(errores)} archivo(s) no se pudieron procesar", expanded=True):
            for nombre, err in errores:
                st.error(f"**{nombre}**: {err}")

    if not dfs:
        st.warning("No se generaron mediciones válidas.")
        return

    df = pd.concat(dfs, ignore_index=True)
    resumen_df = pd.DataFrame(resumenes)
    df["FechaCarga"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if duplicados:
        # No insertamos todavía: guardamos el resultado procesado y pedimos
        # confirmación explícita antes de duplicar datos en la base.
        st.session_state["carga_excel_pendiente"] = {
            "df": df,
            "resumen_df": resumen_df,
            "duplicados": duplicados,
        }
    else:
        _insertar_en_db(df, resumen_df)


def _render_confirmacion_duplicados():
    pendiente = st.session_state["carga_excel_pendiente"]
    duplicados = pendiente["duplicados"]

    st.warning(
        f"⚠️ {len(duplicados)} de los archivos subidos ya habían sido cargados antes "
        f"para este mismo CCTE y Localidad:\n\n" + "\n".join(f"- {d}" for d in duplicados)
    )
    st.caption("Si continuás, esas mediciones quedarán duplicadas en la base.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Insertar de todos modos", width='stretch'):
            _insertar_en_db(pendiente["df"], pendiente["resumen_df"])
            del st.session_state["carga_excel_pendiente"]
            st.rerun()
    with c2:
        with st.container(key="danger-zone"):
            if st.button("❌ Cancelar carga", width='stretch'):
                del st.session_state["carga_excel_pendiente"]
                st.rerun()


def _insertar_en_db(df: pd.DataFrame, resumen_df: pd.DataFrame):
    with st.spinner("💾 Guardando en base de datos…"):
        insert_mediciones(df)

    # Recargar estado global desde SQLite
    reset_tabla_maestra()

    st.success("✅ Archivos procesados y guardados correctamente")

    st.subheader("📄 Resumen de carga")
    st.dataframe(resumen_df, width='stretch')

    st.caption(f"Total de registros insertados: {len(df)}")