import pandas as pd
import streamlit as st

from app.data import filter_by_municipio

# (column, label, format, description) -- the default table view. h3_index,
# coordinates, and the dozens of satellite/climate sub-columns are hidden
# here and only shown when the user opts into the technical view (see
# show_technical). description feeds both the column tooltip (help=) and the
# searchable glossary panel below the table.
CURATED_COLUMNS = [
    ("municipio", "Municipio", None, "Municipio de Tenerife al que pertenece el hexágono."),
    (
        "tipo_zona",
        "Clúster Territorial",
        None,
        "Clasificación territorial en 4 tipologías: Saturado/Overtourism, Transición, Rural Infrautilizada, Urbano Sin Turismo.",
    ),
    (
        "arquetipo_principal",
        "Arquetipo TUI",
        None,
        "Arquetipo de producto turístico dominante según el modelo multicriterio.",
    ),
    (
        "eje_1_saturacion",
        "Eje 1 (Saturación)",
        "%.2f",
        "Gradiente continuo de saturación turística (HDBSCAN), de 0 (sin presión) a 1 (saturación máxima).",
    ),
    (
        "eje_2_rural_infrautilizado",
        "Eje 2 (Rural Infra.)",
        "%.2f",
        "Score compuesto de vocación rural y potencial turístico desaprovechado [0-1].",
    ),
    (
        "ptna_score",
        "Score PTNA",
        "%.1f",
        "Puntuación del modelo de Potencial Turístico No Aprovechado.",
    ),
    (
        "esg_h3_score",
        "Score ESG",
        "%.1f",
        "Puntuación de sostenibilidad territorial insular (escala 0-100).",
    ),
    (
        "restriction_category",
        "Restricción legal",
        None,
        "Si el hexágono solapa con un Espacio Natural Protegido (ENP), una zona turística "
        "oficial, o ninguna de las dos (\"Sin restricción\").",
    ),
    ("area_km2", "Área (km²)", "%.2f", "Superficie del hexágono H3, en kilómetros cuadrados."),
    (
        "n_establecimientos_registro",
        "Alojamientos registrados",
        "%d",
        "Número de alojamientos turísticos con registro oficial en el hexágono.",
    ),
    (
        "n_plazas_registro",
        "Plazas registradas",
        "%d",
        "Capacidad total (número de camas/plazas) de esos alojamientos registrados.",
    ),
    ("n_hoteles", "Hoteles", "%d", "Número de hoteles (establecimientos) en el hexágono."),
    (
        "n_vv",
        "Viviendas vacacionales",
        "%d",
        "Número de viviendas vacacionales registradas en el hexágono.",
    ),
    (
        "rating_booking_medio",
        "Rating Booking",
        "%.1f",
        "Valoración media en Booking de los alojamientos del hexágono, escala 0-10.",
    ),
    (
        "rating_tripadvisor_medio",
        "Rating TripAdvisor",
        "%.1f",
        "Valoración media en TripAdvisor de los alojamientos del hexágono, escala 0-5.",
    ),
    (
        "sentimiento_medio",
        "Sentimiento medio",
        "%.2f",
        "Puntuación media de sentimiento de las reseñas del hexágono, escala 1 (muy negativo) a 5 (muy positivo).",
    ),
    (
        "ndvi_medio",
        "NDVI medio",
        "%.2f",
        "Índice de vegetación medio por satélite, de 0 (sin vegetación) a 1 (vegetación densa).",
    ),
    (
        "temp_media_anual",
        "Temp. media anual (°C)",
        "%.1f",
        "Temperatura media anual del hexágono, en grados Celsius.",
    ),
    ("n_pois_total", "Puntos de interés", "%d", "Número de puntos de interés turístico en el hexágono."),
    (
        "queja_principal",
        "Aspecto más mencionado",
        None,
        "El aspecto (tema) que más aparece en las reseñas de ese hexágono.",
    ),
]

# Columnas con muchos huecos reales (la mayoria de hexagonos no tienen
# alojamiento con presencia en Booking/TripAdvisor, no todas las reseñas
# estan geolocalizadas al hexagono, etc.) -- st.dataframe muestra el texto
# literal "None" para estos huecos tanto en NumberColumn como en TextColumn,
# asi que se formatean como texto con "—" en vez de dejar que se rendericen
# en crudo.
SPARSE_NUMERIC_COLUMNS = {"rating_booking_medio", "rating_tripadvisor_medio", "sentimiento_medio"}
SPARSE_TEXT_COLUMNS = {"queja_principal"}


def _format_or_dash(value, fmt: str | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    if fmt is None:
        return value
    formatted = fmt % value
    return formatted.replace(".", ",")


def filter_table(gdf: pd.DataFrame, municipio: str | None, restriction: str | None) -> pd.DataFrame:
    result = filter_by_municipio(gdf, municipio)
    if restriction and restriction != "Todas":
        result = result[result["restriction_category"] == restriction]
    return result


def columns_entirely_missing(gdf: pd.DataFrame, columns: list[str]) -> set[str]:
    return {column for column in columns if column in gdf.columns and gdf[column].isna().all()}


def prepare_table_view(gdf: pd.DataFrame, show_technical: bool = False) -> pd.DataFrame:
    dropped = gdf.drop(columns=["geometry"], errors="ignore")
    if show_technical:
        return dropped
    columns = [column for column, _, _, _ in CURATED_COLUMNS if column in dropped.columns]
    empty_columns = columns_entirely_missing(dropped, columns)
    columns = [column for column in columns if column not in empty_columns]
    result = dropped[columns].copy()
    for column, _, fmt, _ in CURATED_COLUMNS:
        if column in SPARSE_NUMERIC_COLUMNS | SPARSE_TEXT_COLUMNS and column in result.columns:
            result[column] = result[column].map(lambda v, fmt=fmt: _format_or_dash(v, fmt))
    return result


def build_table_column_config(show_technical: bool = False, gdf: pd.DataFrame | None = None) -> dict:
    if show_technical:
        return {}
    empty_columns = columns_entirely_missing(gdf, [c for c, _, _, _ in CURATED_COLUMNS]) if gdf is not None else set()
    config = {}
    for column, label, fmt, description in CURATED_COLUMNS:
        if column in empty_columns:
            continue
        if column in SPARSE_NUMERIC_COLUMNS:
            config[column] = st.column_config.TextColumn(label, help=description)
        elif fmt:
            config[column] = st.column_config.NumberColumn(label, format=fmt, help=description)
        else:
            config[column] = st.column_config.TextColumn(label, help=description)
    return config


# Descripciones de las columnas tecnicas (solo visibles con "Mostrar columnas
# tecnicas") que no forman parte de CURATED_COLUMNS. Se buscan por su nombre
# de columna en crudo, igual que aparecen en esa vista de la tabla.
_TRIMESTRES_DESC = {"q1": "1er trimestre", "q2": "2º trimestre", "q3": "3er trimestre", "q4": "4º trimestre"}
_ANIOS = ["2022", "2023", "2024", "2025", "2026"]

TECHNICAL_COLUMNS_GLOSSARY: dict[str, str] = {
    "h3_index": "Identificador único del hexágono H3.",
    "cod_municipio": "Código INE del municipio al que pertenece el hexágono.",
    "centroide_lon": "Longitud geográfica del centro del hexágono.",
    "centroide_lat": "Latitud geográfica del centro del hexágono.",
    "n_extrahoteleros": "Número de alojamientos extrahoteleros (ni hotel ni vivienda vacacional) en el hexágono.",
    "n_establecimientos_booking": "Número de alojamientos con presencia en Booking en el hexágono.",
    "n_reviews_booking": "Número de reseñas en Booking de los alojamientos del hexágono.",
    "n_establecimientos_tripadvisor": "Número de alojamientos con presencia en TripAdvisor en el hexágono.",
    "n_reviews_tripadvisor": "Número de reseñas en TripAdvisor de los alojamientos del hexágono.",
    "n_reviews_total": "Número total de reseñas (Booking + TripAdvisor) de los alojamientos del hexágono.",
    "rating_global_100": "Valoración global combinada, normalizada a una escala de 0 a 100.",
    "n_restaurantes": "Número de restaurantes y bares en el hexágono.",
    "n_cultura": "Número de puntos de interés culturales en el hexágono.",
    "n_naturaleza": "Número de puntos de interés de naturaleza y deporte en el hexágono.",
    "n_pois_institucionales": "Número de puntos de interés institucionales (ayuntamientos, oficinas...) en el hexágono.",
    "n_paradas_bus": "Número de paradas de autobús en el hexágono.",
    "altitud_media_m": "Altitud media del hexágono, en metros.",
    "desnivel_m": "Desnivel del hexágono (diferencia entre altitud máxima y mínima), en metros.",
    "slope_mean": "Pendiente media del terreno en el hexágono.",
    "aspect_mean": "Orientación media de la pendiente del terreno, en grados respecto al norte.",
    "hillshade_mean": "Sombreado medio del relieve (iluminación simulada del terreno).",
    "ndvi_medio": "Índice de vegetación medio por satélite, de 0 (sin vegetación) a 1 (vegetación densa).",
    "viirs_medio": "Nivel medio de luminosidad nocturna por satélite (VIIRS).",
    "cambio_luz_nocturna_pct": "% de cambio en la luminosidad nocturna respecto al periodo anterior.",
    "ndbi_medio": "Índice de densidad urbana medio por satélite (NDBI).",
    "dias_ola_calor_anual": "Número de días con ola de calor en el año.",
    "amplitud_termica_media": "Diferencia media entre la temperatura máxima y mínima diaria.",
    "horas_sol_diarias_media": "Media de horas de sol diarias.",
    "lluvia_mm_anual": "Precipitación acumulada media anual, en milímetros.",
    "vel_viento_media_anual": "Velocidad media anual del viento, en metros por segundo.",
    "humedad_media_anual": "Humedad relativa media anual, en porcentaje.",
    "dist_costa_km": "Distancia en línea recta a la costa, en km.",
    "pct_area_enp": "Fracción (0 a 1) del área del hexágono dentro de un Espacio Natural Protegido.",
    "nombre_enp": "Nombre del Espacio Natural Protegido, si el hexágono solapa con uno.",
    "pct_area_zona_turistica": "Fracción (0 a 1) del área del hexágono dentro de una zona turística oficial.",
    "nombre_zona_turistica": "Nombre de la zona turística oficial, si el hexágono solapa con una.",
    "n_resenas": "Número total de reseñas analizadas por NLP en el hexágono.",
    "n_resenas_booking": "Número de reseñas de Booking analizadas por NLP en el hexágono.",
    "n_resenas_tripadvisor": "Número de reseñas de TripAdvisor analizadas por NLP en el hexágono.",
    "densidad_metric": "Métrica de densidad usada para colorear el mapa, según la capa seleccionada.",
    "tiempo_tfs_min": "Tiempo estimado en coche hasta el aeropuerto de Tenerife Sur, en minutos.",
    "tiempo_tfn_min": "Tiempo estimado en coche hasta el aeropuerto de Tenerife Norte, en minutos.",
    "tiempo_capital_min": "Tiempo estimado en coche hasta Santa Cruz de Tenerife, en minutos.",
    "tiempo_extremo_sur_min": "Tiempo estimado en coche hasta el extremo sur de la isla, en minutos.",
    "tiempo_extremo_norte_min": "Tiempo estimado en coche hasta el extremo norte de la isla, en minutos.",
    "tiempo_teide_min": "Tiempo estimado en coche hasta el Teide, en minutos.",
    "tiempo_la_laguna_min": "Tiempo estimado en coche hasta La Laguna, en minutos.",
    "tiempo_candelaria_min": "Tiempo estimado en coche hasta Candelaria, en minutos.",
    "tiempo_los_gigantes_min": "Tiempo estimado en coche hasta Los Gigantes, en minutos.",
    "tiempo_el_medano_min": "Tiempo estimado en coche hasta El Médano, en minutos.",
    "tiempo_garachico_min": "Tiempo estimado en coche hasta Garachico, en minutos.",
    "tiempo_anaga_min": "Tiempo estimado en coche hasta el Parque Rural de Anaga, en minutos.",
    "tiempo_masca_min": "Tiempo estimado en coche hasta Masca, en minutos.",
    "tiempo_vilaflor_min": "Tiempo estimado en coche hasta Vilaflor, en minutos.",
    "tiempo_la_orotava_min": "Tiempo estimado en coche hasta La Orotava, en minutos.",
    "tiempo_guimar_min": "Tiempo estimado en coche hasta Güímar, en minutos.",
    "tiempo_buenavista_min": "Tiempo estimado en coche hasta Buenavista del Norte, en minutos.",
    "tiempo_arico_min": "Tiempo estimado en coche hasta Arico, en minutos.",
    "tiempo_aeropuerto_min": "Tiempo estimado en coche hasta el aeropuerto más cercano, en minutos.",
    "aeropuerto_mas_cercano": "Aeropuerto más cercano al hexágono (TFS o TFN).",
    "n_paradas_bus_200m": "Número de paradas de autobús a menos de 200 metros.",
    "n_paradas_bus_500m": "Número de paradas de autobús a menos de 500 metros.",
    "n_paradas_bus_1000m": "Número de paradas de autobús a menos de 1000 metros.",
    "dist_parada_cercana_m": "Distancia a la parada de autobús más cercana, en metros.",
    "dist_hospital_km": "Distancia al hospital más cercano, en km.",
}

for _anio in _ANIOS:
    TECHNICAL_COLUMNS_GLOSSARY[f"ndvi_{_anio}"] = f"Índice de vegetación (NDVI) medio del hexágono en {_anio}."
    TECHNICAL_COLUMNS_GLOSSARY[f"viirs_{_anio}"] = f"Nivel de luminosidad nocturna (VIIRS) del hexágono en {_anio}."
    TECHNICAL_COLUMNS_GLOSSARY[f"ndbi_{_anio}"] = f"Índice de densidad urbana (NDBI) del hexágono en {_anio}."

for _q, _texto in _TRIMESTRES_DESC.items():
    TECHNICAL_COLUMNS_GLOSSARY[f"ndvi_{_q}"] = f"Índice de vegetación (NDVI) medio del hexágono en el {_texto}."
    TECHNICAL_COLUMNS_GLOSSARY[f"viirs_{_q}"] = f"Nivel de luminosidad nocturna (VIIRS) del hexágono en el {_texto}."
    TECHNICAL_COLUMNS_GLOSSARY[f"horas_sol_{_q}"] = f"Media de horas de sol diarias en el {_texto}."
    TECHNICAL_COLUMNS_GLOSSARY[f"temp_media_{_q}"] = f"Temperatura media en el {_texto}, en grados Celsius."
    TECHNICAL_COLUMNS_GLOSSARY[f"lluvia_mm_{_q}"] = f"Precipitación acumulada media en el {_texto}, en milímetros."
    TECHNICAL_COLUMNS_GLOSSARY[f"vel_viento_media_{_q}"] = f"Velocidad media del viento en el {_texto}, en metros por segundo."
    TECHNICAL_COLUMNS_GLOSSARY[f"humedad_media_{_q}"] = f"Humedad relativa media en el {_texto}, en porcentaje."


def build_column_glossary() -> dict[str, str]:
    glossary = {label: description for _, label, _, description in CURATED_COLUMNS}
    glossary.update(TECHNICAL_COLUMNS_GLOSSARY)
    return glossary
