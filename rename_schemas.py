import os
import re

# Directorio raiz
root_dir = r"c:\Users\ROBERTO\Proyectos_Python\TFM_TUI_Tenerife\AI_Dashboard_Core"

# Extensiones permitidas
allowed_exts = {".md", ".py", ".yml", ".yaml", ".sql", ".ipynb"}

# Directorios a excluir
exclude_dirs = {".venv", ".git", "__pycache__", ".ipynb_checkpoints"}

# Reglas de reemplazo
replacements = [
    (r"\braw_data\b", "bronze"),
    (r"\bprocessed_data\b", "silver"),
    (r"\bbronce\b(?!-raw)", "bronze"),
    (r"\bplata\b", "silver"),
    (r"\bPlata\b", "Silver"),
    (r"\bBronce\b(?!-raw)", "Bronze"),
    (r"\boro\b", "gold"),
    (r"\bOro\b", "Gold"),
]

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = content
    for pattern, repl in replacements:
        new_content = re.sub(pattern, repl, new_content)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

changed_files = 0
for subdir, dirs, files in os.walk(root_dir):
    # Exclude directories
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in allowed_exts:
            filepath = os.path.join(subdir, file)
            try:
                if process_file(filepath):
                    print(f"Modificado: {filepath}")
                    changed_files += 1
            except Exception as e:
                print(f"Error leyendo {filepath}: {e}")

print(f"\nSe han modificado {changed_files} archivos en total.")
