import streamlit as st
import plotly.express as px


def render_graficos():
    #----------------------------- GRAFICOS-------------------------------------
    if not st.session_state["tabla_maestra"].empty:
        df_grafico = st.session_state["tabla_maestra"].copy()

        # Distribución de puntos medidos por CCTE
        df_pie = df_grafico.groupby("CCTE").size().reset_index(name="Cantidad Puntos")
        fig_pie = px.pie(
            df_pie,
            names="CCTE",
            values="Cantidad Puntos",
            title="Distribución de puntos medidos por CCTE",
            color_discrete_sequence=px.colors.qualitative.Set3
        )

        # Localidades por Provincia y CCTE
        resumen = df_grafico.groupby(["Provincia","CCTE"])["Localidad"].nunique().reset_index(name="CantidadLocalidades")
        fig_bar = px.bar(
            resumen,
            x="Provincia",
            y="CantidadLocalidades",
            color="CCTE",
            text="CantidadLocalidades",
            barmode="group",
            title="Localidades por Provincia y CCTE"
        )

        st.subheader("📊 Resumen de mediciones y localidades")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_pie, width="stretch")
        with col2:
            st.plotly_chart(fig_bar, width="stretch")
