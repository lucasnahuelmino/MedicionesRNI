import sqlite3
import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium
from state import get_df_filtrado_global


# ============================================================
# 🔌 CARGA DESDE SQLITE
# ============================================================

def load_mediciones_from_db():

    DB_PATH = "archivosdata/rni.db"

    try:
        conn = sqlite3.connect(DB_PATH)

        query = """
            SELECT
                Lat,
                Lon,
                Resultado,
                Resultado_Pct,
                Fecha,
                Localidad,
                Provincia
            FROM mediciones_rni
        """

        df = pd.read_sql(query, conn)
        conn.close()

        return df

    except Exception as e:
        st.error(f"Error al cargar datos desde SQLite: {e}")
        return pd.DataFrame()


def _load_mediciones_filtradas_global() -> pd.DataFrame:
    """Carga mediciones y aplica los filtros globales actuales."""
    df = st.session_state.get("tabla_maestra", pd.DataFrame())
    if df is None or df.empty:
        df = load_mediciones_from_db()
    if df is None or df.empty:
        return pd.DataFrame()
    return get_df_filtrado_global(df)


# ============================================================
# 🎨 SEMÁFORO GLOBAL
# ============================================================

def render_semaforo_global():

    df = _load_mediciones_filtradas_global()

    if df.empty:
        st.info("No hay datos disponibles.")
        return

    if "Resultado_Pct" not in df.columns:
        st.warning("La columna Resultado_Pct no existe en la base.")
        return

    resultados = pd.to_numeric(df["Resultado_Pct"], errors="coerce").dropna()

    if resultados.empty:
        st.info("No hay valores válidos para el semáforo.")
        return

    max_pct = resultados.max()

    st.subheader("🚦 Escala de interpretación")
    st.image(
        "assets/mapa_color.png",
        caption=f"Máximo detectado: {max_pct:.2f} %",
        width='stretch',
    )


# ============================================================
# 🎨 COLOR POR PORCENTAJE
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

def render_mapa_global():

    df = _load_mediciones_filtradas_global()

    if df.empty:
        st.info("No hay datos para mostrar en el mapa.")
        return

    required_cols = {"Lat", "Lon", "Resultado", "Resultado_Pct"}
    if not required_cols.issubset(df.columns):
        st.warning("Faltan columnas requeridas en la tabla mediciones_rni.")
        return

    coords = df.copy()

    coords["Lat"] = pd.to_numeric(coords["Lat"], errors="coerce")
    coords["Lon"] = pd.to_numeric(coords["Lon"], errors="coerce")
    coords["Resultado"] = pd.to_numeric(coords["Resultado"], errors="coerce")
    coords["Resultado_Pct"] = pd.to_numeric(coords["Resultado_Pct"], errors="coerce")

    coords = coords.dropna(subset=["Lat", "Lon", "Resultado_Pct"])

    if coords.empty:
        st.info("No hay coordenadas válidas.")
        return

    coords["porcentaje"] = coords["Resultado_Pct"]
    coords["lat"] = coords["Lat"].abs() * -1
    coords["lon"] = coords["Lon"].abs() * -1

    # ========================================================
    # BOTONES EN VEZ DE RADIO
    # ========================================================

    if "map_view_mode" not in st.session_state:
        st.session_state.map_view_mode = "todos"

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🌎 Todos los puntos", width='stretch'):
            st.session_state.map_view_mode = "todos"

    with col2:
        if st.button("📍 Máximo por localidad", width='stretch'):
            st.session_state.map_view_mode = "max_localidad"

    mostrar_tipo = st.session_state.map_view_mode

    if mostrar_tipo == "max_localidad":
        coords = coords.loc[
            coords.groupby(["Localidad", "Provincia"])["porcentaje"].idxmax()
        ]

    MAX_PUNTOS_MAPA = 12000

    if len(coords) > MAX_PUNTOS_MAPA and mostrar_tipo == "todos":
        coords = coords.sample(n=MAX_PUNTOS_MAPA, random_state=42)

    coords["color"] = coords["porcentaje"].apply(get_color_por_pct)
    coords["pct_display"] = coords["porcentaje"].round(2)

    lat0 = coords["lat"].mean()
    lon0 = coords["lon"].mean()

    m = folium.Map(
        location=[lat0, lon0],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    for _, row in coords.iterrows():

        popup_text = f"""
        <div style="font-family: Arial; width: 240px;">
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
            popup=popup_text,
            color=row["color"],
            fill=True,
            fillColor=row["color"],
            fillOpacity=0.85,
            weight=1,
            opacity=0.9
        ).add_to(m)

    st_folium(
        m,
        width=1400,
        height=1000,
        returned_objects=[]
    )
