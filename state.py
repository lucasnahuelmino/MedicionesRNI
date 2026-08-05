import pandas as pd
import streamlit as st

from db.sqlite_store import load_tabla_maestra_from_db


DEFAULT_GLOBAL_YEAR = 2026


def init_session_state():
    """Inicializa estado de sesión."""
    st.session_state.setdefault("tabla_maestra", pd.DataFrame())
    st.session_state.setdefault("uploaded_files_list", [])
    st.session_state.setdefault("form_ccte", "")
    st.session_state.setdefault("form_provincia", "")
    st.session_state.setdefault("form_localidad", "")
    st.session_state.setdefault("form_expediente", "")
    
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0


def ensure_tabla_maestra_loaded():
    """Carga tabla maestra desde SQLite si está vacía.
    Ahora con @st.cache_data en load_tabla_maestra_from_db, esto es mucho más rápido.
    """
    if st.session_state["tabla_maestra"].empty:
        try:
            st.session_state["tabla_maestra"] = load_tabla_maestra_from_db()
        except Exception as e:
            st.warning(f"No se pudo cargar tabla desde archivosdata/rni.db: {e}")


def reset_tabla_maestra():
    """Recarga tabla maestra desde SQLite."""
    try:
        # Invalida el cache para forzar refresco
        load_tabla_maestra_from_db.clear()
        st.session_state["tabla_maestra"] = load_tabla_maestra_from_db()
        
        # También reconstruir cache de gráficos cuando se recarga tabla
        from db.sqlite_store import rebuild_graficos_cache
        try:
            rebuild_graficos_cache(st.session_state["tabla_maestra"])
        except Exception:
            pass  # Si el rebuild falla, no interrumpir la app
    except Exception as e:
        st.warning(f"No se pudo recargar tabla desde archivosdata/rni.db: {e}")


def init_global_filters():
    """Inicializa filtros globales en session_state."""
    st.session_state.setdefault(
        "global_filters",
        {
            "ccte": [],
            "provincia": [],
            "anio": str(DEFAULT_GLOBAL_YEAR),
        },
    )


def _default_year_option(years: list[int]) -> str:
    """Devuelve el año por defecto: 2026 si existe, sino el más reciente, sino 'Todos'."""
    if DEFAULT_GLOBAL_YEAR in years:
        return str(DEFAULT_GLOBAL_YEAR)
    if years:
        return str(years[0])
    return "Todos"


@st.cache_data
def _extract_years(df: pd.DataFrame) -> list[int]:
    """Obtiene años disponibles desde Fecha o FechaHora.
    Cacheada porque solo depende del contenido del DF.
    """
    years: list[int] = []
    if df is None or df.empty:
        return years

    if "Fecha" in df.columns:
        y = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce").dt.year
        years = sorted(y.dropna().astype(int).unique().tolist(), reverse=True)
    elif "FechaHora" in df.columns:
        y = pd.to_datetime(df["FechaHora"], errors="coerce").dt.year
        years = sorted(y.dropna().astype(int).unique().tolist(), reverse=True)

    return years


def render_global_filters_sidebar(df: pd.DataFrame, sb=st.sidebar):
    """Dibuja filtros globales y los guarda en session_state['global_filters']."""
    init_global_filters()
    gf = st.session_state["global_filters"]

    sb.markdown("### 🌐 Filtros globales")

    # CCTE
    cctes = (
        sorted(df["CCTE"].dropna().astype(str).unique().tolist())
        if df is not None and not df.empty and "CCTE" in df.columns
        else []
    )
    gf["ccte"] = sb.multiselect(
        "CCTE",
        cctes,
        default=gf.get("ccte", []),
        placeholder="Todos",
        key="gf_ccte",
    )

    # Provincia
    provs = (
        sorted(df["Provincia"].dropna().astype(str).unique().tolist())
        if df is not None and not df.empty and "Provincia" in df.columns
        else []
    )
    gf["provincia"] = sb.multiselect(
        "Provincia",
        provs,
        default=gf.get("provincia", []),
        placeholder="Todas",
        key="gf_provincia",
    )

    # Año
    years = _extract_years(df)
    opciones = ["Todos"] + [str(a) for a in years]

    anio_actual = gf.get("anio", _default_year_option(years))
    if anio_actual not in opciones:
        anio_actual = _default_year_option(years)

    gf["anio"] = sb.selectbox(
        "Año",
        opciones,
        index=opciones.index(anio_actual),
        key="gf_anio",
    )

    st.session_state["global_filters"] = gf

    # Mini resumen
    chips = []
    if gf["ccte"]:
        chips.append(f"CCTE: {', '.join(gf['ccte'])}")
    if gf["provincia"]:
        chips.append(f"Prov: {', '.join(gf['provincia'])}")
    if gf["anio"] != "Todos":
        chips.append(f"Año: {gf['anio']}")
    if chips:
        sb.caption(" · ".join(chips))
    else:
        sb.caption("Mostrando: todo")

    # Botón reset
    if sb.button("🔄 Reset filtros", width='stretch'):
        st.session_state["global_filters"] = {
            "ccte": [],
            "provincia": [],
            "anio": _default_year_option(years),
        }
        try:
            st.rerun()
        except Exception:
            pass


def get_df_filtrado_global(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve df filtrado según session_state['global_filters']."""
    init_global_filters()
    gf = st.session_state["global_filters"]

    if df is None or df.empty:
        return df

    out = df.copy()

    # CCTE
    if gf.get("ccte") and "CCTE" in out.columns:
        out = out[out["CCTE"].astype(str).isin([str(x) for x in gf["ccte"]])]

    # Provincia
    if gf.get("provincia") and "Provincia" in out.columns:
        out = out[out["Provincia"].astype(str).isin([str(x) for x in gf["provincia"]])]

    # Año
    anio = gf.get("anio", "Todos")
    if anio != "Todos":
        anio_int = int(anio)
        if "Fecha" in out.columns:
            yy = pd.to_datetime(out["Fecha"], dayfirst=True, errors="coerce").dt.year
            out = out[yy == anio_int]
        elif "FechaHora" in out.columns:
            yy = pd.to_datetime(out["FechaHora"], errors="coerce").dt.year
            out = out[yy == anio_int]

    return out


def has_active_global_filters() -> bool:
    """True si hay algún filtro global (CCTE/Provincia/Año) activo.

    Centraliza una condición que antes estaba duplicada, con el mismo
    texto exacto, en resumen_general.py, graficos.py, gestion_localidades.py
    y semaforo_mapa.py. Al estar en un solo lugar, un cambio futuro en qué
    cuenta como "filtro activo" (por ejemplo agregar un filtro nuevo) queda
    consistente en todas las secciones automáticamente.
    """
    init_global_filters()
    gf = st.session_state.get("global_filters", {})
    return bool(
        gf.get("ccte") or gf.get("provincia") or (gf.get("anio") and gf.get("anio") != "Todos")
    )


def global_filters_human_label() -> str:
    """Texto descriptivo de los filtros globales activos."""
    init_global_filters()
    gf = st.session_state.get(
        "global_filters",
        {"ccte": [], "provincia": [], "anio": str(DEFAULT_GLOBAL_YEAR)},
    )

    chips = []
    if gf.get("ccte"):
        chips.append(f"CCTE: {', '.join([str(x) for x in gf['ccte']])}")
    if gf.get("provincia"):
        chips.append(f"Prov: {', '.join([str(x) for x in gf['provincia']])}")
    if gf.get("anio") and gf["anio"] != "Todos":
        chips.append(f"Año: {gf['anio']}")

    return "Viendo: " + (" · ".join(chips) if chips else "todo")


def render_active_filters_banner(extra: str = ""):
    """Muestra, de forma consistente en todas las secciones, qué filtros
    globales están activos. `extra` permite agregar filtros propios de la
    sección (ej. localidad seleccionada en Gestión) al mismo renglón.
    """
    texto = global_filters_human_label()
    if extra:
        texto = f"{texto} · {extra}"
    st.caption(f"🔎 {texto}")