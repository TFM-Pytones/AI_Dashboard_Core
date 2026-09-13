import os
import subprocess
import sys

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Encontrar todos los scripts que empiecen por número (01_, 02_, etc.)
    scripts = []
    for file in os.listdir(current_dir):
        if file.endswith('.py') and file[0].isdigit():
            scripts.append(file)
            
    # 2. Ordenarlos alfabéticamente para garantizar el orden correcto (01_, 02_, 03_...)
    scripts.sort()
    
    if not scripts:
        print("No se encontraron scripts numerados en la carpeta.")
        return

    print("=====================================================")
    print(f"Iniciando ejecución secuencial de {len(scripts)} scripts:")
    for s in scripts:
        print(f" - {s}")
    print("=====================================================\n")

    # 3. Ejecutar uno a uno
    for script in scripts:
        script_path = os.path.join(current_dir, script)
        print(f"\n🚀 EJECUTANDO: {script}")
        print("-" * 50)
        
        # Ejecutar el subproceso (sys.executable asegura que usa el mismo entorno virtual)
        try:
            result = subprocess.run(
                [sys.executable, script_path], 
                cwd=current_dir,
                check=True
            )
            print("-" * 50)
            print(f"✅ ÉXITO: {script} completado correctamente.")
        except subprocess.CalledProcessError as e:
            print("-" * 50)
            print(f"❌ ERROR: El script {script} falló o se interrumpió.")
            print("Deteniendo la ejecución. Los siguientes scripts no se ejecutarán.")
            sys.exit(1)
            
    print("\n🎉 TODOS LOS SCRIPTS SE HAN EJECUTADO CON ÉXITO 🎉")

if __name__ == "__main__":
    main()
