import os
from io import BytesIO
import pandas as pd

from utils.excel_utils import find_index_column, extract_numeric_from_text
from utils.geo_utils import parse_dms_to_decimal


# ============================================================
# CORE (NO STREAMLIT)
# ============================================================

def _process_excel_bytes(
    file_bytes: bytes,
    filename: str,
    ccte: str,
    provincia: str,
    localidad: str,
    expediente: str | None,
):
    """Procesa UN archivo Excel y devuelve (df, resumen_dict)."""

    # --- Lectura ---
    df = pd.read_excel(
        BytesIO(file_bytes),
        header=8,
        engine="openpyxl",
    )

    # --- Limpieza estructural ---
    df = df.dropna(axis=1, how="all")

    idx_col = find_index_column(df)
    total_mediciones = len(df)

    if idx_col and idx_col in df.columns:
        df["_idx_num"] = pd.to_numeric(df[idx_col], errors="coerce")
        df = df[df["_idx_num"].notna()]
        if not df.empty:
            total_mediciones = int(df["_idx_num"].max())

    # --- Mapeo de columnas ---
    mapping_candidates = {
        "Fecha": ["fecha"],
        "Hora": ["hora", "time"],
        "Resultado": ["resultado con incertidumbre", "resultado"],
        "Sonda": ["sonda", "sonda utilizada"],
        "Lat": ["latitud", "lat"],
        "Lon": ["longitud", "lon"],
    }

    columnas_map = {}
    for key, cands in mapping_candidates.items():
        found = next(
            (c for c in df.columns if any(cand in str(c).lower() for cand in cands)),
            None,
        )
        if not found and key not in ("Lat", "Lon"):
            raise ValueError(f"No se encontró columna para '{key}'")
        if found:
            columnas_map[key] = found

    df = df.rename(columns={v: k for k, v in columnas_map.items()})

    # --- Metadata fija ---
    df["CCTE"] = ccte
    df["Provincia"] = provincia
    df["Localidad"] = localidad
    df["Expediente"] = expediente or os.path.splitext(filename)[0]
    df["Nombre Archivo"] = filename

    # --- Limpieza de datos ---
    if "Resultado" in df.columns:
        df["Resultado"] = extract_numeric_from_text(df["Resultado"])
        # Calcular porcentaje
        df["Resultado"] = pd.to_numeric(df["Resultado"], errors="coerce")
        df["Resultado_Pct"] = (df["Resultado"] ** 2) / 3770 / 0.20021 * 100

    if "Lat" in df.columns:
        df["Lat"] = df["Lat"].map(parse_dms_to_decimal)

    if "Lon" in df.columns:
        df["Lon"] = df["Lon"].map(parse_dms_to_decimal)

    df.drop(columns=["_idx_num"], errors="ignore", inplace=True)

    # --- Optimización de tipos ---
    for col in [
        "CCTE",
        "Provincia",
        "Localidad",
        "Expediente",
        "Nombre Archivo",
        "Sonda",
    ]:
        if col in df.columns:
            df[col] = df[col].astype("category")

    resumen = {
        "archivo": filename,
        "expediente": df["Expediente"].iloc[0] if not df.empty else None,
        "total_mediciones": total_mediciones,
        "max_resultado": (
            df["Resultado"].max() if "Resultado" in df.columns else None
        ),
    }

    return df, resumen


# ============================================================
# PUBLIC API
# ============================================================

def process_excel(file, metadata: dict):
    """
    Procesa UN archivo Excel (Streamlit UploadedFile).
    Devuelve df procesado.
    """
    df, _ = _process_excel_bytes(
        file.getvalue(),
        file.name,
        metadata["ccte"],
        metadata["provincia"],
        metadata["localidad"],
        metadata.get("expediente"),
    )
    return df


def process_excels(files, metadata: dict):
    """
    Procesa MÚLTIPLES archivos Excel.
    Devuelve:
      - df_final
      - resumen_df
    """
    dfs = []
    resumenes = []

    for file in files:
        df, resumen = _process_excel_bytes(
            file.getvalue(),
            file.name,
            metadata["ccte"],
            metadata["provincia"],
            metadata["localidad"],
            metadata.get("expediente"),
        )
        dfs.append(df)
        resumenes.append(resumen)

    if not dfs:
        return pd.DataFrame(), pd.DataFrame()

    return (
        pd.concat(dfs, ignore_index=True),
        pd.DataFrame(resumenes),
    )


def procesar_archivos(files, ccte: str, provincia: str, localidad: str, expediente: str | None = None):
    """
    Alias para process_excels que acepta parámetros individuales.
    """
    metadata = {
        "ccte": ccte,
        "provincia": provincia,
        "localidad": localidad,
        "expediente": expediente,
    }
    return process_excels(files, metadata)
