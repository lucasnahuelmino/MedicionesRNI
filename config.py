from pathlib import Path

# ---------------------- ESTILO ----------------------
BASE_DIR = Path(__file__).parent
CSS_PATH = BASE_DIR / "styles" / "style.css"
ASSETS = BASE_DIR / "assets"

# ---------------------- DB ----------------------
DB_FILE = "archivosdata/rni.db"
TABLE_NAME = "tabla_maestra"

EXPECTED_COLS = [
    "CCTE", "Provincia", "Localidad",
    "Resultado", "Fecha", "Hora",
    "Nombre Archivo", "Expediente",
    "Sonda", "Lat", "Lon",
    "FechaCarga",
]
