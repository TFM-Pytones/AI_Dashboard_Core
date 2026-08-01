#!/bin/bash
# Script secuencial para descargar el histórico de Agrocabildo en la VM
echo "=== Iniciando secuencia de descargas históricas ==="
date

echo "1/4. Descargando Estación ID 9 (Index 5)..."
~/.venv/bin/python ingestion/agrocabildo/agrocabildo_historical_backfill.py --start-year 2019 --station-range 5

echo "2/4. Descargando Estación ID 12 (Index 8)..."
~/.venv/bin/python ingestion/agrocabildo/agrocabildo_historical_backfill.py --start-year 2019 --station-range 8

echo "3/4. Descargando Estaciones ID 88, 89 y 90 (Index 40-42)..."
~/.venv/bin/python ingestion/agrocabildo/agrocabildo_historical_backfill.py --start-year 2019 --station-range 40-42

echo "4/4. Descargando Estaciones ID 101 y 3 siguientes (Index 51-54)..."
~/.venv/bin/python ingestion/agrocabildo/agrocabildo_historical_backfill.py --start-year 2019 --station-range 51-54

echo "=== Secuencia completada con éxito ==="
date
