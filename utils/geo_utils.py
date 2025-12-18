import re
import numpy as np
import pandas as pd


def parse_dms_to_decimal(val):
    """Convierte coordenadas DMS (grados, minutos, segundos) a decimal."""
    if pd.isna(val):
        return np.nan
    try:
        return float(val)
    except:
        pass
    s = str(val).strip().replace(",", ".")
    m = re.search(r'([+-]?\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)\D*\s*([NnSsEeWwOo])?', s)
    if m:
        d = float(m.group(1)); mnt = float(m.group(2)); sec = float(m.group(3))
        hemi = (m.group(4) or "").upper()
        dec = abs(d) + mnt/60.0 + sec/3600.0
        if hemi in ("S","W","O"):
            dec = -dec
        return dec
    m2 = re.search(r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', s)
    if m2:
        try:
            return float(m2.group(1))
        except:
            return np.nan
    return np.nan
