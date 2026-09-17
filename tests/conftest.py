import sys
from pathlib import Path

# Asegura que la raíz del proyecto esté siempre en sys.path durante la ejecución de tests
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
