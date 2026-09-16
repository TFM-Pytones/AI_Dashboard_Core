"""Agente Text-to-SQL del chatbot (Bloque 8, Subtarea 8.4): genera SQL de
solo lectura contra un esquema curado de tablas gold.* a nivel
municipio/isla, lo valida, lo ejecuta, y redacta la respuesta.

Sin LangChain a propósito -- ver docs/superpowers/specs/2026-09-15-asistente-ia-chatbot-design.md,
decisiones 2 y 3.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from analytics.llm.llm_client import LLMClient

# Esquema curado a mano (igual que KPI_COLUMNS/METRICS/MUNICIPIO_METRICS en
# app/): solo tablas a nivel municipio/isla ya usadas por el dashboard.
# gold_h3_master (nivel hexágono, ~80 columnas técnicas de satélite/clima) se
# excluye a propósito -- un esquema más pequeño produce SQL más preciso, y
# esas preguntas agregadas no son a nivel hexágono.
ESQUEMA_GOLD: dict[str, list[tuple[str, str]]] = {
    "gold.gold_municipio_master": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("area_km2", "superficie en km2"),
        ("poblacion_actual", "población total actual"),
        ("paro_actual", "personas en paro registrado, dato actual"),
        ("empleo_total_actual", "personas empleadas (asalariados + autónomos), dato actual"),
        ("empleo_autonomos_actual", "trabajadores autónomos, dato actual"),
        ("empleo_hosteleria_actual", "empleados en hostelería, dato actual"),
        ("plazas_vv_actual", "plazas de vivienda vacacional, dato actual"),
        ("tasa_ocupacion_vv_actual", "% de ocupación de vivienda vacacional, dato actual"),
        ("ingresos_vv_actual", "ingresos por vivienda vacacional en euros, dato actual"),
        ("n_establecimientos_registro", "número de alojamientos turísticos con registro oficial"),
        (
            "n_plazas_registro",
            "plazas turísticas registradas (capacidad total en camas/plazas, todos los tipos "
            "de alojamiento). Esta es la columna correcta para 'plazas' o 'capacidad'",
        ),
        (
            "n_hoteles",
            "número de hoteles (establecimientos, NO camas/plazas). Para 'plazas hoteleras' o "
            "'capacidad' usa n_plazas_registro, no esta columna",
        ),
        ("n_vv", "número de viviendas vacacionales registradas"),
        ("densidad_plazas_km2", "plazas turísticas por km2"),
        ("plazas_por_1000_hab", "plazas turísticas por cada 1000 habitantes"),
        ("crec_poblacion_pct", "% de crecimiento de población desde 2022"),
        ("var_paro_pct", "% de variación del paro desde 2022"),
        ("crec_empleo_total_pct", "% de crecimiento del empleo total desde 2022"),
        ("crec_plazas_vv_pct", "% de crecimiento de plazas de vivienda vacacional desde 2022"),
        ("crec_ingresos_vv_pct", "% de crecimiento de ingresos de vivienda vacacional desde 2022"),
        ("n_establecimientos_booking", "número de alojamientos con presencia en Booking"),
        ("rating_booking_medio", "valoración media en Booking, escala 0-10"),
        ("n_reviews_booking", "número de reseñas en Booking"),
        ("n_establecimientos_tripadvisor", "número de alojamientos con presencia en TripAdvisor"),
        ("rating_tripadvisor_medio", "valoración media en TripAdvisor, escala 0-5"),
        ("n_pois_total", "número de puntos de interés turístico"),
        ("n_paradas_bus", "número de paradas de autobús"),
    ],
    "gold.gold_municipio_anual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("anio", "año de la serie"),
        ("poblacion", "población total ese año"),
        ("paro_medio", "media anual de personas en paro registrado"),
        ("var_paro_yoy_pct", "% de variación del paro respecto al año anterior"),
        ("empleo_total_medio", "media anual de personas empleadas"),
        ("crec_empleo_total_yoy_pct", "% de crecimiento del empleo respecto al año anterior"),
        ("empleo_autonomos_medio", "media anual de trabajadores autónomos"),
        ("crec_empleo_autonomos_yoy_pct", "% de crecimiento de autónomos respecto al año anterior"),
        ("plazas_vv_media", "media anual de plazas de vivienda vacacional"),
        ("crec_plazas_vv_yoy_pct", "% de crecimiento de plazas VV respecto al año anterior"),
        ("ingresos_vv_media_mensual", "ingresos medios mensuales de vivienda vacacional en euros"),
        ("crec_ingresos_mensual_yoy_pct", "% de crecimiento de ingresos VV respecto al año anterior"),
        ("tasa_ocupacion_vv_media", "% medio de ocupación de vivienda vacacional ese año"),
        ("estancia_media_vv", "duración media de estancia en vivienda vacacional, en días"),
    ],
    "gold.gold_municipio_mensual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("paro_registrado", "personas en paro registrado ese mes"),
        ("paro_yoy_pct", "% de variación del paro respecto al mismo mes del año anterior"),
        ("plazas_vv", "plazas de vivienda vacacional ese mes"),
        ("tasa_ocupacion_vv", "% de ocupación de vivienda vacacional ese mes"),
        ("estancia_media_vv", "duración media de estancia en vivienda vacacional, en días"),
        ("ingresos_vv", "ingresos de vivienda vacacional ese mes, en euros"),
        ("alojamientos_abiertos_vv", "número de alojamientos de vivienda vacacional abiertos ese mes"),
        ("plazas_vv_yoy_pct", "% de variación de plazas VV respecto al mismo mes del año anterior"),
        ("ingresos_vv_yoy_pct", "% de variación de ingresos VV respecto al mismo mes del año anterior"),
    ],
    "gold.gold_municipio_empleo": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("periodo", "periodo trimestral en formato YYYY-QN"),
        ("periodo_texto", "periodo trimestral en texto legible"),
        ("anio", "año"),
        ("trimestre", "trimestre (1-4)"),
        ("empleo_total", "total de personas afiliadas a la Seguridad Social"),
        ("empleo_asalariados", "personas afiliadas como asalariados"),
        ("empleo_autonomos", "personas afiliadas como autónomos"),
        ("pct_autonomos", "% de afiliados que son autónomos"),
        ("pct_asalariados", "% de afiliados que son asalariados"),
        ("crec_empleo_total_yoy_pct", "% de crecimiento del empleo total respecto al mismo trimestre del año anterior"),
        ("crec_empleo_autonomos_yoy_pct", "% de crecimiento de autónomos respecto al mismo trimestre del año anterior"),
    ],
    "gold.gold_turismo_hotelero_anual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("polo_turistico", "polo turístico al que pertenece el municipio (ej. Polo Sur, Polo Norte)"),
        ("anio", "año"),
        ("viajeros_entrados_total", "viajeros alojados en establecimientos hoteleros ese año"),
        ("crec_viajeros_yoy_pct", "% de crecimiento de viajeros respecto al año anterior"),
        ("pernoctaciones_total", "noches pernoctadas en establecimientos hoteleros ese año"),
        ("crec_pernoctaciones_yoy_pct", "% de crecimiento de pernoctaciones respecto al año anterior"),
        ("ocupacion_media_plazas", "% medio de ocupación de plazas hoteleras ese año"),
        ("estancia_media_hotel_dias", "duración media de estancia en hotel, en días"),
    ],
    "gold.gold_turismo_hotelero_mensual": [
        ("cod_municipio", "código INE del municipio"),
        ("municipio", "nombre del municipio"),
        ("polo_turistico", "polo turístico al que pertenece el municipio"),
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("viajeros_entrados", "viajeros alojados en establecimientos hoteleros ese mes"),
        ("pernoctaciones", "noches pernoctadas en establecimientos hoteleros ese mes"),
        ("tasa_ocupacion_plazas", "% de ocupación de plazas hoteleras ese mes"),
        ("estancia_media_hotel_dias", "duración media de estancia en hotel, en días"),
        ("crec_viajeros_yoy_pct", "% de variación de viajeros respecto al mismo mes del año anterior"),
        ("crec_pernoctaciones_yoy_pct", "% de variación de pernoctaciones respecto al mismo mes del año anterior"),
    ],
    "gold.gold_aena_pasajeros": [
        ("periodo", "periodo en formato YYYY-MM"),
        ("anio", "año"),
        ("mes", "mes (1-12)"),
        ("trimestre", "trimestre (Q1-Q4)"),
        ("temporada", "Invierno (Temporada Alta) o Verano (Temporada Media/Baja)"),
        ("aeropuerto_codigo", "TFS (Tenerife Sur) o TFN (Tenerife Norte)"),
        ("aeropuerto_nombre", "nombre completo del aeropuerto"),
        ("tipo_trafico_principal", "Internacional predominante (TFS) o Nacional e Interinsular (TFN)"),
        ("pasajeros", "pasajeros totales ese mes"),
        ("operaciones", "operaciones (despegues + aterrizajes) ese mes"),
        ("pasajeros_por_operacion", "pasajeros medios por operación ese mes"),
    ],
    # Nivel hexágono H3 (2.579 celdas), no municipio -- selección curada de
    # ~24 columnas de las ~80 originales de gold_h3_master. Cubre
    # restricciones legales, distancia a costa, relieve y satélite; se
    # excluyen a propósito los desgloses por año/trimestre de NDVI/NDBI/VIIRS
    # y clima (>40 columnas técnicas) que no aportan a preguntas en lenguaje
    # natural y solo añadirían ruido al esquema.
    "gold.gold_h3_master": [
        ("h3_index", "identificador del hexágono H3"),
        ("cod_municipio", "código INE del municipio al que pertenece el hexágono"),
        ("municipio", "nombre del municipio al que pertenece el hexágono"),
        ("area_km2", "superficie del hexágono en km2"),
        ("n_establecimientos_registro", "alojamientos turísticos con registro oficial en el hexágono"),
        (
            "n_plazas_registro",
            "plazas turísticas registradas en el hexágono (capacidad total en camas/plazas). "
            "Esta es la columna correcta para 'plazas' o 'capacidad'",
        ),
        (
            "n_hoteles",
            "número de hoteles (establecimientos, NO camas/plazas) en el hexágono. Para "
            "'plazas hoteleras' o 'capacidad' usa n_plazas_registro, no esta columna",
        ),
        ("n_vv", "número de viviendas vacacionales en el hexágono"),
        ("rating_booking_medio", "valoración media en Booking en el hexágono, escala 0-10"),
        ("rating_tripadvisor_medio", "valoración media en TripAdvisor en el hexágono, escala 0-5"),
        ("n_pois_total", "puntos de interés turístico en el hexágono"),
        ("n_restaurantes", "restaurantes/bares en el hexágono"),
        ("n_naturaleza", "puntos de interés de naturaleza/deporte en el hexágono"),
        ("n_paradas_bus", "paradas de autobús en el hexágono"),
        ("altitud_media_m", "altitud media del hexágono en metros"),
        ("slope_mean", "pendiente media del terreno en el hexágono"),
        ("ndvi_medio", "índice de vegetación medio por satélite, de 0 (sin vegetación) a 1 (vegetación densa)"),
        ("ndbi_medio", "índice de densidad urbana medio por satélite"),
        ("temp_media_anual", "temperatura media anual del hexágono en grados"),
        ("lluvia_mm_anual", "lluvia media anual del hexágono en mm"),
        ("dist_costa_km", "distancia en línea recta a la costa en km"),
        (
            "pct_area_enp",
            "fracción (0 a 1) del área del hexágono dentro de un Espacio Natural Protegido; "
            "0 significa que no hay solape",
        ),
        ("nombre_enp", "nombre del Espacio Natural Protegido, si pct_area_enp > 0"),
        (
            "pct_area_zona_turistica",
            "fracción (0 a 1) del área del hexágono dentro de una zona turística oficial; "
            "0 significa que no hay solape. Un hexágono 'sin restricción' tiene pct_area_enp = 0 "
            "Y pct_area_zona_turistica = 0 a la vez",
        ),
        ("nombre_zona_turistica", "nombre de la zona turística oficial, si pct_area_zona_turistica > 0"),
    ],
    # Conectada al dashboard el 2026-09-16 (antes devolvia vacio -- el
    # modelo dbt original nunca se materializo, ver app/data.py). Solo cubre
    # los hexagonos cuyas reseñas se pudieron geolocalizar (410 de 2.579).
    # No tiene columna de municipio: para agrupar por municipio hace falta
    # JOIN con gold.gold_h3_master por h3_index (union segura, 1 fila por
    # hexagono en ambas tablas, sin riesgo de duplicar filas).
    "gold.gold_h3_sentimiento": [
        ("h3_index", "identificador del hexágono H3 -- usa JOIN con gold_h3_master.h3_index para obtener el municipio"),
        (
            "sentimiento_medio",
            "puntuación media de sentimiento de las reseñas del hexágono, escala 1 (muy negativo) a 5 (muy positivo)",
        ),
        ("n_resenas_sentimiento", "número de reseñas analizadas para calcular sentimiento_medio en el hexágono"),
        ("n_resenas_booking", "de esas reseñas, cuántas son de Booking"),
        ("n_resenas_tripadvisor", "de esas reseñas, cuántas son de TripAdvisor"),
        ("queja_principal", "aspecto o queja más mencionado en las reseñas del hexágono"),
    ],
}

TABLAS_PERMITIDAS: set[str] = set(ESQUEMA_GOLD.keys())

PALABRAS_PROHIBIDAS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "CREATE"}

LIMIT_POR_DEFECTO = 200

# Granularidad de cada tabla, mostrada en el esquema que ve el LLM. Sin esto
# el LLM no sabe que gold_h3_master tiene muchas filas por municipio (a
# diferencia de las tablas *_anual/*_mensual, con una fila por municipio y
# periodo) y genera JOINs entre niveles que duplican cada hexágono una vez
# por cada fila coincidente de la otra tabla, sesgando cualquier AVG/SUM.
GRANULARIDAD_TABLA: dict[str, str] = {
    "gold.gold_municipio_master": "1 fila por municipio, 31 filas en total",
    "gold.gold_municipio_anual": "1 fila por municipio y año",
    "gold.gold_municipio_mensual": "1 fila por municipio y mes",
    "gold.gold_municipio_empleo": "1 fila por municipio y trimestre",
    "gold.gold_turismo_hotelero_anual": "1 fila por municipio y año",
    "gold.gold_turismo_hotelero_mensual": "1 fila por municipio y mes",
    "gold.gold_aena_pasajeros": "1 fila por mes, no tiene columna de municipio",
    "gold.gold_h3_master": (
        "1 fila por hexágono H3, ~2.579 filas en total -- MUCHAS filas por municipio, "
        "a diferencia de las demás tablas"
    ),
    "gold.gold_h3_sentimiento": (
        "1 fila por hexágono H3, pero SOLO 410 de los 2.579 hexágonos tienen reseñas "
        "geolocalizadas -- avisa de esta cobertura parcial en la respuesta"
    ),
}


def describir_esquema() -> str:
    bloques = []
    for tabla, columnas in ESQUEMA_GOLD.items():
        granularidad = GRANULARIDAD_TABLA.get(tabla)
        cabecera = f"Tabla {tabla} ({granularidad}):" if granularidad else f"Tabla {tabla}:"
        lineas_columnas = "\n".join(f"  - {col}: {desc}" for col, desc in columnas)
        bloques.append(f"{cabecera}\n{lineas_columnas}")
    return "\n\n".join(bloques)


def _tablas_referenciadas(sql: str) -> set[str]:
    return {t.lower() for t in re.findall(r"(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)", sql, re.IGNORECASE)}


def validar_sql(sql: str) -> tuple[bool, str | None]:
    sql_limpio = sql.strip().rstrip(";").strip()
    if ";" in sql_limpio:
        return False, "Solo se permite una única sentencia SQL."
    if not re.match(r"(?is)^SELECT\b", sql_limpio):
        return False, "Solo se permiten sentencias SELECT."
    palabras = set(re.findall(r"[A-Za-z]+", sql_limpio.upper()))
    prohibidas = palabras & PALABRAS_PROHIBIDAS
    if prohibidas:
        return False, f"Palabras clave no permitidas: {', '.join(sorted(prohibidas))}."
    tablas = _tablas_referenciadas(sql_limpio)
    no_permitidas = tablas - TABLAS_PERMITIDAS
    if no_permitidas:
        return False, f"Tablas no permitidas: {', '.join(sorted(no_permitidas))}."
    return True, None


def asegurar_limit(sql: str, limite: int = LIMIT_POR_DEFECTO) -> str:
    sql_limpio = sql.strip().rstrip(";").strip()
    if re.search(r"\bLIMIT\s+\d+", sql_limpio, re.IGNORECASE):
        return sql_limpio
    return f"{sql_limpio}\nLIMIT {limite}"


PROMPT_SQL = """Eres un generador de consultas SQL de solo lectura (PostgreSQL) sobre datos turísticos de Tenerife.

Devuelve UNICAMENTE la sentencia SQL, sin explicaciones, sin bloques de código markdown, sin punto y coma final.
Debe ser una única sentencia SELECT. Usa solo las tablas y columnas listadas abajo.

Cada tabla indica su granularidad (filas que tiene) entre paréntesis. Si necesitas
combinar una tabla a nivel de hexágono (gold_h3_master, muchas filas por municipio) con
una tabla a nivel de municipio-año/mes (que también puede tener varias filas por
municipio) SOLO para filtrar por una columna de la segunda, NO uses JOIN: cada fila de
la primera tabla se duplicaría una vez por cada fila coincidente de la segunda,
sesgando cualquier AVG/SUM/COUNT. En su lugar, filtra con una subconsulta:
  WHERE cod_municipio IN (SELECT DISTINCT cod_municipio FROM tabla WHERE condicion)
Usa JOIN solo cuando necesites columnas de ambas tablas a la vez en el SELECT.

Incluye siempre en el SELECT las columnas numéricas que uses para ordenar o filtrar
(no solo el nombre o id del municipio), para que el resultado sea verificable.

Si el resultado involucra municipios, incluye siempre la columna `municipio`
(nombre legible) en el SELECT -- `cod_municipio` no es legible para el usuario
final, es solo un código INE interno para hacer JOIN o filtrar.

ESQUEMA DISPONIBLE:
{esquema}

PREGUNTA: {pregunta}
{motivo_reintento}
SQL:"""

PROMPT_NARRACION = """Eres un analista de turismo. Redacta una respuesta breve (1-2 frases) en español a la pregunta del usuario, basándote UNICAMENTE en estas filas de resultado de una consulta SQL. No inventes datos que no estén en las filas.

PREGUNTA: {pregunta}

FILAS:
{filas}

RESPUESTA:"""


@dataclass
class RespuestaSQL:
    texto: str
    sql: str
    filas: list[dict] = field(default_factory=list)
    error: str | None = None


def _generar_sql(pregunta: str, llm: LLMClient, motivo_reintento: str = "") -> str:
    prompt = PROMPT_SQL.format(esquema=describir_esquema(), pregunta=pregunta, motivo_reintento=motivo_reintento)
    # max_tokens=1000, no 300: mismo motivo que en router.py -- el modelo
    # (openai/gpt-oss-120b) gasta presupuesto en tokens de razonamiento
    # ocultos antes del SQL en sí. Con un esquema grande (gold_h3_master +
    # las tablas de municipio) 300 no bastaba y devolvia "" siempre.
    # Confirmado empiricamente contra la API real de Groq.
    respuesta = llm.complete(prompt, temperature=0.0, max_tokens=1000)
    return respuesta.strip().strip("`").strip()


def responder_sql(pregunta: str, engine, llm: LLMClient | None = None) -> RespuestaSQL:
    cliente = llm or LLMClient()

    sql = _generar_sql(pregunta, cliente)
    es_valido, motivo = validar_sql(sql)
    if not es_valido:
        motivo_reintento = f"\nTu SQL anterior fue rechazada: {motivo}\nGenera una nueva sentencia SQL valida.\n"
        sql = _generar_sql(pregunta, cliente, motivo_reintento)
        es_valido, motivo = validar_sql(sql)
        if not es_valido:
            return RespuestaSQL(
                texto="No he podido generar una consulta SQL válida para esta pregunta.",
                sql=sql,
                error=motivo,
            )

    sql_final = asegurar_limit(sql)

    try:
        df = pd.read_sql(sql_final, engine)
    except Exception as exc:
        motivo_reintento = (
            f"\nTu SQL anterior fallo al ejecutarse con este error de Postgres: {exc}\n"
            "Genera una nueva sentencia SQL que lo corrija.\n"
        )
        sql = _generar_sql(pregunta, cliente, motivo_reintento)
        es_valido, motivo = validar_sql(sql)
        if not es_valido:
            return RespuestaSQL(
                texto="No he podido generar una consulta SQL válida para esta pregunta.",
                sql=sql,
                error=motivo,
            )
        sql_final = asegurar_limit(sql)
        try:
            df = pd.read_sql(sql_final, engine)
        except Exception as exc2:
            return RespuestaSQL(
                texto="La consulta generada no se pudo ejecutar correctamente contra la base de datos.",
                sql=sql_final,
                error=str(exc2),
            )

    if df.empty:
        return RespuestaSQL(texto="La consulta no devolvió resultados.", sql=sql_final, filas=[])

    filas = df.to_dict("records")
    prompt_narracion = PROMPT_NARRACION.format(pregunta=pregunta, filas=filas)
    # max_tokens=600, no 200: mismo motivo que en _generar_sql -- con muchas
    # filas (ej. los 31 municipios agrupados) el modelo necesita mas
    # presupuesto de razonamiento antes de poder redactar la respuesta.
    texto = cliente.complete(prompt_narracion, temperature=0.3, max_tokens=600)
    return RespuestaSQL(texto=texto.strip(), sql=sql_final, filas=filas)
