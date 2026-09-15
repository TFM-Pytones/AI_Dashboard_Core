import os
import sys
import subprocess
from dotenv import load_dotenv

def main():
    # Cargar variables de entorno del archivo .env (busqueda automatica hacia
    # arriba: el .env real vive un nivel por encima de AI_Dashboard_Core)
    load_dotenv()
    
    # Asegurarnos de que estamos pasando comandos a dbt
    if len(sys.argv) < 2:
        print("Uso: python run_dbt.py <comando_dbt> [argumentos...]")
        print("Ejemplo: python run_dbt.py run --select silver_h3_grid")
        sys.exit(1)
        
    dbt_args = sys.argv[1:]
    
    # Ruta al ejecutable de dbt en el entorno virtual
    dbt_executable = os.path.join(".venv", "Scripts", "dbt.exe")
    if not os.path.exists(dbt_executable):
        # Fallback por si acaso
        dbt_executable = "dbt"
        
    # Construir el comando completo
    cmd = [dbt_executable] + dbt_args
    
    # Ejecutar dentro de la carpeta dbt_project
    print(f"Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, cwd="dbt_project")

if __name__ == "__main__":
    main()
