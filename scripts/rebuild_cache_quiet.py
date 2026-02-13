import os
import sys
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
warnings.filterwarnings('ignore')

from db import sqlite_store

try:
    df = sqlite_store.load_tabla_maestra_from_db()
    print('tabla_maestra_rows', len(df))
except Exception as e:
    print('error_loading_tabla_maestra', e)

try:
    sqlite_store.rebuild_resumen_cache()
    resumen = sqlite_store.load_resumen_from_cache()
    print('resumen_rows_after_rebuild', len(resumen))
    if not resumen.empty:
        print(resumen[['CCTE','Provincia','Localidad','Mediciones','TiempoTrabajadoSegundos']].head(10).to_string(index=False))
except Exception as e:
    print('error_rebuild', e)

try:
    sqlite_store.rebuild_graficos_cache()
    print('graficos_cache_rebuilt', 'success')
except Exception as e:
    print('error_graficos_rebuild', e)
