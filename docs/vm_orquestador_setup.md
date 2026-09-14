# Guía de Creación y Configuración del Orquestador (VM Azure)

Esta guía documenta el proceso exacto para aprovisionar, conectar y configurar la máquina virtual de producción (`mv-orquestador-tfm`) en Microsoft Azure, que alojará Apache Airflow y dbt para orquestar los pipelines de datos del TFM de Tenerife.

---

## 1. Creación de la Máquina en el Portal de Azure

La máquina debe crearse bajo la misma red virtual que la base de datos PostgreSQL para garantizar conectividad segura.

1. **Datos básicos:**
   - **Suscripción y Grupo:** Usar el grupo de recursos actual (`rg-tfm-tenerife`).
   - **Nombre de la VM:** `mv-orquestador-tfm`
   - **Región:** `Spain Central`
   - **Imagen (SO):** `Ubuntu Server 24.04 LTS - x64 Gen2`
   - **Tamaño:** `Standard_B2ats_v2` (2 vCPUs, 2 GiB RAM)
   - **Autenticación:** Clave pública SSH.
   - **Usuario:** `patron_tfm_mv`
   - **Par de claves:** Generar nuevo y descargarlo (`key-mv-orquestador.pem`).
   - **Puertos públicos:** Permitir acceso por el puerto `22 (SSH)`.

2. **Discos:**
   - **Tipo de SO:** HDD estándar o SSD Estándar de 30 GB.

3. **Redes:**
   - **Red virtual:** Seleccionar la VNet del proyecto (`vnet-spaincentral-1`).
   - **IP Pública:** Crear una nueva llamada `mv-orquestador-tfm-ip`.
   - **Grupo de Seguridad (NSG):** Crear uno nuevo llamado `mv-orquestador-tfm-nsg`.

*(Una vez completado, guarda a buen recaudo el archivo `key-mv-orquestador.pem` descargado)*.

---

## 2. Conexión a la Máquina Virtual (SSH)

Con el archivo `.pem` y la dirección IP Pública (disponible en el portal de Azure), abre una terminal local (PowerShell, Git Bash o CMD) e introduce el siguiente comando:

```bash
# Cambia la ruta por donde tengas guardado tu archivo .pem, y pon la IP correcta
ssh -i C:\Users\TU_USUARIO\Downloads\key-mv-orquestador.pem patron_tfm_mv@<IP_PUBLICA_AZURE>
```

> **Aviso de seguridad (Huella):** La primera vez que conectes, te preguntará si confías en el servidor (`Are you sure you want to continue connecting?`). Escribe `yes` y pulsa Enter.

---

## 3. Instalación de Software Base

Una vez dentro de la máquina (la terminal indicará `patron_tfm_mv@mv-orquestador-tfm`), actualiza el sistema e instala Python y Git:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git libpq-dev -y
```

---

## 4. Descarga del Proyecto

A continuación, clonamos el repositorio de GitHub (si el repo es privado, te pedirá tu usuario de GitHub y un *Personal Access Token* como contraseña):

```bash
git clone https://github.com/tu-usuario/AI_Dashboard_Core.git
cd AI_Dashboard_Core
```

---

## 5. Entorno Virtual y Dependencias

Creamos el entorno aislado e instalamos Apache Airflow junto con las librerías del proyecto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install apache-airflow
```

---

## 6. Configuración de Credenciales

Para que el servidor se pueda conectar a la base de datos de PostgreSQL y al Datalake, hay que replicar el archivo `.env`:

```bash
nano .env
```
Copia y pega en la terminal el contenido de tu `.env` local. Guarda los cambios pulsando `Ctrl+O`, luego `Enter`, y cierra con `Ctrl+X`.

---

## 7. Inicialización de Airflow

Finalmente, preparamos la base de datos interna de Airflow y creamos el usuario administrador para el panel web:

```bash
airflow db migrate
airflow users create \
    --username admin \
    --firstname Administrador \
    --lastname TFM \
    --role Admin \
    --email tu@email.com \
    --password <PON_AQUI_UNA_CONTRASEÑA>
```

*(Tras este paso, solo quedaría abrir el puerto 8080 en Azure y levantar los servicios web y scheduler para tener el orquestador en producción).*
