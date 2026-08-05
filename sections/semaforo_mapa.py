import sqlite3
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import streamlit as st
from streamlit_folium import st_folium
from state import get_df_filtrado_global, has_active_global_filters

# Bounding box aproximado de Argentina (incluye Antártida Argentina).
# Se usa para validar/corregir signos de lat/lon en vez de forzarlos a ciegas.
LAT_MIN, LAT_MAX = -90.0, -21.0
LON_MIN, LON_MAX = -74.0, -53.0


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

@st.cache_data(show_spinner=False)
def _prep_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza y valida coordenadas, calcula color y texto de popup.
    Cacheada por contenido de df: evita recalcular en cada rerun/click.
    """
    coords = df.copy()

    coords["Lat"] = pd.to_numeric(coords["Lat"], errors="coerce")
    coords["Lon"] = pd.to_numeric(coords["Lon"], errors="coerce")
    coords["Resultado"] = pd.to_numeric(coords["Resultado"], errors="coerce")
    coords["Resultado_Pct"] = pd.to_numeric(coords["Resultado_Pct"], errors="coerce")

    coords = coords.dropna(subset=["Lat", "Lon", "Resultado_Pct"])
    if coords.empty:
        return coords

    # Antes: se forzaba lat/lon a negativo a ciegas (abs()*-1), lo que podía
    # "corregir" coordenadas realmente inválidas sin avisar. Ahora: probamos
    # el signo original y, si no cae dentro de Argentina, probamos el signo
    # invertido; si ninguno es válido, se descarta el punto (en vez de
    # graficarlo en el lugar equivocado).
    lat_raw, lon_raw = coords["Lat"], coords["Lon"]

    def _fix(lat, lon):
        candidatos = [(lat, lon), (-abs(lat), -abs(lon))]
        for la, lo in candidatos:
            if LAT_MIN <= la <= LAT_MAX and LON_MIN <= lo <= LON_MAX:
                return la, lo
        return None, None

    fixed = [_fix(la, lo) for la, lo in zip(lat_raw, lon_raw)]
    coords["lat"] = [f[0] for f in fixed]
    coords["lon"] = [f[1] for f in fixed]
    coords = coords.dropna(subset=["lat", "lon"])

    if coords.empty:
        return coords

    coords["porcentaje"] = coords["Resultado_Pct"]
    coords["color"] = coords["porcentaje"].apply(get_color_por_pct)
    coords["pct_display"] = coords["porcentaje"].round(2)

    return coords


_LEGEND_HTML = """
<div style="position: fixed; bottom: 25px; left: 25px; z-index: 9999;
            background: white; padding: 10px 14px; border-radius: 8px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-family: Arial; font-size: 12px;">
  <b>Referencias (% del límite)</b><br/>
  <span style="background:#84C2F5;width:10px;height:10px;display:inline-block;"></span> 0–1%
  <span style="background:#489DFF;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> 1–2%
  <span style="background:#006BD6;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> 2–4%<br/>
  <span style="background:#89DD89;width:10px;height:10px;display:inline-block;"></span> 8–15%
  <span style="background:#4D9623;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> 15–20%
  <span style="background:#D9FF00;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> 20–35%<br/>
  <span style="background:#F39A6D;width:10px;height:10px;display:inline-block;"></span> 35–50%
  <span style="background:#E68200;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> 50–100%
  <span style="background:#CC0000;width:10px;height:10px;display:inline-block;margin-left:6px;"></span> >100%
</div>
"""


def render_mapa_global():

    # Datos base: tabla completa. El usuario decide si aplicar filtros
    # globales con el toggle de abajo (antes esto se ignoraba siempre y
    # sin avisar, lo que rompía la relación con los filtros del resto de la app).
    df_all = st.session_state.get("tabla_maestra", pd.DataFrame())
    if df_all is None or df_all.empty:
        df_all = load_mediciones_from_db()

    if df_all.empty:
        st.info("No hay datos disponibles para cargar el mapa (tabla vacía en DB).")
        return

    required_cols = {"Lat", "Lon", "Resultado", "Resultado_Pct"}
    if not required_cols.issubset(df_all.columns):
        st.warning("Faltan columnas requeridas en la tabla mediciones_rni.")
        return

    hay_filtros_globales = has_active_global_filters()

    # ========================================================
    # CONTROLES
    # ========================================================
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        if "map_view_mode" not in st.session_state:
            st.session_state.map_view_mode = "todos"
        st.session_state.map_view_mode = st.radio(
            "Puntos a mostrar",
            options=["todos", "max_localidad"],
            format_func=lambda v: "🌎 Todos los puntos" if v == "todos" else "📍 Máximo por localidad",
            index=0 if st.session_state.map_view_mode == "todos" else 1,
            horizontal=True,
        )

    with c2:
        usar_filtros = st.checkbox(
            "Aplicar filtros globales al mapa",
            value=False,
            help="Por defecto el mapa muestra todos los puntos aunque haya filtros "
                 "globales activos, para que nunca quede vacío. Activá esto para "
                 "que respete los mismos filtros (CCTE/Provincia/Año) que el resto de la app.",
        )

    with c3:
        pct_min = st.slider(
            "% mínimo a mostrar",
            min_value=0, max_value=100, value=0, step=5,
            help="Subí este valor para aligerar el mapa mostrando solo los puntos más relevantes.",
        )

    if usar_filtros and hay_filtros_globales:
        df = get_df_filtrado_global(df_all)
        st.caption("Mapa filtrado según filtros globales activos.")
    else:
        df = df_all
        if hay_filtros_globales:
            st.caption("Mapa mostrando todos los puntos (filtros globales no aplicados). Activá el toggle para respetarlos.")

    coords = _prep_coords(df)

    if coords.empty:
        st.info("No hay coordenadas válidas para graficar con la selección actual.")
        return

    mostrar_tipo = st.session_state.map_view_mode

    if mostrar_tipo == "max_localidad":
        coords = coords.loc[
            coords.groupby(["Localidad", "Provincia"])["porcentaje"].idxmax()
        ]

    if pct_min > 0:
        coords = coords[coords["porcentaje"] >= pct_min]

    if coords.empty:
        st.info("Ningún punto cumple con el % mínimo seleccionado.")
        return

    MAX_PUNTOS_MAPA = 12000
    total_disponible = len(coords)
    if total_disponible > MAX_PUNTOS_MAPA and mostrar_tipo == "todos":
        coords = coords.sample(n=MAX_PUNTOS_MAPA, random_state=42)
        st.caption(
            f"Mostrando una muestra de {MAX_PUNTOS_MAPA:,} de {total_disponible:,} puntos "
            "para mantener el mapa rápido. Usá '📍 Máximo por localidad' o subí el % mínimo "
            "para ver el set completo más liviano."
        )

    st.caption(f"Puntos en el mapa: {len(coords):,}".replace(",", "."))

    lat0 = coords["lat"].mean()
    lon0 = coords["lon"].mean()

    m = folium.Map(
        location=[lat0, lon0],
        zoom_start=5,
        tiles="CartoDB positron",
        prefer_canvas=True,  # renderizado más rápido con muchos puntos
    )

    # Clustering: agrupa puntos cercanos en zoom alejado. Esto reduce
    # drásticamente el trabajo del navegador cuando hay miles de puntos,
    # que era la causa principal de la lentitud al abrir el mapa.
    cluster = MarkerCluster(disableClusteringAtZoom=11).add_to(m)

    for row in coords.itertuples(index=False):
        popup_text = f"""
        <div style="font-family: Arial; width: 240px;">
            <b>{row.Localidad}</b><br/>
            <b>Provincia:</b> {row.Provincia}<br/>
            <b>Porcentaje:</b> {row.pct_display:.2f}%<br/>
            <b>Resultado (V/m):</b> {row.Resultado:.2f}<br/>
            <b>Fecha:</b> {getattr(row, 'Fecha', 'N/A')}<br/>
        </div>
        """
        folium.CircleMarker(
            location=[row.lat, row.lon],
            radius=6,
            popup=folium.Popup(popup_text, max_width=260),
            color=row.color,
            fill=True,
            fillColor=row.color,
            fillOpacity=0.85,
            weight=1,
            opacity=0.9,
        ).add_to(cluster)

    m.get_root().html.add_child(folium.Element(_LEGEND_HTML))

    st_folium(
        m,
        width=None,
        height=750,
        use_container_width=True,
        returned_objects=[],
    )

    with st.expander("⬇️ Descargar puntos mostrados en el mapa"):
        cols_export = [c for c in ["Localidad", "Provincia", "CCTE", "Fecha", "Resultado", "Resultado_Pct"] if c in coords.columns]
        st.download_button(
            "Descargar CSV",
            data=coords[cols_export].to_csv(index=False).encode("utf-8"),
            file_name="puntos_mapa_rni.csv",
            mime="text/csv",
        )