# Bloque 2 (NLP sentimiento/aspectos) — adaptación para Google Colab

**Esto es una adaptación para correr en Google Colab del trabajo original de Guille
en [`analytics/tarea2/`](../../tarea2/) — NO es un reemplazo.** El original queda
intacto como referencia y por si Guille vuelve a tocarlo. Esta carpeta existe para
poder correr el Bloque 2 en paralelo (en Colab, con GPU) mientras el Bloque 5
(MGWR/PTNA) se sigue trabajando en otra máquina.

Contexto completo del porqué de esta tarea (bloqueante de `sentimiento_medio` para
el Bloque 5): `analytics/mgwr/docs/contexto_maestro_proyecto_ptna.md`, sección 6.

## Qué hay acá

```
analytics/tarea2_colab/
  notebooks/
    nlp_sentimiento_2_1.ipynb        -- copia adaptada de tarea2/nlp_sentimiento_2_1.ipynb
    nlp_aspectos_tarea_2_2.ipynb     -- copia adaptada de tarea2/nlp_aspectos_tarea_2_2.ipynb
    traducir_aspectos.ipynb          -- copia adaptada de tarea2/traducir_aspectos.ipynb
    cruce_nlp_hexagono_h3.sql        -- copia CORREGIDA de tarea2/cruce_nlp_hexagono_h3.sql
  docs/
    README.md                        -- este archivo
```

Los 3 notebooks tienen sus outputs de celda limpios a propósito (la versión original
en `tarea2/` tenía outputs de una corrida previa que un diagnóstico de código
encontró contradictorios con las notas de los propios notebooks — ver
"Diagnóstico previo" más abajo). Se van a generar outputs nuevos y reales la
primera vez que corran en Colab.

## Orden de ejecución

Según las dependencias reales verificadas en el código (no según el orden de los
tickets):

1. **`nlp_sentimiento_2_1.ipynb`** y **`nlp_aspectos_tarea_2_2.ipynb`** — pueden
   correr en cualquier orden, o en paralelo (dos notebooks de Colab abiertos a la
   vez). Ninguno depende del otro: los dos leen directo de
   `silver.tripadvisor_resenas` / `silver.silver_booking_reviews`, no de la tabla
   que crea el otro.
2. **`traducir_aspectos.ipynb`** — depende de que **2.2 ya haya corrido** y poblado
   `gold.nlp_aspectos_resenas` (su Paso 3 lee de ahí). No depende de 2.1.
3. **`cruce_nlp_hexagono_h3.sql`** — depende de **2.1 y 2.2** (hace `LEFT JOIN`
   contra ambas tablas), y ahora también de **`traducir_aspectos.ipynb`** para que
   `gold.aspecto_traducciones` tenga contenido real (ver el bug corregido, abajo) —
   aunque al ser `LEFT JOIN`, corre igual sin eso, solo que `queja_principal` va a
   salir mayormente `NULL` hasta que la tabla de traducciones tenga datos.

```
2.1 ──┐
      ├──► cruce_nlp_hexagono_h3.sql
2.2 ──┴──► traducir_aspectos.ipynb ──┘
```

## Secrets a configurar en Colab (antes de correr cualquier notebook)

Panel izquierdo → ícono de llave (🔑) → agregar estos 4 secrets con los mismos
valores que tiene el `.env` del repo, y activar el toggle de acceso del notebook
para cada uno:

- `AZURE_DB_HOST`
- `AZURE_DB_USER`
- `AZURE_DB_PASSWORD`
- `AZURE_DB_NAME`

El puerto (`5432`) queda fijo en el código, igual que en `analytics/mgwr/scripts/_db.py`
— no hay secret separado para eso. Los notebooks originales usaban un único
`AZURE_DB_URL` (string de conexión completo) leído del `.env` local; acá se
reconstruye esa misma URL a partir de los 4 secrets de arriba, porque Colab no
tiene filesystem persistente para un `.env`.

## GPU / Drive por notebook

| Notebook | ¿Necesita GPU? | ¿Necesita Google Drive montado? |
|---|---|---|
| `nlp_sentimiento_2_1.ipynb` | Recomendado (si no, ~horas en CPU) | No |
| `nlp_aspectos_tarea_2_2.ipynb` | Recomendado (PyABSA es más pesado) | **Sí** — el checkpoint de PyABSA pesa varios cientos de MB; sin Drive se vuelve a descargar en cada sesión nueva de Colab porque `/content/` es efímero |
| `traducir_aspectos.ipynb` | No (traducción de texto, sin modelos) | No |

Cada notebook tiene una celda "Paso 0" al principio que deja esto listo (pip
install puntual de las dependencias necesarias — no `requirements.txt` completo,
mismo criterio que ya usa el equipo en la VM del proyecto — y, en el caso de 2.2,
el `drive.mount()`).

## Pasos manuales que quedan

- **Ninguno relacionado a rutas de disco** — el ajuste manual que pedía el
  notebook original de 2.2 ("Ajusta la ruta `D:/huggingface_cache` a tu disco
  externo real si no es `D:`") ya no aplica: las rutas ahora son fijas
  (`/content/drive/MyDrive/tfm_tenerife/...`) porque todos los que corran esto en
  Colab montan Drive de la misma forma.
- **Sigue siendo manual** (por diseño, no es una limitación de esta adaptación):
  en `nlp_aspectos_tarea_2_2.ipynb`, el Paso 5 corre PyABSA sobre 2 frases de
  prueba y pide revisar a ojo que los campos devueltos sean `aspect`/`sentiment`/
  `confidence` antes de seguir al Paso 7. Si PyABSA cambió de formato, el Paso 7
  ahora **sí avisa con un mensaje explícito** (ver "Cambios de robustez" abajo) en
  vez de fallar en silencio, pero la revisión manual del Paso 5 sigue siendo la
  primera línea de defensa.
- **`traducir_aspectos.ipynb`, Paso 3b**: sigue siendo una celda condicional,
  separada del resto del flujo — correrla solo si ya lanzaste el Paso 4 antes y
  sospechás que se guardaron traducciones contaminadas (páginas de error de
  Google Translate guardadas como si fueran traducciones válidas). Si es tu
  primera corrida, saltala.

## Cambios respecto al original (además de rutas y secrets)

- **Bug corregido en `cruce_nlp_hexagono_h3.sql`**: la query original referenciaba
  `a.aspecto_normalizado`, una columna que no existe en ningún `CREATE TABLE` real
  del proyecto (hallazgo del diagnóstico de código de `analytics/tarea2/`). Se
  agregó el `LEFT JOIN gold.aspecto_traducciones` que faltaba y se usa
  `t.aspecto_traducido`, que es la columna que sí existe (creada por
  `traducir_aspectos.ipynb`). Documentado con comentarios en el propio archivo.
- **`nlp_aspectos_tarea_2_2.ipynb`, `parsear_resultado`**: antes, si PyABSA
  cambiaba el nombre de un campo (`aspect`/`sentiment`/`confidence`), el código
  hacía `.get(campo, [])` y devolvía una lista vacía en silencio — cada reseña
  quedaba marcada como "sin aspecto detectado" sin ningún aviso. Ahora se imprime
  un warning explícito (una sola vez por ejecución, no una vez por fila) si falta
  alguno de esos campos.
- **`nlp_aspectos_tarea_2_2.ipynb`, chequeo de versión de torch**: el aviso de
  "torch desactualizado" seguía sin detener la ejecución (a propósito, eso no
  cambió), pero ahora está enmarcado entre líneas de `!!!` para que no se pierda
  entre el resto del output de la celda.

## Diagnóstico previo (contexto, no repetido acá)

Ya existe un diagnóstico de código completo sobre `analytics/tarea2/` (sesión
anterior) con estos hallazgos, que esta adaptación tiene en cuenta:

- Ruta hardcodeada `D:/huggingface_cache` / `D:/pyabsa_trabajo` en 2.2 → resuelto acá con Google Drive.
- Bug de `a.aspecto_normalizado` en la SQL → corregido acá (ver arriba).
- Fallo silencioso en `parsear_resultado` si PyABSA cambia de formato → endurecido acá (ver arriba).
- Sin credenciales embebidas en texto plano en ningún notebook (confirmado, se mantiene así acá con Colab secrets).
- Los outputs de celda de la versión original de `tarea2/` son contradictorios
  con las notas en texto de los propios notebooks (ej. un notebook dice "no he
  podido probar esto" pero tiene una celda de reparación para un bug muy
  específico que solo se ve en ejecución real) — y ninguna de las 3 tablas que
  estos notebooks dicen crear (`gold.nlp_sentimiento_resenas`,
  `gold.nlp_aspectos_resenas`, `gold.aspecto_traducciones`) existe hoy en la base
  real (verificado contra `information_schema`, solo `SELECT`, en la sesión que
  armó esta carpeta). Es decir: el Bloque 2 arranca de cero en la práctica,
  más allá de lo que sugieran los outputs guardados en `tarea2/`.

## Discrepancias entre el plan (`plan_final_mejorado.md`, Bloque 2) y el código real

No estaban en el diagnóstico anterior (que comparaba el código contra sí mismo,
no contra el plan):

- El plan (Subtarea 2.3) da un SQL de referencia que usa **`a.aspecto` directo**
  (sin ninguna normalización/traducción) para `queja_principal`, y no menciona en
  ningún lado un paso de traducción. Es decir: **`traducir_aspectos.ipynb` y todo
  el concepto de `aspecto_normalizado`/`aspecto_traducido` son un agregado de
  Guille, no algo pedido por el ticket**. Tiene sentido igual — el SQL del plan,
  usado literal, mezclaría aspectos en distintos idiomas sin agrupar
  (`"location"`/`"ubicación"`/`"posizione"` como conceptos distintos) porque
  PyABSA multilingüe devuelve el aspecto en el idioma original de la reseña — pero
  vale la pena que quien revise esto con el PM sepa que es scope agregado, no del
  ticket original.
- El plan pide como output de 2.1 solo `resena_id, hotel_id, score`; el código
  real agrega `h3_index` y `fuente`. Mismo caso en 2.2: el plan pide
  `resena_id, aspecto, sentimiento`; el código real agrega `hotel_id`, `confianza`
  y `fuente`. Guille documenta estas dos desviaciones en las notas de sus propios
  notebooks (ya señalado ahí, no es nuevo, pero el plan lo confirma en blanco y
  negro).
- El plan lista `["precio", "limpieza", "ubicacion", "transporte", "naturaleza", "servicio", "ruido"]`
  como aspectos "a detectar", pero el propio plan aclara que es orientativo, no
  una restricción ("los aspectos son detectados automáticamente... no hace falta
  definirlos a mano") — coincide con la decisión de Guille de no filtrar nada.
  No es una discrepancia real, solo confirmación de que el código sigue el plan
  en este punto.
- El plan filtra por `WHERE anio > 2021` sobre columnas genéricas que no existen
  (`silver.booking_reviews`, `silver.tripadvisor_resenas` con una columna `anio`);
  el código real usa `EXTRACT(YEAR FROM r.fecha_publicacion)` / `EXTRACT(YEAR FROM b.review_date)`
  sobre los nombres reales de columna. Mismo criterio de filtrado, nombres
  corregidos — consistente con lo que el propio archivo `.sql` ya documentaba
  sobre nombres genéricos del ticket.
