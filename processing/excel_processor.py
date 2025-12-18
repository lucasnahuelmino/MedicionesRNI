import os
import pandas as pd
import streamlit as st

from utils.excel_utils import find_index_column, extract_numeric_from_text
from utils.geo_utils import parse_dms_to_decimal


def procesar_archivos(uploaded_files, ccte, provincia, localidad, expediente):
    """Procesa múltiples archivos Excel y los integra en la tabla maestra."""
    lista_procesados, resumen_archivos = [], []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, header=8, engine="openpyxl")
        except Exception as e:
            st.warning(f"No se pudo leer {file.name}: {e}")
            continue

        df = df.dropna(axis=1, how="all")
        idx_col = find_index_column(df)
        total_mediciones = len(df)

        # Detecta número de mediciones
        if idx_col:
            df["_idx_num"] = pd.to_numeric(df[idx_col], errors="coerce")
            df = df[df["_idx_num"].notna()]
            if not df.empty:
                total_mediciones = int(df["_idx_num"].max())

        # Mapeo de columnas esperadas
        mapping_candidates = {
            "Fecha": ["fecha"],
            "Hora": ["hora", "time"],
            "Resultado": ["resultado con incertidumbre", "resultado"],
            "Sonda": ["sonda", "sonda utilizada"],
            "Lat": ["latitud", "lat"],
            "Lon": ["longitud", "lon"]
        }

        columnas_map, missing = {}, False
        for key, cands in mapping_candidates.items():
            found = next((c for c in df.columns if any(cand in str(c).lower() for cand in cands)), None)
            if not found and key not in ("Lat", "Lon"):
                st.warning(f"Archivo {file.name}: no se encontró columna para '{key}'")
                missing = True
                break
            if found:
                columnas_map[key] = found
        if missing:
            continue

        # Renombrado y limpieza
        df = df.rename(columns={v: k for k, v in columnas_map.items()})
        df["CCTE"], df["Provincia"], df["Localidad"] = ccte, provincia, localidad
        df["Expediente"] = expediente if expediente else os.path.splitext(file.name)[0]
        df["Nombre Archivo"] = file.name

        # Limpieza y formateo de campos
        if "Resultado" in df.columns:
            df["Resultado"] = extract_numeric_from_text(df["Resultado"])
        if "Lat" in df.columns:
            df["Lat"] = df["Lat"].apply(parse_dms_to_decimal)
        if "Lon" in df.columns:
            df["Lon"] = df["Lon"].apply(parse_dms_to_decimal)
        df.drop(columns=["_idx_num"], errors="ignore", inplace=True)

        lista_procesados.append(df)
        resumen_archivos.append({
            "archivo": file.name,
            "expediente": df["Expediente"].iloc[0],
            "total mediciones": total_mediciones,
            "max_resultado": df["Resultado"].max() if "Resultado" in df.columns else None
        })

    if lista_procesados:
        return pd.concat(lista_procesados, ignore_index=True), pd.DataFrame(resumen_archivos)
    return pd.DataFrame(), pd.DataFrame()
