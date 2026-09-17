"""
analytics/clustering/run_hdbscan_clustering.py
----------------------------------------------
Pipeline oficial de Clustering Territorial HDBSCAN (V1 Definitivo).
Resuelve la tipificación espacial de Tenerife sobre los 2.579 hexágonos H3.

Corrige las limitaciones del modelo histórico (que clasificaba erróneamente
el Teide como "Urbano Sin Turismo") incorporando la dimensión de protección
ambiental (pct_area_enp) y log-transformaciones para variables con sesgo extremo.

Tipologías producidas (6 clases, 100% cobertura insular):
1. Espacio Natural / Teide y Cumbre
2. Espacios Rurales Protegidos (Anaga/Teno)
3. Transición Costera y Medianías
4. Rural Agrícola / Medianías Norte
5. Saturado / Overtourism
6. Urbano Residencial

Salida: Actualiza la tabla `gold.h3_clusters` en PostgreSQL preservando
la compatibilidad del esquema (h3_index, tipo_zona).
"""

import os
import sys
import argparse
import logging
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import HDBSCAN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

FEATURE_COLS = [
    "n_plazas_log",
    "viirs_log",
    "ndvi_medio",
    "ndbi_medio",
    "altitud_media_m",
    "slope_mean",
    "dist_costa_km",
    "pct_area_enp",
]

CLUSTER_MAPPING = {
    "Cluster_1": "Espacio Natural / Teide y Cumbre",
    "Cluster_0": "Espacios Rurales Protegidos (Anaga/Teno)",
    "Cluster_3": "Rural Agrícola / Medianías Norte",
    "Cluster_2": "Transición Costera y Medianías",
    "Saturado/Overtourism": "Saturado / Overtourism",
    "Urbano Residencial": "Urbano Residencial",
}


def get_pg_engine():
    load_dotenv()
    pg_user = os.getenv("AZURE_DB_USER")
    pg_pass = os.getenv("AZURE_DB_PASSWORD")
    pg_host = os.getenv("AZURE_DB_HOST")
    pg_port = os.getenv("AZURE_DB_PORT", "5432")
    pg_db = os.getenv("AZURE_DB_NAME")

    if not all([pg_user, pg_pass, pg_host, pg_db]):
        raise ValueError("Faltan variables de entorno para PostgreSQL (AZURE_DB_USER, AZURE_DB_PASSWORD, etc.)")

    connection_string = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    return create_engine(connection_string, connect_args={"sslmode": "require"})


def load_data(engine) -> pd.DataFrame:
    query = """
        SELECT
            h3_index,
            municipio,
            n_plazas_registro,
            altitud_media_m,
            slope_mean,
            dist_costa_km,
            pct_area_enp,
            ndvi_medio,
            ndbi_medio,
            viirs_medio
        FROM gold.gold_h3_master
    """
    logging.info("Cargando features desde gold.gold_h3_master...")
    df = pd.read_sql(query, engine)
    logging.info(f"Cargados {len(df)} hexágonos H3.")
    return df


def execute_clustering(df_input: pd.DataFrame) -> pd.DataFrame:
    df = df_input.copy()
    
    # 1. Transformaciones logarítmicas
    df["n_plazas_log"] = np.log1p(df["n_plazas_registro"].fillna(0).clip(lower=0))
    df["viirs_log"] = np.log1p(df["viirs_medio"].fillna(0).clip(lower=0))

    # 2. Imputación con mediana y escalado
    X_raw = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median())
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # 3. Reducción PCA a 3 componentes (captura >81% varianza)
    pca = PCA(n_components=3, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    var_exp = pca.explained_variance_ratio_.sum()
    logging.info(f"PCA completado (3 componentes). Varianza explicada acumulada: {var_exp:.2%}")

    # 4. HDBSCAN
    hdb = HDBSCAN(
        min_cluster_size=30,
        min_samples=10,
        cluster_selection_method="eom",
        copy=True
    )
    labels = hdb.fit_predict(X_pca)
    n_noise = (labels == -1).sum()
    logging.info(f"HDBSCAN completado. Puntos núcleo asignados: {len(labels)-n_noise}, Ruido inicial: {n_noise} ({n_noise/len(labels):.1%})")

    # 5. Centroides de clústeres no-ruido
    unique_c = [c for c in np.unique(labels) if c != -1]
    centroids = {c: X_pca[labels == c].mean(axis=0) for c in unique_c}

    # 6. Reasignación de ruido con reglas experto territoriales
    final_labels = []
    for i in range(len(df)):
        lab = labels[i]
        if lab == -1:
            plazas = df.loc[i, "n_plazas_registro"]
            viirs = df.loc[i, "viirs_medio"]
            enp = df.loc[i, "pct_area_enp"]
            if plazas >= 500:
                final_labels.append("Saturado/Overtourism")
            elif viirs >= 20 and enp < 0.2:
                final_labels.append("Urbano Residencial")
            else:
                pt = X_pca[i]
                closest = min(centroids.keys(), key=lambda c: np.linalg.norm(pt - centroids[c]))
                final_labels.append(f"Cluster_{closest}")
        else:
            final_labels.append(f"Cluster_{lab}")

    # 7. Asignación de tipologías finales
    df["tipo_zona"] = [CLUSTER_MAPPING[x] for x in final_labels]
    df["hdbscan_raw_label"] = labels
    df["pca_1"] = X_pca[:, 0]
    df["pca_2"] = X_pca[:, 1]
    df["pca_3"] = X_pca[:, 2]

    return df


def save_to_database(df: pd.DataFrame, engine, dry_run: bool = False):
    counts = df["tipo_zona"].value_counts()
    logging.info("Distribución final de las 6 tipologías:")
    for tipo, cnt in counts.items():
        logging.info(f"  - {tipo}: {cnt} ({cnt/len(df):.1%})")

    if dry_run:
        logging.info("MODO DRY-RUN: No se escriben cambios en la base de datos.")
        return

    table_name = "h3_clusters"
    backup_table = "h3_clusters_backup_old"

    with engine.begin() as con:
        # Respaldar tabla anterior si existe y no se ha respaldado aún
        check_backup = con.execute(text(
            f"SELECT 1 FROM information_schema.tables WHERE table_schema='gold' AND table_name='{backup_table}'"
        )).scalar()
        if not check_backup:
            logging.info(f"Creando copia de respaldo de seguridad: gold.{backup_table}...")
            con.execute(text(f"CREATE TABLE gold.{backup_table} AS SELECT * FROM gold.{table_name}"))
            logging.info("Respaldo creado correctamente.")

    # Guardar la nueva tabla manteniendo compatibilidad exacta
    out_df = df[["h3_index", "tipo_zona", "pca_1", "pca_2", "pca_3", "hdbscan_raw_label"]].copy()
    logging.info(f"Actualizando tabla gold.{table_name} con {len(out_df)} hexágonos...")
    out_df.to_sql(table_name, con=engine, schema="gold", if_exists="replace", index=False)

    with engine.begin() as con:
        logging.info(f"Creando índice primario sobre {table_name}(h3_index)...")
        con.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_h3 ON gold.{table_name} (h3_index);"))

    logging.info("¡Migración de gold.h3_clusters completada con éxito!")


def main():
    parser = argparse.ArgumentParser(description="Pipeline Oficial HDBSCAN - Tipificación Territorial")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta el clustering sin escribir en PostgreSQL")
    args = parser.parse_args()

    engine = get_pg_engine()
    df_raw = load_data(engine)
    df_clustered = execute_clustering(df_raw)
    save_to_database(df_clustered, engine, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
