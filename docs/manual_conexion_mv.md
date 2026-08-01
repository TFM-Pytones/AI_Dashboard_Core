# Manual General de Operación y Administración de la Máquina Virtual (VM)

Este documento describe de forma genérica los pasos para conectarse, administrar los recursos, gestionar dependencias y lanzar tareas en segundo plano en la Máquina Virtual (VM) de Azure.

---

## 1. Conexión SSH y Navegación

Para conectarse a la máquina virtual desde tu terminal local (PowerShell, Git Bash, Linux o la terminal de macOS):

```bash
ssh patron_tfm_mv@68.221.135.144
```

Una vez dentro del servidor, accede al directorio del proyecto:

```bash
cd AI_Dashboard_Core
```

---

## 2. Entorno Virtual e Instalación Selectiva de Dependencias (Ahorro de disco)

Para aislar las librerías del proyecto, activa siempre el entorno virtual:

```bash
source ~/.venv/bin/activate
```

> [!IMPORTANT]
> **Control de Dependencias Pesadas**
> Algunas librerías incluidas en el archivo general `requirements.txt` (como `PyTorch`, `TensorFlow`, `Transformers` u otras de Deep Learning/NLP) ocupan gigabytes de espacio en disco y exigen mucha CPU/RAM durante su compilación.
>
> Para evitar saturar el almacenamiento de la VM o provocar caídas por falta de RAM, se recomienda instalar únicamente lo necesario para el propósito del servidor (por ejemplo, solo dependencias de ingesta o base de datos) comentando o excluyendo los paquetes pesados.

### Estrategias de Instalación Selectiva

* **Comentar líneas en el archivo**: Edita `requirements.txt` en la VM (ej. `nano requirements.txt`) y añade un símbolo `#` delante de las librerías pesadas que no se necesiten en el servidor:
  ```text
  # torch>=2.0.0          <-- Comentado para evitar su descarga en la VM
  # rasterio>=1.3.16      <-- Comentado para evitar su descarga en la VM
  ```

---

## 3. Actualización del Código (Git)

Para mantener el servidor sincronizado con los últimos cambios del repositorio en GitHub:

```bash
git pull origin main
```

Si hay conflictos con archivos modificados automáticamente por el servidor en sus ejecuciones (archivos de progreso local, bases de datos SQLite locales, logs, etc.), puedes usar **Git Stash** para no perder cambios locales:

```bash
git stash                 # Guarda tus cambios locales temporalmente
git pull origin main      # Descarga la última versión del repositorio
git stash pop             # Aplica tus cambios locales de nuevo sobre el código nuevo
```

---

## 4. Monitoreo de Capacidad y Recursos del Sistema

Antes y durante la ejecución de tareas pesadas, es vital verificar la capacidad del servidor para evitar bloqueos:

* **Espacio libre en disco duro**:
  ```bash
  df -h
  ```
  *(Revisa el porcentaje de uso de la partición raíz `/`)*.
* **Memoria RAM libre y en uso**:
  ```bash
  free -h
  ```
  *(O `free -m` para ver los valores detallados en Megabytes)*.
* **Monitoreo de CPU y procesos en tiempo real**:
  ```bash
  htop
  ```
  *(O `top` si htop no está instalado. Permite identificar qué procesos consumen más recursos)*.

---

## 5. Control de Procesos (Detener tareas en ejecución)

Si un script se queda colgado o necesitas detenerlo manualmente para liberar recursos:

1. **Buscar el identificador de proceso (PID)**:
   ```bash
   ps aux | grep <nombre_del_script_o_tecnologia>
   ```
   *Ejemplo*: `ps aux | grep python`

2. **Detener el proceso usando su PID**:
   * Parada ordenada (SIGTERM):
     ```bash
     kill <PID>
     ```
   * Parada forzada inmediata (SIGKILL):
     ```bash
     kill -9 <PID>
     ```

3. **Detener todos los procesos que coincidan con un nombre/patrón**:
   ```bash
   pkill -9 -f <nombre_patron>
   ```
   *Ejemplo*: `pkill -9 -f python`

---

## 6. Gestión de Archivos de Progreso (JSON)

Muchos pipelines utilizan archivos JSON para recordar qué tareas o bloques ya han sido completados con éxito y evitar repetirlos en ejecuciones futuras.

Si necesitas forzar al script a repetir un lote de trabajo específico, puedes limpiar sus claves correspondientes directamente desde la terminal con este comando rápido de Python:

```bash
python -c "import json; f = 'ruta/progreso.json'; data = json.load(open(f)); data['keys'] = [k for k in data['keys'] if not k.startswith('prefijo_a_borrar')]; json.dump(data, open(f, 'w'), indent=2)"
```

---

## 7. Ejecución en Segundo Plano (Nohup)

Si ejecutas un script normal y cierras la sesión SSH, la VM matará el proceso. Para evitarlo y permitir que la tarea continúe de fondo (background):

```bash
nohup <ruta_python> <ruta_script.py> --argumento valor > salida.log 2>&1 &
```

* **`nohup`**: Ignora la señal de desconexión del usuario (*No Hang Up*).
* **`> salida.log 2>&1`**: Redirige tanto la salida estándar como los errores al archivo de log.
* **`&`**: Envía la tarea a ejecutarse de fondo.

### Ejemplo práctico
```bash
nohup ~/.venv/bin/python ingestion/script.py --range 1-10 > run.log 2>&1 &
```

Para verificar la salida del script en tiempo real:
```bash
tail -f run.log
```
*(Pulsa `Ctrl+C` para salir del modo de visualización en tiempo real sin detener el script)*.
