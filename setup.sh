#!/usr/bin/env bash
#
# Prepara el entorno local del proyecto: venv, dependencias y kernel de Jupyter.
#
# PASOS QUE TIENES QUE SEGUIR:
#   1. Trae los ultimos cambios:          git pull origin main
#   2. Ejecuta este script:                bash setup.sh
#   3. Rellena el archivo .env que se te   (se crea solo si no lo tenias, a partir
#      habra creado, con las credenciales   de .env.example) con los valores reales
#      reales de la base de datos           que te pase alguien del equipo por un
#                                            canal privado (NUNCA por git ni chat publico)
#   4. Abre notebooks/connect_neon.ipynb en VSCode y selecciona el kernel
#      "AI Dashboard Core (.venv)" (arriba a la derecha) si no se selecciona solo
#   5. Verifica que todo funciona:
#        - En el notebook: dale a "Run All", debe decir "Conexion completada"
#        - En dbt:  cd dbt_project
#                    export $(grep -v '^#' ../.env | xargs)
#                    DBT_PROFILES_DIR=. ../.venv/bin/dbt debug
#                    (debe terminar en "All checks passed!")
#
# El .env con las credenciales reales NO se toca aqui por seguridad: si ya
# existe se deja intacto; si no existe, se crea vacio a partir de .env.example
# y hay que rellenarlo a mano (paso 3).
set -e

cd "$(dirname "$0")"

KERNEL_NAME="ai_dashboard_core"
KERNEL_DISPLAY="AI Dashboard Core (.venv)"

if [ ! -d ".venv" ]; then
    echo "==> Creando entorno virtual (.venv)..."
    python3 -m venv .venv
else
    echo "==> .venv ya existe, se reutiliza."
fi

echo "==> Instalando dependencias de requirements.txt..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "==> Registrando kernel de Jupyter '$KERNEL_NAME'..."
.venv/bin/python -m ipykernel install --user --name "$KERNEL_NAME" --display-name "$KERNEL_DISPLAY"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "AVISO: no tenias .env, se ha creado uno vacio a partir de .env.example."
    echo "       Rellena DB_USER, DB_PASSWORD, DB_HOST y DB_NAME antes de continuar"
    echo "       (pide los valores reales por un canal privado, nunca por git)."
else
    echo "==> .env ya existe, no se toca."
fi

echo ""
echo "Setup completado. Proximos pasos:"
echo "  1. Si el .env se acaba de crear, rellenalo con las credenciales reales."
echo "  2. En VSCode, abre notebooks/connect_neon.ipynb y selecciona el kernel '$KERNEL_DISPLAY'."
echo "  3. Dale a 'Run All' en el notebook: debe decir 'Conexion completada'."
echo "  4. Prueba dbt:"
echo "       cd dbt_project"
echo "       export \$(grep -v '^#' ../.env | xargs)"
echo "       DBT_PROFILES_DIR=. ../.venv/bin/dbt debug"
echo "     Debe terminar en 'All checks passed!'."
