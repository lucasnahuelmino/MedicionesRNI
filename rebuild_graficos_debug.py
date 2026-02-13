import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from db import sqlite_store

print("=" * 60)
print("Iniciando rebuild de cache de gráficos...")
print("=" * 60)

try:
    print("\n1. Cargando tabla maestra...")
    df = sqlite_store.load_tabla_maestra_from_db()
    print(f"   ✓ Cargados {len(df)} registros")
    
    print("\n2. Ejecutando rebuild_graficos_cache()...")
    sqlite_store.rebuild_graficos_cache(df)
    print(f"   ✓ Rebuild completado")
    
    print("\n3. Verificando datos en cache...")
    import sqlite3
    conn = sqlite3.connect('archivosdata/rni.db')
    cursor = conn.cursor()
    
    tables = [
        'graficos_ccte_summary',
        'graficos_provincia_ccte', 
        'graficos_mensual',
        'graficos_hotspots'
    ]
    
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} filas")
    
    conn.close()
    print("\n✓ Cache reconstruido exitosamente")
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    traceback.print_exc()
