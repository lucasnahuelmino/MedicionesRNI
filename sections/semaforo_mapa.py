import pandas as pd
import streamlit as st
import pydeck as pdk


def render_semaforo(max_resultado_pct, df_localidad):
    # ---------------- Semáforo ----------------
    if max_resultado_pct and not df_localidad.empty:
        rangos_colores = [
            (0, 1, "#84C2F5"), (1, 2, "#489DFF"), (2, 4, "#006BD6"),
            (4, 8, "#A9E7A9"), (8, 15, "#89DD89"), (15, 20, "#4D9623"),
            (20, 35, "#D9FF00"), (35, 50, "#F39A6D"), (50, 100, "#E68200"),
            (100, float("inf"), "#CC0000")
        ]
        _ = next((color for low, high, color in rangos_colores if low <= max_resultado_pct < high), "#FFFFFF")

        # Imagen del semáforo de colores
        st.image("assets/mapa_color.png", caption="Escala de colores para interpretar los resultados", width="stretch")


def render_mapa(df_localidad):
    # ------------------- MAPA INTERACTIVO ------------------
    if "Lat" in df_localidad.columns and "Lon" in df_localidad.columns and not df_localidad.empty:
        coords = df_localidad.dropna(subset=["Lat", "Lon"])[["Lat", "Lon", "Localidad", "Resultado"]].copy()
        if not coords.empty:
            # Forzamos coordenadas negativas (Argentina)
            coords["lat"] = coords["Lat"].apply(lambda x: -abs(x))
            coords["lon"] = coords["Lon"].apply(lambda x: -abs(x))

            rangos_colores_map = [
                (0, 1, [132, 194, 245]),
                (1, 2, [72, 157, 255]),
                (2, 4, [0, 107, 214]),
                (4, 8, [169, 231, 169]),
                (8, 15, [137, 221, 137]),
                (15, 20, [77, 150, 35]),
                (20, 35, [217, 255, 0]),
                (35, 50, [243, 154, 109]),
                (50, 100, [230, 130, 0]),
                (100, float("inf"), [204, 0, 0])
            ]

            def color_semaforo(valor):
                if pd.isna(valor):
                    return [200, 200, 200]
                for low, high, color in rangos_colores_map:
                    if low <= valor < high:
                        return color
                return [0, 0, 0]

            coords["color"] = coords["Resultado"].apply(color_semaforo)

            st.subheader("🗺️ Mapa Semaforizado")
            mapa = pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(
                    latitude=coords["lat"].mean(),
                    longitude=coords["lon"].mean(),
                    zoom=6,
                    pitch=0,
                ),
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=coords,
                        get_position='[lon, lat]',
                        get_fill_color='color',
                        get_radius=12,
                        pickable=True,
                    )
                ],
                tooltip={"text": "Localidad: {Localidad}\nResultado: {Resultado}"}
            )
            st.pydeck_chart(mapa, width="stretch")
