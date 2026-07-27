#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script unificado de configuración del entorno local (venv, dependencias y kernel Jupyter).
Compatible con Windows, macOS y Linux.

Ejecución:
    python setup.py (o python AI_Dashboard_Core/setup.py)
"""

import os
import sys
import shutil
import subprocess

def run_command(args, cwd=None):
    """Ejecuta un comando del sistema de forma segura."""
    try:
        subprocess.run(args, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar: {' '.join(args)}")
        sys.exit(e.returncode)

def main():
    # Asegurar que el directorio de trabajo es el del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print("==> Preparando entorno local de desarrollo...")

    # 1. Determinar el entorno virtual a usar/crear
    venv_name = ".venv"
    if os.path.isdir(venv_name):
        print("==> Se detectó entorno virtual '.venv' existente. Se reutilizará.")
    else:
        print(f"==> Creando entorno virtual '{venv_name}'...")
        run_command([sys.executable, "-m", "venv", venv_name])

    # 2. Determinar ruta de binarios según el sistema operativo
    if os.name == "nt":  # Windows
        venv_python = os.path.join(venv_name, "Scripts", "python.exe")
    else:  # macOS / Linux
        venv_python = os.path.join(venv_name, "bin", "python")

    if not os.path.exists(venv_python):
        print(f"ERROR: No se encontró el ejecutable de Python en {venv_python}")
        sys.exit(1)

    print(f"==> Usando Python del venv: {venv_python}")

    # 3. Actualizar pip e instalar dependencias
    print("==> Instalando dependencias desde requirements.txt...")
    run_command([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
    run_command([venv_python, "-m", "pip", "install", "-r", "requirements.txt"])

    # 4. Registrar kernel de Jupyter
    kernel_name = "ai_dashboard_core"
    kernel_display = "AI Dashboard Core (.venv)"
    print(f"==> Registrando kernel de Jupyter '{kernel_display}'...")
    run_command([
        venv_python, "-m", "ipykernel", "install",
        "--user", "--name", kernel_name, "--display-name", kernel_display
    ])

    # 5. Crear archivo .env si no existe
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
            print("\nAVISO: Se ha creado el archivo '.env' a partir de '.env.example'.")
            print("       Rellena las credenciales de la base de datos en '.env' antes de continuar.")
    else:
        print("==> El archivo '.env' ya existe, no se modifica.")

    print("\nSetup completado exitosamente de forma multiplataforma.")
    print("Próximos pasos:")
    print("  1. Verifica tu archivo .env con las credenciales reales de Neon DB.")
    print("  2. Abre notebooks/connect_neon.ipynb en VS Code y selecciona el kernel 'AI Dashboard Core (.venv)'.")

if __name__ == "__main__":
    main()
