# Guía de Gestión de Accesos y Redes en Azure (Guía de Migración)

Esta guía detalla cómo configurar el control de accesos, redes y seguridad en Azure cuando el proyecto sea migrado a otra suscripción, cuenta o entorno de Azure de producción.

---

## 1. Control de Acceso (IAM) en el Grupo de Recursos

Cuando migres el proyecto, el nuevo administrador de la cuenta de Azure deberá dar acceso a todo el equipo de desarrollo a nivel de **Grupo de Recursos** (*Resource Group*) para que todos puedan administrar la máquina virtual, la base de datos y el almacenamiento.

### Paso a paso para asignar accesos en el portal:
1. En el Portal de Azure, entra al nuevo **Grupo de recursos**.
2. En el menú de la izquierda, haz clic en **Control de acceso (IAM)**.
3. Haz clic en **Agregar** -> **Agregar asignación de rol** (*Add role assignment*).
4. **IMPORTANTE (Pestañas de Roles)**:
   * Por defecto, Azure te mostrará la pestaña **"Roles de función de trabajo"** (donde solo salen subtipos limitados como *Colaborador de VM*, *Colaborador de SQL*, etc.).
   * Para dar permisos generales a todo el grupo, haz clic en la pestaña superior llamada **"Roles de administrador de privilegios"** (*Privileged administrator roles*).
5. Selecciona uno de los siguientes roles principales:
   * **`Colaborador` (Contributor)**: Permite administrar todos los recursos (VM, Postgres, Storage), pero no permite añadir a otras personas ni ver costes de facturación. *(Recomendado para el equipo de desarrollo)*.
   * **`Propietario` (Owner)**: Permite administrar todos los recursos y, además, delegar accesos y añadir a otras personas.
6. En la pestaña de miembros, busca y selecciona a tus compañeros por su correo y haz clic en **Revisar y asignar**.

### ⚠️ Permiso extra para explorar archivos en el Portal:
El rol de *Colaborador* general a veces bloquea la descarga o visualización de archivos desde la interfaz web del Datalake. Si los desarrolladores necesitan explorar los archivos Parquet directamente desde el portal web, debes asignarles adicionalmente el rol:
*   **`Colaborador de datos de Storage Blob`** (*Storage Blob Data Contributor*).

---

## 2. Configuración de Red y Firewall de PostgreSQL (Flexible Server)

Por seguridad, Azure Database for PostgreSQL bloquea por defecto cualquier conexión externa. Al migrar a un nuevo servidor PostgreSQL, debes habilitar los accesos de red:

1. Entra al nuevo recurso de **Azure Database for PostgreSQL flexible server**.
2. En el menú izquierdo, ve a **Redes** (*Networking*).
3. Configura las siguientes reglas en la sección de **Firewall**:

### A. Permitir la conexión desde la Máquina Virtual de Azure:
* Activa la casilla **"Permitir acceso público desde cualquier servicio de Azure dentro de esta suscripción a este servidor"** (*Allow public access from any Azure service...*). Esto permite que tus scrapers en la VM conecten con la base de datos sin necesidad de configurar IPs complejas.

### B. Permitir la conexión a los ordenadores locales de los desarrolladores:
* Para que vuestros ordenadores personales o de trabajo puedan consultar la base de datos localmente (DBeaver, Python local, etc.), debéis registrar vuestras IPs públicas.
* Haz clic en **"Agregar dirección IP de cliente actual"** (*Add current client IP address*) para registrar tu IP.
* Si tus compañeros necesitan conectarse, introduce un nombre identificativo para su regla y su dirección IP pública.
* Haz clic en **Guardar** (arriba a la izquierda) para aplicar los cambios de red.

---

## 3. Configuración de Red y Puertos de la Máquina Virtual (NSG)

Para permitir que te puedas conectar a tu nueva máquina virtual Linux mediante SSH desde tu ordenador local:

1. En el Portal de Azure, entra al recurso de la **Máquina virtual**.
2. En el menú izquierdo, ve a **Redes** (*Networking*).
3. Asegúrate de tener una **Regla de puerto de entrada** (*Inbound port rule*) configurada para el protocolo **SSH**:
   * **Puerto de destino**: `22`
   * **Protocolo**: `TCP`
   * **Acción**: `Permitir` (Allow)
   * **Origen**: Puedes dejarlo en `Any` (Cualquiera) o, para mayor seguridad en entornos corporativos, limitar el origen a las IPs públicas de tu equipo.

---

## 4. Checklist de Credenciales para el archivo `.env`

Cuando todos los recursos estén creados en el nuevo Azure, debes generar y repartir el nuevo archivo `.env` con la siguiente información:

```env
# Variables de la nueva base de datos PostgreSQL en Azure
AZURE_DB_HOST=servidor-nuevo.postgres.database.azure.com
AZURE_DB_USER=usuario_administrador
AZURE_DB_PASSWORD=contraseña_segura
AZURE_DB_NAME=postgres
AZURE_DB_URL="postgresql://usuario:contraseña@servidor-nuevo:5432/postgres?sslmode=require"

# Cadena de conexión del nuevo Datalake
# (Se obtiene en el Storage Account -> menú izquierdo "Claves de acceso" -> Botón "Mostrar claves" -> Copiar "Cadena de conexión")
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=nuevoname;AccountKey=clave_larga;EndpointSuffix=core.windows.net"
```
