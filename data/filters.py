import streamlit as st
import pandas as pd


def render_filters():
    st.header("🔍 Filtros de datos")

    df = st.session_state.df

    if df is None or df.empty:
        st.info("Primero cargá archivos Excel para poder filtrar.")
        return

    filtered_df = df.copy()

    with st.expander("Filtros disponibles", expanded=True):

        col1, col2, col3 = st.columns(3)

        # =========================
        # Filtro por Provincia
        # =========================
        with col1:
            if "provincia" in filtered_df.columns:
                provincias = sorted(filtered_df["provincia"].dropna().unique())
                selected_provincias = st.multiselect(
                    "Provincia",
                    provincias
                )
                if selected_provincias:
                    filtered_df = filtered_df[
                        filtered_df["provincia"].isin(selected_provincias)
                    ]

        # =========================
        # Filtro por Localidad
        # =========================
        with col2:
            if "localidad" in filtered_df.columns:
                localidades = sorted(filtered_df["localidad"].dropna().unique())
                selected_localidades = st.multiselect(
                    "Localidad",
                    localidades
                )
                if selected_localidades:
                    filtered_df = filtered_df[
                        filtered_df["localidad"].isin(selected_localidades)
                    ]

        # =========================
        # Filtro por Servicio
        # =========================
        with col3:
            if "servicio" in filtered_df.columns:
                servicios = sorted(filtered_df["servicio"].dropna().unique())
                selected_servicios = st.multiselect(
                    "Servicio",
                    servicios
                )
                if selected_servicios:
                    filtered_df = filtered_df[
                        filtered_df["servicio"].isin(selected_servicios)
                    ]

        st.divider()

        col4, col5 = st.columns(2)

        # =========================
        # Filtro por rango de fecha
        # =========================
        with col4:
            if "fecha" in filtered_df.columns:
                filtered_df["fecha"] = pd.to_datetime(
                    filtered_df["fecha"],
                    errors="coerce"
                )

                min_date = filtered_df["fecha"].min()
                max_date = filtered_df["fecha"].max()

                date_range = st.date_input(
                    "Rango de fechas",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )

                if isinstance(date_range, tuple) and len(date_range) == 2:
                    filtered_df = filtered_df[
                        (filtered_df["fecha"] >= pd.to_datetime(date_range[0])) &
                        (filtered_df["fecha"] <= pd.to_datetime(date_range[1]))
                    ]

        # =========================
        # Filtro por Nivel (ej: campo eléctrico)
        # =========================
        with col5:
            if "nivel" in filtered_df.columns:
                min_val = float(filtered_df["nivel"].min())
                max_val = float(filtered_df["nivel"].max())

                nivel_range = st.slider(
                    "Rango de nivel",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val)
                )

                filtered_df = filtered_df[
                    (filtered_df["nivel"] >= nivel_range[0]) &
                    (filtered_df["nivel"] <= nivel_range[1])
                ]

    # =========================
    # Guardar resultado
    # =========================
    st.session_state.filtered_df = filtered_df

    st.success(f"Registros filtrados: {len(filtered_df)}")

    st.dataframe(
        filtered_df,
        width='stretch',
        height=450
    )
