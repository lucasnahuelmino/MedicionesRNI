from datetime import datetime, timedelta
import pandas as pd


def format_timedelta_long(td: timedelta) -> str:
    """Convierte un timedelta a formato hh:mm:ss."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def calcular_tiempo_total_por_archivo(df: pd.DataFrame) -> timedelta:
    """
    Calcula la duración total de medición por archivo (considerando saltos de día),
    usando siempre Fecha + Hora y agrupando por 'Nombre Archivo'.
    """
    total = timedelta(0)
    if "Nombre Archivo" in df.columns:
        for _, df_archivo in df.groupby("Nombre Archivo"):
            if "Fecha" in df_archivo.columns and "Hora" in df_archivo.columns:
                for fecha, df_dia in df_archivo.groupby("Fecha"):
                    horas_validas = df_dia["Hora"].dropna()
                    if not horas_validas.empty:
                        dt_inicio = datetime.combine(fecha, horas_validas.min())
                        dt_fin = datetime.combine(fecha, horas_validas.max())
                        delta = dt_fin - dt_inicio
                        if delta.total_seconds() < 0:
                            delta += timedelta(days=1)
                        total += delta
    return total
