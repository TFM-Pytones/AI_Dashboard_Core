import os
import json
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, ".."))

csv_path = os.path.join(project_dir, "data", "estaciones-meteorologicas.csv")
progress_path = os.path.join(project_dir, "ingestion", "agrocabildo", "backfill_progress.json")

# Load stations metadata
if os.path.exists(csv_path):
    df_stations = pd.read_csv(csv_path)
    stations_map = dict(zip(df_stations["estacion_id"], df_stations["estacion_nombre"]))
else:
    df_stations = pd.DataFrame()
    stations_map = {}

# Load progress
if os.path.exists(progress_path):
    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)
else:
    progress = {"completed_keys": []}

completed_keys = progress.get("completed_keys", [])

# Parse keys
progress_by_station = {}
for key in completed_keys:
    parts = key.split("_")
    if len(parts) == 3:
        st_id, sensor_id, year = parts
        st_id = int(st_id)
        if st_id not in progress_by_station:
            progress_by_station[st_id] = []
        progress_by_station[st_id].append((sensor_id, year))

print("=" * 70)
print("ANALISIS DEL ESTADO DEL BACKFILL HISTORICO (AGROCABILDO)")
print("=" * 70)
print(f"Total de claves completadas en backfill_progress.json: {len(completed_keys)}\n")

print(f"{'ID':<6} | {'Nombre Estacion':<20} | {'Claves':<8} | {'Sensores':<20} | {'Estado'}")
print("-" * 70)

target_ids = df_stations["estacion_id"].tolist() if not df_stations.empty else sorted(progress_by_station.keys())

for st_id in target_ids:
    name = stations_map.get(st_id, f"Desconocida ({st_id})")
    data = progress_by_station.get(st_id, [])
    
    if not data:
        print(f"{st_id:<6} | {name:<20} | {0:<8} | {'-':<20} | PENDIENTE")
        continue
        
    # Agrupar por sensor y contar años por sensor
    sensors = {}
    for s_id, y in data:
        if s_id not in sensors:
            sensors[s_id] = 0
        sensors[s_id] += 1
        
    sensors_str = ", ".join([f"{s}({cnt})" for s, cnt in sorted(sensors.items())])
    
    # Decidir estado
    # Asumiendo 8 años (2019-2026) por sensor, si todos los sensores tienen 8 años, está completo
    is_complete = all(cnt == 8 for cnt in sensors.values()) and len(sensors) >= 4
    status = "COMPLETO" if is_complete else "EN PROGRESO"
    
    print(f"{st_id:<6} | {name:<20} | {len(data):<8} | {sensors_str:<20} | {status}")

print("=" * 70)
