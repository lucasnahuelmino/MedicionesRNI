import pandas as pd
import streamlit as st


DEFAULT_GLOBAL_YEAR = "2026"


# ============================================================
# CORE FILTER ENGINE
# ============================================================

def apply_global_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica filtros globales definidos en session_state.
    Devuelve una VISTA filtrada (nuevo DF liviano).
    """
    if df is None or df.empty:
        return df

    gf = st.session_state.get("global_filters", {})
    out = df

    # CCTE
    if gf.get("ccte"):
        out = out[out["CCTE"].astype(str).isin(gf["ccte"])]

    # Provincia
    if gf.get("provincia"):
        out = out[out["Provincia"].astype(str).isin(gf["provincia"])]

    # Año
    anio = gf.get("anio", DEFAULT_GLOBAL_YEAR)
    if anio != "Todos" and "Fecha" in out.columns:
        yy = pd.to_datetime(out["Fecha"], dayfirst=True, errors="coerce").dt.year
        out = out[yy == int(anio)]

    return out


# ============================================================
# MÉTRICAS RÁPIDAS
# ============================================================

def get_kpis(df: pd.DataFrame) -> dict:
    """KPIs rápidos para dashboard."""
    if df is None or df.empty:
        return {
            "mediciones": 0,
            "localidades": 0,
            "expedientes": 0,
            "max_resultado": None,
        }

    return {
        "mediciones": len(df),
        "localidades": df["Localidad"].nunique() if "Localidad" in df.columns else 0,
        "expedientes": df["Expediente"].nunique() if "Expediente" in df.columns else 0,
        "max_resultado": df["Resultado"].max() if "Resultado" in df.columns else None,
    }


# ============================================================
# DATA PARA TABLAS
# ============================================================

def get_table_view(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Prepara DF para mostrar en tabla:
    - selecciona columnas
    - limita filas
    """
    if df is None or df.empty:
        return df

    out = df

    if columns:
        cols_ok = [c for c in columns if c in out.columns]
        out = out[cols_ok]

    if limit:
        out = out.head(limit)

    return out


# ============================================================
# AGRUPACIONES COMUNES
# ============================================================

def group_by_provincia(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    return (
        df.groupby("Provincia", observed=True)
        .agg(
            mediciones=("Resultado", "count"),
            max_resultado=("Resultado", "max"),
            promedio=("Resultado", "mean"),
        )
        .reset_index()
        .sort_values("mediciones", ascending=False)
    )


def group_by_ccte(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    return (
        df.groupby("CCTE", observed=True)
        .agg(
            mediciones=("Resultado", "count"),
            max_resultado=("Resultado", "max"),
        )
        .reset_index()
        .sort_values("mediciones", ascending=False)
    )
