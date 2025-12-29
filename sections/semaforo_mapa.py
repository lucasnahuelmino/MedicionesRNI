import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

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
    if df_localidad is None or df_localidad.empty:
        return
    if "Lat" not in df_localidad.columns or "Lon" not in df_localidad.columns:
        return

    MAX_PUNTOS_MAPA = 12000  # ajustable (8000-20000 según la PC)

    # 1) Tomar SOLO columnas mínimas
    cols = [c for c in ["Lat", "Lon", "Resultado"] if c in df_localidad.columns]
    coords = df_localidad[cols].dropna(subset=["Lat", "Lon"]).copy()
    if coords.empty:
        return

    # 2) Asegurar numéricos
    coords["Lat"] = pd.to_numeric(coords["Lat"], errors="coerce")
    coords["Lon"] = pd.to_numeric(coords["Lon"], errors="coerce")
    coords["Resultado"] = pd.to_numeric(coords["Resultado"], errors="coerce")
    coords = coords.dropna(subset=["Lat", "Lon", "Resultado"])
    if coords.empty:
        return

    # 3) Convertir a % y quedarnos con eso
    coords["pct"] = (coords["Resultado"] ** 2) / 3770 / 0.20021 * 100

    # 4) Forzar coordenadas negativas (Argentina)
    coords["lat"] = coords["Lat"].abs() * -1
    coords["lon"] = coords["Lon"].abs() * -1

    # 5) 🔥 Si hay demasiados puntos: SAMPLE automático
    total_puntos = len(coords)
    if total_puntos > MAX_PUNTOS_MAPA:
        coords = coords.sample(n=MAX_PUNTOS_MAPA, random_state=42)
        st.info(
            f"🗺️ Mapa: mostrando una muestra de {MAX_PUNTOS_MAPA:,} puntos "
            f"(de {total_puntos:,}). Filtrá por provincia/CCTE/localidad para ver el detalle completo."
            .replace(",", ".")
        )

    # 6) Colores por % (semaforizado)
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

    def color_semaforo_pct(valor_pct):
        if pd.isna(valor_pct):
            return [200, 200, 200]
        for low, high, color in rangos_colores_map:
            if low <= valor_pct < high:
                return color
        return [0, 0, 0]

    coords["color"] = coords["pct"].apply(color_semaforo_pct)

    # 7) SOLO lo que viaja al JSON del mapa
    coords = coords[["lon", "lat", "pct", "color"]].copy()
    coords["pct"] = coords["pct"].round(2)

    st.subheader("🗺️ Mapa Semaforizado (%)")

    # Fallback por si mean da NaN (casos raros)
    lat0 = float(coords["lat"].mean()) if np.isfinite(coords["lat"].mean()) else -34.61
    lon0 = float(coords["lon"].mean()) if np.isfinite(coords["lon"].mean()) else -58.38

    mapa = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=lat0,
            longitude=lon0,
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
        tooltip={"text": "Resultado (%): {pct}"}
    )

    st.pydeck_chart(mapa, width="stretch")
