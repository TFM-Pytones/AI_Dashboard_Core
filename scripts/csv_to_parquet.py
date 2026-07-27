import pandas as pd

print("Leyendo los archivos CSV...")
# Leemos los datos extraídos
df_temas = pd.read_csv("losviajeros_temas.csv")
df_mensajes = pd.read_csv("losviajeros_mensajes.csv")

print("Convirtiendo a formato Parquet (compresión Snappy)...")
# Exportamos con el estándar definido para la Capa Bronce
df_temas.to_parquet("losviajeros_temas.parquet", engine="pyarrow", compression="snappy")
df_mensajes.to_parquet("losviajeros_mensajes.parquet", engine="pyarrow", compression="snappy")

print("¡Listo! Archivos .parquet generados correctamente.")