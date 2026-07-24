# Guía Completa de Configuración y Uso de Máquinas Virtuales en Azure

Esta guía está diseñada para que cualquier miembro del equipo pueda comprender qué es la Máquina Virtual (VM) de Azure, cómo conectarse a ella, configurarla desde cero para ejecutar scripts de Python, y resolver las dudas y errores más comunes que suelen surgir durante el proceso.

---

## 1. Conceptos Básicos: ¿Qué es cada recurso en Azure?

Cuando creas una máquina virtual en Azure, se generan varios recursos asociados en tu grupo de recursos (*Resource Group*). Es importante entender qué hace cada uno para comprender la facturación y el funcionamiento:

*   **Máquina Virtual (Virtual Machine - VM)**: Es el ordenador virtual propiamente dicho que está alojado en los centros de datos de Microsoft. Consume recursos de procesamiento (CPU y RAM) solo cuando está **encendida**.
*   **Disco de Sistema Operativo (OS Disk / Disco)**: Es el "disco duro" de la máquina. Aunque la máquina virtual esté apagada, este disco sigue ocupando espacio físico en los servidores de Azure y genera un pequeño coste de almacenamiento continuo.
*   **Dirección IP Pública (Public IP Address)**: Es la dirección numérica única (ej. `20.126.85.10`) que permite que tu ordenador personal se comunique con la máquina virtual a través de Internet. Mantener esta IP reservada tiene un coste mínimo por hora.
*   **Grupo de Seguridad de Red (Network Security Group - NSG)**: Es el cortafuegos (*firewall*) de tu máquina virtual. Define qué puertos están abiertos (por ejemplo, el puerto `22` para SSH o el puerto `3389` para Escritorio Remoto RDP).

---

## 2. Paso a Paso: Configuración desde Cero en la VM

Una vez creada la máquina virtual en el Portal de Azure, sigue estos pasos para configurarla para cualquier proyecto de Python:

### Paso 2.1: Iniciar y obtener la IP de la VM
1. Entra al **[Portal de Azure](https://portal.azure.com/)**.
2. Busca **Máquinas virtuales** y selecciona tu máquina.
3. Si el estado es *Detenido*, haz clic en **Iniciar** (Start) y espera a que cambie a **En ejecución** (Running).
4. Copia la **Dirección IP pública** que aparece en la tarjeta de *Esenciales* (Essentials).

### Paso 2.2: Conectarse a la máquina virtual
Abre la consola de tu ordenador (PowerShell en Windows, o la Terminal en macOS/Linux) y conéctate por SSH (si tu VM es Linux):
```bash
ssh tu_usuario_de_la_vm@IP_PUBLICA_DE_LA_VM
```
Introduce la contraseña que creaste al dar de alta la máquina en Azure.

### Paso 2.3: Preparar el entorno del Sistema Operativo (Linux/Ubuntu)
Por defecto, las imágenes limpias de Linux no traen instaladas algunas herramientas esenciales de Python. Ejecuta los siguientes comandos para preparar la máquina:

```bash
# Actualizar el gestor de paquetes de la máquina
sudo apt update

# Instalar el creador de entornos virtuales y compiladores básicos de C
sudo apt install -y python3-venv python3-pip libpq-dev python3-dev build-essential
```

> [!IMPORTANT]
> El paquete `libpq-dev` y `build-essential` son necesarios para compilar librerías que conectan con bases de datos (como `psycopg2` o herramientas de analítica). Si no se instalan, Python dará un error al intentar instalar las dependencias del proyecto.

### Paso 2.4: Descargar el proyecto (Git)
Clona el repositorio en el que vayas a trabajar en tu carpeta de usuario de la VM:
```bash
git clone https://github.com/tu-organizacion/tu-repositorio.git
cd tu-repositorio
```

### Paso 2.5: Crear y activar el entorno virtual de Python
Crear un entorno virtual (`venv`) evita que las librerías del proyecto entren en conflicto con las del sistema operativo de la máquina virtual:

```bash
# Crear el entorno virtual en una carpeta llamada .venv
python3 -m venv .venv

# Activar el entorno virtual
source .venv/bin/activate
```
*(Sabrás que se ha activado correctamente porque el indicador de tu consola ahora empezará por `(.venv)`)*.

### Paso 2.6: Instalar las dependencias
Con el entorno virtual activo, instala todos los requerimientos del proyecto:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Resolución de Problemas y Preguntas Frecuentes

### ❓ ¿Cómo cierro la terminal sin que se pare el script?
Si ejecutas un script de Python normalmente (ej. `python3 script.py`) y cierras la consola, el script se apagará de inmediato. Para que se ejecute de fondo (*background*) y puedas cerrar la terminal o apagar tu ordenador personal:

1. Detén el script actual con `Ctrl + C`.
2. Ejecútalo usando **`nohup`** y el símbolo **`&`** al final:
   ```bash
   nohup python3 script.py > ejecucion.log 2>&1 &
   ```
3. Esto generará un proceso independiente en la nube y guardará todo lo que imprima el script en un archivo de texto llamado `ejecucion.log`. Ya puedes cerrar la terminal.

Para ver el progreso de la ejecución en tiempo real en otro momento:
```bash
tail -f ejecucion.log
```

---

### ❌ Error: "ensurepip is not available"
*   **Causa**: Estás intentando crear un entorno virtual en una distribución Linux (como Ubuntu o Debian) que separa el módulo `venv` del paquete básico de Python.
*   **Solución**: Instala el paquete de desarrollo correspondiente a la versión de Python que tenga la VM.
    ```bash
    sudo apt install -y python3-venv
    # Si sabes la versión exacta (ej. Python 3.12):
    sudo apt install -y python3.12-venv
    ```

---

### ❌ Error: "pg_config executable not found" o fallos al compilar "psycopg2"
*   **Causa**: Estás instalando paquetes de bases de datos que requieren compilar código en C durante la instalación, y la máquina virtual no tiene instalados los archivos de cabecera de base de datos ni los compiladores del sistema.
*   **Solución**: Ejecuta el siguiente comando para instalar las herramientas de compilación necesarias en el sistema operativo:
    ```bash
    sudo apt install -y libpq-dev python3-dev build-essential
    ```

---

### ❌ Error: "Your local changes would be overwritten by merge" al hacer Git Pull
*   **Causa**: Tienes archivos modificados localmente en la VM (como el archivo de progreso del scraping o configuraciones locales) y Git no quiere sobreescribirlos al descargar la nueva versión de GitHub.
*   **Solución**: Si quieres descartar esos cambios locales de la VM y quedarte con lo que hay en GitHub:
    ```bash
    git checkout -- ruta/del/archivo/con/cambios
    git pull
    ```

---

### ❓ He vuelto a entrar a la VM y ha desaparecido el "(.venv)" al principio
*   **Causa**: Cada vez que abres una nueva conexión SSH o abres una terminal nueva, inicias una sesión limpia y debes volver a activar el entorno de desarrollo.
*   **Solución**: Entra a la carpeta de tu repositorio y vuelve a ejecutar el comando de activación:
    ```bash
    cd tu-repositorio
    source .venv/bin/activate
    ```

---

## 4. Control de Costes: Buenas Prácticas

Las suscripciones de Azure consumen crédito por segundo. Sigue estas pautas para no agotar el crédito del equipo innecesariamente:

1.  **Diferencia entre Apagar y Desasignar**:
    *   Si entras a la VM y ejecutas `sudo poweroff` o le das a "Apagar" dentro de la interfaz, Azure **seguirá cobrándote el procesamiento** porque los recursos de hardware siguen reservados para ti.
    *   Para dejar de pagar por el procesamiento, **siempre debes apagar la VM desde el Portal de Azure** (el botón "Detener" o *Stop*), asegurándote de que el estado pase a **Detenido (desasignado)** o *Stopped (Deallocated)*.
2.  **IP Estática vs Dinámica**: Si no necesitas una IP pública fija, configúrala como dinámica. De esta forma, si la máquina está apagada, no te cobrarán por la IP reservada.
3.  **Pausar Bases de Datos**: Si utilizas bases de datos administradas (como Azure Database for PostgreSQL), recuerda pulsar el botón **Detener** (Stop) en su panel correspondiente si vas a pasar varios días sin realizar consultas para pausar los costes de cómputo de la base de datos.
