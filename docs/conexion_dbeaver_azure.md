# Guía de Conexión: DBeaver con Azure Database for PostgreSQL

Esta guía explica paso a paso cómo conectar el gestor de bases de datos **DBeaver** al servidor flexible de PostgreSQL en Azure (`db-tfm-tenerife`).

---

## Requisitos Previos

Antes de comenzar, asegúrate de tener instalados los siguientes componentes:
1. **DBeaver Community Edition**: Descargable de forma gratuita desde [dbeaver.io](https://dbeaver.io/).
2. **Acceso de Red (Firewall)**: Tu dirección IP pública debe estar autorizada en las reglas de firewall del servidor flexible de Azure para que permita la conexión.

---

## Paso a Paso para la Conexión

### Paso 1: Crear una Nueva Conexión en DBeaver
1. Abre DBeaver.
2. En la esquina superior izquierda (o en el menú `Archivo -> Nueva conexión`), haz clic en el icono del **Enchufe con un símbolo "+"**.
3. En la lista de bases de datos, selecciona **PostgreSQL** y haz clic en **Siguiente**.

---

### Paso 2: Rellenar la Configuración Principal (Pestaña "Main")
Introduce los siguientes valores correspondientes al entorno del TFM:

| Campo | Valor |
| :--- | :--- |
| **Host** | `db-tfm-tenerife.postgres.database.azure.com` |
| **Port** | `5432` |
| **Database** | `postgres` |
| **Username** | *[usuario de administrador suministrado en el .env]* |
| **Password** | *[Contraseña de administrador suministrada en el .env]* |

> [!NOTE]
> Se recomienda dejar desmarcada la opción **"Show all databases"** para que el explorador de DBeaver cargue de forma más rápida.

---

### Paso 3: Configurar la Seguridad SSL (Pestaña "SSL")
Azure Database for PostgreSQL obliga a realizar conexiones encriptadas. Para configurar el cifrado en DBeaver:

1. En la parte superior de la ventana de configuración, haz clic en la pestaña **SSL** (situada a la derecha de la pestaña *Main*).
2. Marca la casilla **"Use SSL"** abajo en la parte Advanced (se activará el check).
3. En el menú desplegable **SSL mode**, selecciona la opción **`require`**.
4. Deja los demás campos (como certificados raíz, cliente, etc.) completamente vacíos. Azure realiza la autenticación segura sin necesidad de archivos locales adicionales en este modo.

---

### Paso 4: Probar la Conexión y Descargar Controladores
1. En la parte inferior izquierda de la ventana, haz clic en el botón **Test Connection** (Probar conexión).
2. Si DBeaver te indica que necesita el controlador de PostgreSQL:
   - Aparecerá una pequeña ventana flotante indicando los archivos a descargar.
   - Haz clic en el botón **Download** (Descargar). DBeaver descargará e instalará el driver automáticamente en unos segundos.
3. Una vez completado, verás una ventana de confirmación indicando el estado **Connected** (Conectado) junto a la versión de la base de datos de Azure. Haz clic en **OK**.
4. Haz clic en el botón **Finalizar** (Finish) abajo a la derecha de la ventana principal para guardar la conexión en tu lista.

---

## Exploración de Esquemas del TFM
Una vez guardada la conexión, haz doble clic sobre ella en el panel de navegación izquierdo de DBeaver. Al desplegarla, dentro de **postgres** y luego en la opción **Schemas**, podrás acceder a:
* **`silver`**: Contiene las tablas limpias de transporte, límites de municipios y zonas turísticas de Tenerife.
* **`gold`**: El esquema destinado a las tablas finales de KPIs e indicadores.
