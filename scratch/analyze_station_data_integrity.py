import os
import sys
import re
import pandas as pd

project_dir = r"c:\Users\ROBERTO\Proyectos_Python\TFM_TUI_Tenerife\AI_Dashboard_Core"

# 1. Datos pegados por el usuario
user_input = """
estacion_60.parquet
3.36 MiB
estacion_207.parquet
3.41 MiB
estacion_210.parquet
3.77 MiB
estacion_213.parquet
3.88 MiB
estacion_211.parquet
3.93 MiB
estacion_212.parquet
4.19 MiB
estacion_194.parquet
4.97 MiB
estacion_204.parquet
8.35 MiB
estacion_199.parquet
8.94 MiB
estacion_198.parquet
9.21 MiB
estacion_201.parquet
9.33 MiB
estacion_88.parquet
12.62 MiB
estacion_54.parquet
13.56 MiB
estacion_75.parquet
14.28 MiB
estacion_57.parquet
14.85 MiB
estacion_73.parquet
15.09 MiB
estacion_71.parquet
15.2 MiB
estacion_80.parquet
15.27 MiB
estacion_78.parquet
15.28 MiB
estacion_65.parquet
15.29 MiB
estacion_66.parquet
15.3 MiB
estacion_76.parquet
15.31 MiB
estacion_63.parquet
15.33 MiB
estacion_81.parquet
15.35 MiB
estacion_68.parquet
15.35 MiB
estacion_67.parquet
15.38 MiB
estacion_74.parquet
15.38 MiB
estacion_69.parquet
15.39 MiB
estacion_70.parquet
15.39 MiB
estacion_64.parquet
15.4 MiB
estacion_58.parquet
15.4 MiB
estacion_86.parquet
15.46 MiB
estacion_61.parquet
15.69 MiB
estacion_62.parquet
15.69 MiB
estacion_77.parquet
15.77 MiB
estacion_93.parquet
18.48 MiB
estacion_13.parquet
18.64 MiB
estacion_82.parquet
18.7 MiB
estacion_11.parquet
18.7 MiB
estacion_83.parquet
18.79 MiB
estacion_56.parquet
18.8 MiB
estacion_91.parquet
18.81 MiB
estacion_7.parquet
18.82 MiB
estacion_103.parquet
18.84 MiB
estacion_106.parquet
18.87 MiB
estacion_92.parquet
18.9 MiB
estacion_85.parquet
18.94 MiB
estacion_97.parquet
18.97 MiB
estacion_95.parquet
18.98 MiB
estacion_190.parquet
18.98 MiB
estacion_102.parquet
18.98 MiB
estacion_5.parquet
18.99 MiB
estacion_98.parquet
19.02 MiB
estacion_181.parquet
19.05 MiB
estacion_101.parquet
19.06 MiB
estacion_87.parquet
19.09 MiB
estacion_2.parquet
19.09 MiB
estacion_105.parquet
19.13 MiB
estacion_1.parquet
19.18 MiB
estacion_10.parquet
19.18 MiB
estacion_96.parquet
19.27 MiB
estacion_94.parquet
19.33 MiB
estacion_90.parquet
19.35 MiB
estacion_89.parquet
19.88 MiB
"""

# Parsear tamaños
uploaded_sizes = {}
lines = [l.strip() for l in user_input.strip().split("\n") if l.strip()]
for i in range(0, len(lines), 2):
    file_name = lines[i]
    size_str = lines[i+1]
    
    st_id = int(re.search(r"estacion_(\d+)\.parquet", file_name).group(1))
    size_val = float(size_str.split()[0])
    uploaded_sizes[st_id] = size_val

# 2. Cargar CSVs de metadatos
csv_estaciones = os.path.join(project_dir, "data", "estaciones-meteorologicas.csv")
csv_sensores = os.path.join(project_dir, "data", "sensores-meteorologicos.csv")

if not os.path.exists(csv_estaciones) or not os.path.exists(csv_sensores):
    print("[ERROR] No se encuentran los CSVs en la carpeta data/")
    sys.exit(1)

df_est = pd.read_csv(csv_estaciones, encoding="utf-8-sig")
df_est.columns = [c.strip().lstrip('\ufeff') for c in df_est.columns]

df_sens = pd.read_csv(csv_sensores, encoding="utf-8-sig")
df_sens.columns = [c.strip().lstrip('\ufeff') for c in df_sens.columns]

# Contar sensores por estación
sensor_counts = df_sens.groupby("estacion_id")["sensor_id"].count().to_dict()

# 3. Analizar completitud
current_year = 2026
results = []

for idx, row in df_est.iterrows():
    st_id = int(row["estacion_id"])
    nombre = row["estacion_nombre"]
    
    # Calcular años activa
    fecha_inst = row["fecha_instalacion"]
    year_inst = int(fecha_inst.split("-")[0]) if isinstance(fecha_inst, str) else 1996
    years_active = current_year - year_inst
    if years_active <= 0:
        years_active = 1
        
    num_sensors = sensor_counts.get(st_id, 0)
    
    # Puntuación de volumen teórico: años activa * número de sensores
    theoretical_volume = years_active * num_sensors
    
    file_size = uploaded_sizes.get(st_id, None)
    
    results.append({
        "indice": idx + 1,
        "id_estacion": st_id,
        "nombre": nombre,
        "year_inst": year_inst,
        "years_active": years_active,
        "num_sensors": num_sensors,
        "theoretical_volume": theoretical_volume,
        "file_size_mib": file_size
    })

df_res = pd.DataFrame(results)

# Separar faltantes de presentes
df_missing = df_res[df_res["file_size_mib"].isna()].copy()
df_present = df_res[df_res["file_size_mib"].notna()].copy()

# Calcular ratio de densidad de datos (MiB por volumen teórico de datos)
df_present["ratio"] = df_present["file_size_mib"] / df_present["theoretical_volume"]

# Encontrar estaciones con ratio anómalamente bajo (umbral: menos del 50% de la mediana)
median_ratio = df_present["ratio"].median()
threshold = median_ratio * 0.50

df_undercompleted = df_present[df_present["ratio"] < threshold].copy()

# Imprimir resultados
print("="*70)
print("1. ESTACIONES QUE FALTAN POR COMPLETO (0% en Azure)")
print("="*70)
if df_missing.empty:
    print("¡No falta ninguna estación!")
else:
    for _, row in df_missing.iterrows():
        print(f"  [{int(row['indice'])}] ID {int(row['id_estacion'])}: {row['nombre']} (Instalación: {int(row['year_inst'])}, {int(row['num_sensors'])} sensores)")

print("\n" + "="*70)
print("2. ESTACIONES QUE ESTÁN SUBIDAS PERO LES FALTAN DATOS (Anomalía de tamaño)")
print("="*70)
print(f"Mediana del ratio tamaño/volumen: {median_ratio:.4f} MiB por (sensor * año)")
print(f"Umbral de alerta (50% de la mediana): {threshold:.4f} MiB por (sensor * año)\n")

if df_undercompleted.empty:
    print("Todas las estaciones subidas parecen tener la cantidad de datos esperada.")
else:
    for _, row in df_undercompleted.sort_values(by="ratio").iterrows():
        print(f"  [{int(row['indice'])}] ID {int(row['id_estacion'])}: {row['nombre']}")
        print(f"     -> Tamaño actual: {row['file_size_mib']:.2f} MiB")
        print(f"     -> Instalación: {int(row['year_inst'])} ({int(row['years_active'])} años activa) | Sensores: {int(row['num_sensors'])}")
        print(f"     -> Ratio de completitud: {row['ratio']:.4f} MiB/vol vs Mediana {median_ratio:.4f} (Posible pérdida de registros)")
        print("-" * 50)
