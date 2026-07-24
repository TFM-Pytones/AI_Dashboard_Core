# Guía Completa de Configuración y Uso de Máquinas Virtuales en Azure

Esta guía está diseñada para que cualquier miembro del equipo pueda comprender qué es la Máquina Virtual (VM) de Azure, cómo conectarse a ella desde su propio ordenador (sea Windows o macOS/Linux), configurarla desde cero para ejecutar scripts de Python, y resolver las dudas y errores más comunes durante el proceso.

---

## 1. Conceptos Básicos: ¿Qué es cada recurso en Azure?

Cuando creas una máquina virtual en Azure, se generan varios recursos asociados en tu grupo de recursos (*Resource Group*):

*   **Máquina Virtual (Virtual Machine - VM)**: Es el servidor virtual (en nuestro caso, con sistema operativo **Linux Ubuntu/Debian**) alojado en la nube. Consume recursos de procesamiento (CPU y RAM) solo cuando está **encendida**.
*   **Disco de Sistema Operativo (OS Disk / Disco)**: Es el "disco duro" de la máquina Linux. Aunque esté apagada, este disco sigue ocupando espacio físico en los servidores de Azure y genera un pequeño coste continuo.
*   **Dirección IP Pública (Public IP Address)**: Es la dirección numérica única (ej. `20.126.85.10`) que te permite conectarte a la VM. Mantener esta IP reservada tiene un coste mínimo por hora.
*   **Grupo de Seguridad de Red (Network Security Group - NSG)**: Es el cortafuegos (*firewall*) de tu máquina virtual. Controla qué puertos están abiertos (por ejemplo, el puerto `22` para permitir conexiones SSH externas).

---

## 2. Paso a Paso: Configuración desde Cero en la VM (Linux)

Sigue esta secuencia ordenada para preparar tu máquina virtual. Cada paso incluye los problemas específicos que te puedes encontrar.

### Paso 2.1: Iniciar y obtener la IP de la VM
1. Entra al **[Portal de Azure](https://portal.azure.com/)**.
2. Busca **Máquinas virtuales** y selecciona tu máquina (`mv-orquestador-tfm`).
3. Si el estado es *Detenido*, haz clic en **Iniciar** (Start) y espera a que cambie a **En ejecución** (Running).
4. Copia la **Dirección IP pública** que aparece en la tarjeta de *Esenciales* (Overview).

---

### Paso 2.2: Conectarse a la máquina virtual (Linux) desde tu ordenador host
Dependiendo de qué sistema operativo utilices en tu ordenador personal para trabajar:

*   **Desde Windows**:
    1. Abre la consola de **PowerShell** (o Git Bash).
    2. Ejecuta el comando de conexión SSH indicando el usuario de la VM y la IP pública que copiaste:
       ```bash
       ssh tu_usuario_de_la_vm@IP_PUBLICA_DE_LA_VM
       ```
    3. Escribe la contraseña de la máquina virtual (no verás los caracteres mientras escribes por seguridad) y pulsa `Enter`.
*   **Desde macOS / Linux**:
    1. Abre tu aplicación de **Terminal**.
    2. Ejecuta el mismo comando de conexión:
       ```bash
       ssh tu_usuario_de_la_vm@IP_PUBLICA_DE_LA_VM
       ```

---

### Paso 2.3: Generar un Token de Acceso Personal en GitHub (PAT)
GitHub ya no permite usar tu contraseña habitual en la línea de comandos de la VM. Necesitas un Token de Acceso Personal para poder clonar repositorios pertenecientes a organizaciones o privados.

1. Ve a **[GitHub](https://github.com)** en tu navegador, haz clic en tu foto de perfil (arriba a la derecha) y entra en **Settings** (Configuración).
2. En el menú lateral izquierdo, baja hasta el final y haz clic en **Developer Settings** (Ajustes de desarrollador).
3. Selecciona **Personal access tokens** -> **Tokens (classic)**.
4. Haz clic en **Generate new token** -> **Generate new token (classic)**.
5. Dale un nombre identificativo (ej. *VM Azure*), selecciona la casilla **`repo`** (imprescindible para clonar) y pulsa en **Generate token**.
6. **Copia el token largo que aparece en pantalla** (guárdalo temporalmente; una vez cierres la página no volverá a mostrarse).

---

### Paso 2.4: Descargar el proyecto en la VM (Git Clone)
Una vez conectado por SSH dentro de la terminal de la máquina virtual, descarga el repositorio. Para evitar que Git te pida de forma interactiva tu usuario y contraseña, **integra el Token de GitHub directamente en el comando**:

```bash
git clone https://TU_TOKEN_DE_GITHUB@github.com/TFM-Pytones/AI_Dashboard_Core.git
```
*(Sustituye `TU_TOKEN_DE_GITHUB` por el token largo que copiaste de GitHub en el paso anterior).*

#### ⚠️ Problema común al actualizar el código más adelante: "Your local changes would be overwritten by merge"
*   **Por qué ocurre**: Has ejecutado pruebas en la VM que han modificado algún archivo localmente (como el progreso del scraping) y Git bloquea el `git pull` para no sobreescribir tus cambios.
*   **Solución**: Si quieres descartar esos cambios de la VM y traer la versión limpia de GitHub, ejecuta:
    ```bash
    git checkout -- ruta/del/archivo/con/cambios
    git pull
    ```

---

### Paso 2.5: Crear y activar el entorno virtual de Python en la VM (Linux)
El entorno virtual (`.venv`) mantiene aisladas las librerías de tu proyecto para evitar conflictos con el sistema operativo de la máquina virtual.

```bash
# Crear el entorno virtual en una carpeta llamada .venv
python3 -m venv .venv

# Activar el entorno virtual
source .venv/bin/activate
```
*(Sabrás que se ha activado correctamente porque el indicador de tu consola ahora empezará por el prefijo `(.venv)`)*.

#### ⚠️ Problema común 1: Error "ensurepip is not available" al crear el entorno
*   **Por qué ocurre**: En distribuciones Linux limpias (como Ubuntu o Debian), el módulo `venv` de Python viene separado del paquete base por defecto para ahorrar espacio.
*   **Solución**: Instala el paquete de entornos virtuales en el sistema operativo mediante el gestor de paquetes de la VM e inténtalo de nuevo:
    ```bash
    sudo apt update
    sudo apt install -y python3-venv
    # (Si sabes la versión exacta de Python instalada, ej. 3.12, puedes forzarla):
    sudo apt install -y python3.12-venv
    ```
    Una vez instalado, borra la carpeta fallida e inténtalo de nuevo:
    ```bash
    rm -rf .venv
    python3 -m venv .venv
    ```

#### ⚠️ Problema común 2: Ha desaparecido el "(.venv)" al principio de la consola al reconectarte
*   **Por qué ocurre**: Cada vez que cierras la consola SSH y te vuelves a conectar, inicias una sesión de terminal limpia. El entorno sigue existiendo en el disco, pero está desactivado.
*   **Solución**: Entra en tu carpeta de proyecto y vuelve a activarlo:
    ```bash
    source ../.venv/bin/activate   # (Si creaste el .venv en la raíz del usuario)
    # o bien:
    source .venv/bin/activate      # (Si creaste el .venv dentro de la carpeta del proyecto)
    ```

---

### Paso 2.6: Crear el archivo de configuración `.env` en la VM
El archivo `.env` almacena de forma segura las credenciales de bases de datos y accesos. **No se debe subir a GitHub**, por lo que hay que crearlo directamente en la VM usando el editor de texto integrado de Linux (`Nano`).

1. Estando en la consola de la VM, ejecuta el comando:
   ```bash
   nano .env
   ```
   *(Se abrirá una pantalla de edición vacía en tu terminal).*
2. Copia las credenciales de tu ordenador y pégalas:
   * **Si te conectas desde Windows (PowerShell/Git Bash)**: Simplemente haz **clic derecho** dentro de la ventana de la consola para pegar el contenido del portapapeles.
   * **Si te conectas desde macOS**: Pulsa `Cmd + V` o haz clic derecho -> *Paste*.
3. **Guardar y salir de Nano**:
   * Pulsa **`Ctrl + O`** para preparar el guardado del archivo.
   * Pulsa **`Enter`** para confirmar que deseas guardarlo con el nombre `.env`.
   * Pulsa **`Ctrl + X`** para salir del editor Nano y volver a la consola habitual de Linux.

---

### Paso 2.7: Instalar las dependencias (requirements.txt)

> [!IMPORTANT]
> **Paso obligatorio previo**: Antes de instalar las dependencias, debes navegar mediante la terminal al directorio donde esté alojado el archivo `requirements.txt` (en este caso, la carpeta del proyecto `AI_Dashboard_Core`). Si intentas ejecutar `pip` fuera de esta carpeta, Python te dará el error `No such file or directory` porque no encontrará el archivo de requerimientos.

```bash
# 1. Navegar obligatoriamente a la carpeta del proyecto
cd AI_Dashboard_Core

# 2. Instalar los requerimientos
pip install --upgrade pip
pip install -r requirements.txt
```

#### ⚠️ Problema común: Error "pg_config executable not found" o fallos instalando "psycopg2"
*   **Por qué ocurre**: Librerías de bases de datos como `psycopg2` o herramientas de datos como `dbt-postgres` necesitan compilar código C localmente en la VM y requieren dependencias de desarrollo del sistema operativo.
*   **Solución**: Instala las herramientas de compilación y librerías de PostgreSQL necesarias en el sistema operativo de tu VM antes de volver a ejecutar el comando de instalación de Python:
    ```bash
    sudo apt install -y libpq-dev python3-dev build-essential
    ```
    Una vez finalizada la instalación de los paquetes del sistema, ejecuta de nuevo:
    ```bash
    pip install -r requirements.txt
    ```

---

## 3. Ejecución en Segundo Plano (Nohup)

Si cierras la terminal de SSH, la sesión terminará y tu script en ejecución se apagará. Para dejar los procesos corriendo en la nube indefinidamente y poder apagar tu ordenador personal:

1. Ejecuta el script añadiendo **`nohup`** al principio y el símbolo **`&`** al final:
   ```bash
   nohup python3 ingestion/agrocabildo/agrocabildo_historical_backfill.py --station-range 35-45 > scraper.log 2>&1 &
   ```
   *(Esto ejecutará el código de fondo y redirigirá la salida de logs a un archivo llamado `scraper.log`)*.
2. Ahora ya puedes cerrar la terminal directamente o escribir `exit`. El servidor de Azure continuará trabajando.

Si quieres volver a conectarte más tarde para ver el progreso de los logs en tiempo real:
```bash
tail -f scraper.log
```

---

## 4. Control de Costes: Buenas Prácticas

Las suscripciones de Azure consumen crédito por segundo. Sigue estas pautas para no agotar el crédito del equipo innecesariamente:

1.  **Diferencia entre Apagar y Desasignar**:
    *   Si entras a la VM y ejecutas `sudo poweroff` o le das a "Apagar" dentro del sistema operativo, Azure **seguirá cobrándote el procesamiento** porque los recursos de hardware siguen asignados a ti.
    *   Para dejar de pagar por el procesamiento, **siempre debes apagar la VM desde el Portal de Azure** haciendo clic en el botón **"Detener"** (Stop), asegurándote de que el estado pase a **Detenido (desasignado)** (*Stopped (Deallocated)*).
2.  **Pausar Bases de Datos**: Si utilizas bases de datos administradas (como Azure Database for PostgreSQL Flexible Server), recuerda pulsar el botón **Detener** (Stop) en su panel de control si vas a pasar más de 1 o 2 días sin realizar consultas para pausar los costes de cómputo.
