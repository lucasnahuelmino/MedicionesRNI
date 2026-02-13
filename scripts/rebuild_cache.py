import os
import sys

# Asegurar que el root del proyecto esté en sys.path para importar paquetes locales
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import sqlite_store

print("Cargando tabla maestra desde DB...")
try:
    df = sqlite_store.load_tabla_maestra_from_db()
    print("Registros en tabla maestra:", len(df))
except Exception as e:
    print("Error cargando tabla maestra:", e)

print("Lanzando rebuild_resumen_cache()...")
try:
    sqlite_store.rebuild_resumen_cache()
    resumen = sqlite_store.load_resumen_from_cache()
    print("Registros en resumen_localidades después de rebuild:", len(resumen))
    if not resumen.empty:
        print(resumen.head(10))
except Exception as e:
    print("Error durante rebuild:", e)
