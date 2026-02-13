import numpy as np
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import streamlit as st
from streamlit_folium import st_folium

# ============================================================
# 🎨 SEMÁFORO GLOBAL
# ============================================================

def render_semaforo_global(df):
    if df is None or df.empty:
        return

    if "Resultado_Pct" not in df.columns:
        return

    resultados = pd.to_numeric(df["Resultado_Pct"], errors="coerce").dropna()
    if resultados.empty:
        return

    max_pct = resultados.max()

    st.subheader("🚦 Escala de interpretación")
    st.image(
        "assets/mapa_color.png",
        caption=f"Máximo detectado: {max_pct:.2f} %",
        use_container_width=True,
    )


# ============================================================
# 🗺️ FUNCIONES AUXILIARES
# ============================================================

def get_color_por_pct(pct):
    rangos_colores = [
        (0, 1, "#84C2F5"),
        (1, 2, "#489DFF"),
        (2, 4, "#006BD6"),
        (4, 8, "#A9E7A9"),
        (8, 15, "#89DD89"),
        (15, 20, "#4D9623"),
        (20, 35, "#D9FF00"),
        (35, 50, "#F39A6D"),
        (50, 100, "#E68200"),
        (100, float("inf"), "#CC0000"),
    ]

    for low, high, color in rangos_colores:
        if low <= pct < high:
            return color

    return "#C8C8C8"


# ============================================================
# 🗺️ MAPA GLOBAL
# ============================================================

def render_mapa_global(df):

    if df is None or df.empty:
        st.info("No hay datos para mostrar en el mapa.")
        return

    required_cols = {"Lat", "Lon", "Resultado", "Resultado_Pct"}
    if not required_cols.issubset(df.columns):
        st.warning(f"Faltan columnas requeridas: {required_cols}")
        return

    MAX_PUNTOS_MAPA = 12000

    # ------------------ PREPARACIÓN ------------------

    coords = df[[
        "Lat", "Lon",
        "Resultado",
        "Resultado_Pct",
        "Fecha",
        "Localidad",
        "Provincia"
    ]].copy()

    coords["Lat"] = pd.to_numeric(coords["Lat"], errors="coerce")
    coords["Lon"] = pd.to_numeric(coords["Lon"], errors="coerce")
    coords["Resultado"] = pd.to_numeric(coords["Resultado"], errors="coerce")
    coords["Resultado_Pct"] = pd.to_numeric(coords["Resultado_Pct"], errors="coerce")

    coords = coords.dropna(subset=["Lat", "Lon", "Resultado_Pct"])

    if coords.empty:
        st.info("No hay coordenadas válidas para el mapa.")
        return

    # Usamos directamente la columna nueva
    coords["porcentaje"] = coords["Resultado_Pct"]

    # Forzar Argentina
    coords["lat"] = coords["Lat"].abs() * -1
    coords["lon"] = coords["Lon"].abs() * -1

    # ------------------ OPCIÓN DE FILTRO ------------------

    col1, col2 = st.columns([1, 3])

    with col1:
        mostrar_tipo = st.radio(
            "Vista del mapa:",
            ["Todos los puntos", "Máximo por localidad"],
            key="mapa_tipo_vista"
        )

    if mostrar_tipo == "Máximo por localidad":
        coords = coords.loc[
            coords.groupby(["Localidad", "Provincia"])["porcentaje"].idxmax()
        ]

    total = len(coords)

    if total > MAX_PUNTOS_MAPA and mostrar_tipo == "Todos los puntos":
        coords = coords.sample(n=MAX_PUNTOS_MAPA, random_state=42)
        st.info(
            f"🗺️ Mostrando {MAX_PUNTOS_MAPA:,} puntos "
            f"de {total:,} registros totales."
            .replace(",", ".")
        )

    coords["color"] = coords["porcentaje"].apply(get_color_por_pct)
    coords["pct_display"] = coords["porcentaje"].round(2)

    # ------------------ MAPA ------------------

    st.markdown("## 🗺️ Mapa nacional de mediciones RNI (%)")

    lat0 = coords["lat"].mean()
    lon0 = coords["lon"].mean()

    m = folium.Map(
        location=[lat0, lon0],
        zoom_start=5,
        tiles="https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
        attr="CartoDB"
    )

    for _, row in coords.iterrows():

        popup_text = f"""
        <div style="font-family: Arial; width: 250px;">
            <b>{row['Localidad']}</b><br/>
            <b>Provincia:</b> {row['Provincia']}<br/>
            <b>Porcentaje:</b> {row['pct_display']:.2f}%<br/>
            <b>Resultado (V/m):</b> {row['Resultado']:.2f}<br/>
            <b>Fecha:</b> {row.get('Fecha', 'N/A')}<br/>
        </div>
        """

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            popup=folium.Popup(popup_text, max_width=300),
            color=row["color"],
            fill=True,
            fillColor=row["color"],
            fillOpacity=0.8,
            weight=1,
            opacity=0.9
        ).add_to(m)

    st_folium(m, width=1400, height=700)


