from __future__ import annotations

from datetime import timedelta
import pandas as pd


def _normalize_time_str(s: pd.Series) -> pd.Series:
    """
    Normaliza horas tipo:
      "10:08:09 a.m." / "10:08:09 a. m." / "10:08:09 AM" / "22:10:00"
    -> "10:08:09am" / "22:10:00"
    """
    out = s.astype("string").fillna("").str.strip().str.lower()

    # Unificamos variantes español/inglés con puntos/espacios
    # "a. m." -> "am", "p. m." -> "pm"
    out = out.str.replace(r"\s+", "", regex=True)      # quita espacios
    out = out.str.replace(".", "", regex=False)        # quita puntos

    # Por si viene "a.m" / "p.m"
    out = out.str.replace("a:m", "am", regex=False)
    out = out.str.replace("p:m", "pm", regex=False)

    # Si por algún motivo viene "a.m" sin dos puntos ya queda "am" igual
    return out


def add_fechahora(df: pd.DataFrame, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora") -> pd.DataFrame:
    """
    Crea una columna datetime (out_col) combinando fecha y hora en forma robusta.
    Tolera:
      Fecha: "20/03/2025", "2025-03-20", etc.
      Hora : "10:08:09 a.m.", "10:08:09 a. m.", "22:10:00", etc.
    """
    if df is None or df.empty:
        out = df.copy() if df is not None else pd.DataFrame()
        out[out_col] = pd.NaT
        return out

    out = df.copy()

    if fecha_col not in out.columns or hora_col not in out.columns:
        out[out_col] = pd.NaT
        return out

    # Fecha a datetime y "piso" a 00:00:00 para sumar la hora luego
    fecha_dt = pd.to_datetime(out[fecha_col], dayfirst=True, errors="coerce").dt.normalize()

    # Normalizo y parseo hora. Truco: parseo la hora como datetime y saco hour/min/sec.
    hora_norm = _normalize_time_str(out[hora_col])
    hora_dt = pd.to_datetime(hora_norm, errors="coerce")  # puede quedar NaT si viene muy roto

    # Armo timedelta de hora
    hora_td = (
        pd.to_timedelta(hora_dt.dt.hour.fillna(0).astype("int64"), unit="h")
        + pd.to_timedelta(hora_dt.dt.minute.fillna(0).astype("int64"), unit="m")
        + pd.to_timedelta(hora_dt.dt.second.fillna(0).astype("int64"), unit="s")
    )

    out[out_col] = fecha_dt + hora_td

    # Si fecha_dt era NaT o hora_dt era NaT, el resultado debe ser NaT
    invalid = fecha_dt.isna() | hora_dt.isna()
    out.loc[invalid, out_col] = pd.NaT

    return out


def format_timedelta_long(td) -> str:
    """
    Formatea un timedelta en texto tipo:
      '2 h 13 min 05 s'
      '13 min 05 s'
      '0 s'
    """
    if td is None:
        return "0 s"
    if not isinstance(td, timedelta):
        try:
            td = timedelta(seconds=float(td))
        except Exception:
            return "0 s"

    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        total_seconds = 0

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours} h {minutes:02d} min {seconds:02d} s"
    if minutes > 0:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


def calcular_tiempo_total_por_archivo(df: pd.DataFrame) -> timedelta:
    """
    Calcula tiempo total de medición sumando (fin - inicio) por archivo+fecha (si hay Nombre Archivo),
    usando FechaHora robusta (add_fechahora).

    Espera columnas: 'Fecha', 'Hora' y opcional 'Nombre Archivo'.
    """
    if df is None or df.empty:
        return timedelta(0)

    out = add_fechahora(df, fecha_col="Fecha", hora_col="Hora", out_col="FechaHora")
    out = out.dropna(subset=["FechaHora"])
    if out.empty:
        return timedelta(0)

    # Día de medición para agrupar (evita mezclar días)
    out["_Dia"] = out["FechaHora"].dt.date

    group_cols = ["_Dia"]
    if "Nombre Archivo" in out.columns:
        group_cols = ["Nombre Archivo", "_Dia"]

    # Min/Max por grupo y sumo duraciones (vectorizado, sin apply por fila)
    agg = out.groupby(group_cols)["FechaHora"].agg(["min", "max"]).reset_index()
    dur = (agg["max"] - agg["min"]).dropna()

    if dur.empty:
        return timedelta(0)

    total = dur.sum()
    # total es pandas Timedelta; lo convierto a python timedelta
    return total.to_pytimedelta()
