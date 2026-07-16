"""
TFM Tenerife - Estandarizacion de Coordenadas a EPSG:32628
Fase 1 - Configuracion Espacial (PostGIS)

Recorre TODAS las tablas de raw_data que tengan una columna de tipo
geometry, las reproyecta a EPSG:32628 y deja el resultado en
processed_data con su indice GIST correspondiente.

No hace falta decirle que tablas existen: las descubre preguntando
directamente a PostGIS (vista 'geometry_columns'), junto con el
nombre real de la columna de geometria y su SRID de origen. Por eso
funciona igual con 'geometry' (limites_municipales, zonas_turisticas,
gtfs_paradas, gtfs_rutas) que con 'ubicacion' (estaciones_clima).

Se puede ejecutar tantas veces como haga falta: si processed_data ya
tiene esa tabla, se sobrescribe con la version mas reciente de
raw_data (util si algun dato de origen cambia).

Requisitos:
    pip install geopandas sqlalchemy psycopg2-binary geoalchemy2

Uso (en Colab, con el secreto NEON_CONN ya configurado):
    import os
    from google.colab import userdata
    os.environ['NEON_CONN'] = userdata.get('NEON_CONN')
    !python estandarizar_coordenadas.py

Uso (en local):
    export NEON_CONN="postgresql://usuario:password@...neon.tech/db?sslmode=require"
    python estandarizar_coordenadas.py
"""

import os
import geopandas as gpd
from sqlalchemy import create_engine, text

SRID_DESTINO = 32628


def obtener_engine():
    conn_string = os.environ['NEON_CONN']
    return create_engine(conn_string, pool_pre_ping=True, pool_recycle=280)


def listar_tablas_espaciales(engine, esquema='raw_data'):
    """Devuelve (nombre_tabla, columna_geometria, srid) para cada tabla
    de 'esquema' que tenga una columna de tipo geometry, consultando
    directamente los metadatos de PostGIS."""
    consulta = text('''
        SELECT f_table_name, f_geometry_column, srid
        FROM geometry_columns
        WHERE f_table_schema = :esquema
    ''')
    with engine.connect() as conn:
        resultado = conn.execute(consulta, {'esquema': esquema})
        return [(fila[0], fila[1], fila[2]) for fila in resultado]


def estandarizar_tabla(engine, nombre_tabla, columna_geom, srid_origen):
    print()
    print('Procesando', nombre_tabla, '- columna', columna_geom, '- SRID origen', srid_origen)

    gdf = gpd.read_postgis(
        f'SELECT * FROM raw_data.{nombre_tabla}',
        engine,
        geom_col=columna_geom,
        crs=f'EPSG:{srid_origen}',
    )
    print('  leidas', len(gdf), 'filas de raw_data.' + nombre_tabla)

    gdf_proc = gdf.to_crs(epsg=SRID_DESTINO)

    gdf_proc.to_postgis(
        nombre_tabla, engine, schema='processed_data',
        if_exists='replace', index=False,
    )

    with engine.begin() as conn:
        conn.execute(text(
            f'CREATE INDEX IF NOT EXISTS idx_processed_{nombre_tabla} '
            f'ON processed_data.{nombre_tabla} USING GIST ({columna_geom})'
        ))

    print('  -> processed_data.' + nombre_tabla, 'lista en EPSG:' + str(SRID_DESTINO))


def main():
    engine = obtener_engine()
    tablas = listar_tablas_espaciales(engine)

    if not tablas:
        print('No se encontraron tablas con geometria en raw_data.')
        return

    print('Tablas espaciales encontradas en raw_data:')
    for nombre_tabla, columna_geom, srid_origen in tablas:
        print(' -', nombre_tabla, '(' + columna_geom + ', SRID ' + str(srid_origen) + ')')

    for nombre_tabla, columna_geom, srid_origen in tablas:
        estandarizar_tabla(engine, nombre_tabla, columna_geom, srid_origen)

    print()
    print('Estandarizacion completada para', len(tablas), 'tablas.')


if __name__ == '__main__':
    main()
