from pathlib import Path

# ---------------------- ESTILO ----------------------
BASE_DIR = Path(__file__).parent
CSS_PATH = BASE_DIR / "styles" / "style.css"
ASSETS = BASE_DIR / "assets"

# ---------------------- DB ----------------------
# La configuración real de la base (ruta y nombre de tabla) vive en
# db/sqlite_store.py (DB_PATH = archivosdata/rni.db, tabla mediciones_rni).
# Antes había acá un DB_FILE/TABLE_NAME que apuntaban a una tabla
# "tabla_maestra" inexistente y no se usaban en ningún lado — se quitaron
# para no inducir a error a futuro. Si necesitás las columnas esperadas de
# un Excel de carga, están en processing/excel_processor.py.