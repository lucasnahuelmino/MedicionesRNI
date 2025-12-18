import pandas as pd


def extract_numeric_from_text(series):
    """Extrae valores numéricos (float) desde texto."""
    s = series.astype(str).str.replace(",", ".", regex=False)
    num = s.str.extract(r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', expand=False)
    return pd.to_numeric(num, errors="coerce")


def find_index_column(df):
    """Detecta la columna que actúa como índice numérico."""
    candidates = ["índice", "indice", "index", "nro", "nº", "n°", "num", "numero", "#"]
    for c in df.columns:
        if any(cand in str(c).lower() for cand in candidates):
            return c
    return None
