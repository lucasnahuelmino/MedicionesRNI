from datetime import datetime
import pandas as pd
import streamlit as st

from db.sqlite_store import save_tabla_maestra_to_db, delete_by_localidad, load_tabla_maestra_from_db, load_resumen_from_cache


def render_editor_localidad(localidad_seleccionada, df_localidad):
    # -------------------- Edición de información (plegable) --------------------
    if localidad_seleccionada:
        if df_localidad is None or not isinstance(df_localidad, pd.DataFrame) or df_localidad.empty:
            tabla_maestra = st.session_state.get("tabla_maestra", pd.DataFrame())
            if isinstance(tabla_maestra, pd.DataFrame) and not tabla_maestra.empty:
                df_localidad = tabla_maestra[
                    tabla_maestra["Localidad"] == localidad_seleccionada
                ].copy()

        if df_localidad is None or not isinstance(df_localidad, pd.DataFrame) or df_localidad.empty:
            st.warning("No se encontró información de la localidad seleccionada para editar.")
            return

        # >>> CAMBIO SQLITE: aseguramos que FechaCarga sea datetime antes de usar strftime
        if "FechaCarga" in st.session_state["tabla_maestra"].columns:
            st.session_state["tabla_maestra"]["FechaCarga"] = pd.to_datetime(
                st.session_state["tabla_maestra"]["FechaCarga"], errors="coerce"
            )

        ultima_fecha = None
        if "FechaCarga" in st.session_state["tabla_maestra"].columns:
            mask_fecha = st.session_state["tabla_maestra"]["Localidad"] == localidad_seleccionada
            if mask_fecha.any():
                ultima_fecha = st.session_state["tabla_maestra"].loc[mask_fecha, "FechaCarga"].max()

        expander_title = f"✏️ Editar información de {localidad_seleccionada}"
        if ultima_fecha is not None and pd.notna(ultima_fecha):
            expander_title += f" (Última modificación: {ultima_fecha.strftime('%d/%m/%Y %H:%M:%S')})"

        with st.expander(expander_title, expanded=False):
            ccte_actual = df_localidad["CCTE"].iloc[0]
            provincia_actual = df_localidad["Provincia"].iloc[0]
            localidad_actual = df_localidad["Localidad"].iloc[0]
            expediente_actual = df_localidad["Expediente"].iloc[0]

            ccte_options = ["CABA", "Buenos Aires", "Comodoro Rivadavia", "Córdoba", "Neuquén", "Posadas", "Salta"]
            provincia_options = [
                "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes", "Entre Ríos", "Formosa", "Jujuy",
                "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis", "Santa Cruz",
                "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán",
            ]

            # Bug corregido: si el CCTE/Provincia real de la localidad no estaba
            # en estas listas fijas, el selectbox caía en índice 0 sin avisar
            # (mostraba "CABA" aunque el valor real fuera otro), y al guardar
            # CUALQUIER cambio (incluso solo el Expediente) se pisaba el CCTE
            # real por "CABA" silenciosamente. Ahora se agrega el valor actual
            # a la lista si no está, para no perder ni corromper datos.
            if ccte_actual and ccte_actual not in ccte_options:
                ccte_options = [ccte_actual] + ccte_options
            if provincia_actual and provincia_actual not in provincia_options:
                provincia_options = [provincia_actual] + provincia_options

            ccte_index = ccte_options.index(ccte_actual) if ccte_actual in ccte_options else 0
            provincia_index = provincia_options.index(provincia_actual) if provincia_actual in provincia_options else 0

            nuevo_ccte = st.selectbox(
                "CCTE",
                ccte_options,
                index=ccte_index
            )
            nueva_provincia = st.selectbox(
                "Provincia",
                provincia_options,
                index=provincia_index
            )
            nueva_localidad = st.text_input("Localidad", value=localidad_actual)
            nuevo_expediente = st.text_input("Expediente", value=expediente_actual)

            if "FechaCarga" not in st.session_state["tabla_maestra"].columns:
                st.session_state["tabla_maestra"]["FechaCarga"] = pd.NaT

            def guardar_cambios():
                if not nueva_localidad.strip():
                    st.error("El nombre de la localidad no puede quedar vacío.")
                    return

                mask = st.session_state["tabla_maestra"]["Localidad"] == localidad_actual
                st.session_state["tabla_maestra"].loc[mask, "CCTE"] = nuevo_ccte
                st.session_state["tabla_maestra"].loc[mask, "Provincia"] = nueva_provincia
                st.session_state["tabla_maestra"].loc[mask, "Localidad"] = nueva_localidad.strip()
                st.session_state["tabla_maestra"].loc[mask, "Expediente"] = nuevo_expediente
                st.session_state["tabla_maestra"].loc[mask, "FechaCarga"] = datetime.now()

                try:
                    # >>> CAMBIO SQLITE: guardamos en DB
                    save_tabla_maestra_to_db(st.session_state["tabla_maestra"])
                    st.success("Cambios guardados correctamente")
                    # Antes no había rerun acá: los selectbox de Gestión (CCTE/
                    # Provincia/Localidad) seguían mostrando los valores viejos
                    # hasta que el usuario interactuaba con algo más.
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()
                except Exception as e:
                    st.error(f"No se pudieron guardar los cambios: {e}")

            st.button("💾 Guardar cambios", on_click=guardar_cambios)

            # ============================================================
            # ✅ FIX: Usar delete_by_localidad() para eliminación correcta
            # ============================================================
            def eliminar_localidad_cb():
                """
                Elimina UNA localidad específica (con CCTE y Provincia) 
                sin afectar otros registros de la base de datos.
                """

                ccte_para_eliminar = df_localidad["CCTE"].iloc[0] if not df_localidad.empty else None
                provincia_para_eliminar = df_localidad["Provincia"].iloc[0] if not df_localidad.empty else None
                
                try:
                    delete_by_localidad(
                        localidad=localidad_actual,
                        provincia=provincia_para_eliminar,
                        ccte=ccte_para_eliminar
                    )
                    

                    mask = st.session_state["tabla_maestra"]["Localidad"] == localidad_actual
                    st.session_state["tabla_maestra"] = st.session_state["tabla_maestra"].loc[~mask]

                    try:
                        load_tabla_maestra_from_db.clear()
                        load_resumen_from_cache.clear()
                    except Exception:
                        pass  # Si no existen los caches, continuar sin errores
                    
                    st.success(f"✅ Localidad '{localidad_actual}' eliminada correctamente")
                    
                    # Recargar la página para actualizar la UI
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()
                        
                except Exception as e:
                    st.error(f"❌ No se pudo eliminar la localidad: {e}")

            st.markdown("---")
            with st.container(key="danger-zone"):
                st.button("🗑️ Eliminar localidad", on_click=eliminar_localidad_cb)