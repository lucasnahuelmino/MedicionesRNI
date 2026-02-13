import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from db.sqlite_store import (
    load_graficos_ccte_summary,
    load_graficos_provincia_ccte,
    load_graficos_mensual,
    load_graficos_hotspots
)

print("=" * 60)
print("VERIFICACIÓN DE DATOS DE CACHE DE GRÁFICOS")
print("=" * 60)

try:
    print("\n✓ Cargando CCTE Summary...")
    df_ccte = load_graficos_ccte_summary()
    print(f"  → {len(df_ccte)} filas")
    print(f"  → Total Puntos: {df_ccte['Puntos'].sum():,}")
    print(f"  → CCTEs: {df_ccte['CCTE'].tolist()}")
    
    print("\n✓ Cargando Relacion Provincia-CCTE...")
    df_prov = load_graficos_provincia_ccte()
    print(f"  → {len(df_prov)} pares Provincia/CCTE")
    
    print("\n✓ Cargando Datos Mensuales...")
    df_mes = load_graficos_mensual()
    print(f"  → {len(df_mes)} meses con datos")
    print(f"  → Total Puntos: {df_mes['Puntos'].sum():,}")
    
    print("\n✓ Cargando Hotspots...")
    df_hot = load_graficos_hotspots()
    print(f"  → {len(df_hot)} localidades con hotspots")
    if not df_hot.empty:
        top3 = df_hot.head(3)
        for _, row in top3.iterrows():
            print(f"    - {row['Localidad']}: {row['ResultadoMaxVm']:.2f} V/m ({row['ResultadoMaxPct']:.1f}%)")
    
    print("\n" + "=" * 60)
    print("✓ TODOS LOS DATOS DE CACHE CARGADOS CORRECTAMENTE")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
