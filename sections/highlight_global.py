from datetime import datetime
import pandas as pd
import streamlit as st


def render_highlight_global():
    # ------------------- HIGHLIGHT GLOBAL ------------------
    if "tabla_maestra" in st.session_state and not st.session_state["tabla_maestra"].empty:
        df = st.session_state["tabla_maestra"].copy()
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
        idx_max = df["Resultado"].idxmax()
        fila_max = df.loc[idx_max]

        localidad_top = fila_max.get("Localidad", "N/A")
        resultado_top = fila_max["Resultado"]
        resultado_top_pct = resultado_top**2 / 3770 / 0.20021 * 100 if pd.notna(resultado_top) else None

        # Fecha/Hora asociada
        fecha_top = None
        if "FechaHora" in fila_max and pd.notna(fila_max["FechaHora"]):
            fecha_top = fila_max["FechaHora"]
        elif "Fecha" in fila_max and "Hora" in fila_max:
            try:
                fecha_top = datetime.combine(fila_max["Fecha"], fila_max["Hora"])
            except:
                fecha_top = fila_max["Fecha"]
        elif "Fecha" in fila_max:
            fecha_top = fila_max["Fecha"]

        st.markdown("## 🌎 Valor máximo registrado en Argentina")

        col1, col2, col3, col4 = st.columns([2.5, 1.5, 1.5, 1.5])
        col1.metric("Localidad", localidad_top)
        col2.metric("Resultado máximo V/m", f"{resultado_top:.2f}")
        col3.metric("Resultado máximo (%)", f"{resultado_top_pct:.2f}" if resultado_top_pct else "N/A")
        col4.metric("Fecha/Hora", str(fecha_top))
