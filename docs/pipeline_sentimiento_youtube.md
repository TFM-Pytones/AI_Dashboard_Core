# Pipeline de percepción turística: YouTube + Análisis de Sentimiento

Documento explicativo del trabajo hecho en el **PR #40** (`Feat/Integracion-API-Youtube → main`),
que cerró los issues **#13**, **#16** y **#17**. Explica qué es cada pieza, por qué se construyó
así, y qué se obtuvo con datos reales — pensado como referencia tanto para el equipo como para
la memoria del TFM.

---

## 1. Contexto: por qué existen estos tres issues

El proyecto necesita medir la **percepción turística** de Tenerife: qué opina la gente, dónde
hay saturación, qué zonas están infrautilizadas. Para eso hace falta texto real escrito por
personas hablando de la isla — reseñas, comentarios, publicaciones en foros — y después un
proceso que convierta ese texto en datos estructurados (positivo/negativo, temas, ubicación).

Ese objetivo se parte en tres fases, que son los tres issues de este PR:

| Issue | Nombre | Qué resuelve |
|---|---|---|
| **#13** | Integración APIs de Google y YouTube | **Conseguir el texto**: ir a buscar comentarios reales sobre Tenerife en una fuente externa. |
| **#16** | Setup Entorno Hugging Face y Modelos | **Preparar la herramienta de análisis**: montar el entorno de IA que va a "leer" ese texto y decidir si es positivo o negativo. |
| **#17** | Inferencia de Sentimiento por Lotes | **Aplicar la herramienta a todo el texto**: correr el análisis sobre todos los comentarios conseguidos, no solo una muestra, y guardar el resultado. |

En una frase: **#13 trae los datos, #16 prepara el modelo, #17 los junta y produce el resultado final.**

---

## 2. Issue #13 — Por qué YouTube (y por qué no Google Reviews)

El issue original pedía dos fuentes: reseñas de Google y comentarios de YouTube. Se investigó
el coste de cada una antes de tocar código:

- **Google Reviews** sale de la API de **Google Places** (concretamente "Place Details"), y
  solo el nivel que incluye reseñas (**Enterprise + Atmosphere**) las trae. Ese nivel exige
  tener una **cuenta de facturación de Google Cloud con tarjeta** vinculada (aunque no se llegue
  a gastar), y solo da **1.000 peticiones gratis al mes** — muy poco margen para un proyecto que
  quiere consultar muchos sitios turísticos.
- **YouTube Data API v3** es gratuita de verdad: **no pide tarjeta**, y da 10.000 unidades de
  cuota gratis al día.

Decisión: se descartó la parte de Google Reviews. El mismo tipo de dato (opiniones/reseñas) ya
lo van a cubrir, sin coste, los issues **#12** (scraping de TripAdvisor/Booking) y **#14**
(Reddit) — así que no se pierde cobertura, solo se evita la fricción y el riesgo de coste.

### Cómo funciona `ingestion/scraping/youtube.py`

1. **Busca vídeos** relacionados con turismo en Tenerife usando 4 frases de búsqueda distintas
   ("Tenerife turismo", "Tenerife travel", "visitar Tenerife", "Tenerife vacaciones") — así se
   cubren ángulos distintos (turistas hispanohablantes, anglosajones, gente que ya fue, gente
   planeando el viaje).
2. Para cada vídeo encontrado, **descarga todos sus comentarios** (hasta 300 por vídeo,
   paginando de 100 en 100).
3. Guarda todo en la base de datos, en dos tablas:
   - `raw_data.youtube_videos`: qué vídeo es, de qué canal, cuántas visitas tiene.
   - `raw_data.youtube_comments`: el texto de cada comentario, quién lo escribió, cuántos "me
     gusta" tiene.
4. Está hecho para poder **relanzarse sin miedo**: si un comentario ya está guardado, no lo
   duplica, solo actualiza lo que haga falta (esto se llama *upsert* — "update or insert").

### Qué se sacó de ahí (dato real, no simulado)

Ejecutando el script una vez con una API key real:

- **41 vídeos únicos** encontrados sobre Tenerife.
- **3.100 comentarios únicos** descargados de esos vídeos.
- Desglose por término de búsqueda:

  | Término | Vídeos | Comentarios |
  |---|---|---|
  | Tenerife turismo | 15 | 1.883 |
  | Tenerife travel | 14 | 599 |
  | Tenerife vacaciones | 6 | 316 |
  | visitar Tenerife | 6 | 302 |

- Ejemplo real de lo que hay guardado: comentarios como *"Que playas tan feas con esa arena
  negra"* o *"Vivi en esa Isla preciosa por muchos años"* — opiniones genuinas, sin filtrar ni
  moderar, tal cual las escribió la gente.

En este punto, todavía es **texto en bruto**: la base de datos sabe que existe el comentario,
pero no sabe si es positivo o negativo. Para eso hacen falta los issues #16 y #17.

---

## 3. Issue #16 — Qué es Hugging Face y por qué hace falta

### El problema que resuelve

Un ordenador no entiende español ni sabe si una frase como *"qué asco de playa"* es negativa
por sí solo — hace falta un **modelo de lenguaje entrenado específicamente para eso** (un tipo
de Inteligencia Artificial llamado *modelo de clasificación de sentimiento*). Entrenar uno desde
cero requeriría millones de frases ya etiquetadas y muchísima potencia de cálculo — algo
inviable para un TFM.

**Hugging Face** es una plataforma (como un "GitHub de modelos de IA") donde miles de
organizaciones publican modelos ya entrenados, gratis y listos para usar. En vez de entrenar
uno propio, el proyecto **descarga uno ya hecho** y lo usa directamente.

### El modelo elegido: `cardiffnlp/twitter-xlm-roberta-base-sentiment`

- Es **multilingüe**: entiende español, inglés, y varios idiomas más sin necesitar un modelo
  distinto por idioma — importante porque los comentarios de YouTube vienen mezclados.
- Está entrenado específicamente con **texto de redes sociales** (tuits) — es decir, con
  frases cortas, informales, con faltas, emojis y jerga. Es exactamente el mismo tipo de texto
  que hay en los comentarios de YouTube, a diferencia de un modelo entrenado con reseñas largas
  y formales.
- Da como resultado una de estas tres etiquetas por cada texto: **positive**, **neutral** o
  **negative**, junto a un "score" (0 a 1) que indica cuánta confianza tiene el modelo en su
  propia predicción.
- Es público y gratuito: se descarga una vez (~1.1GB) y se queda guardado en el ordenador — no
  hace falta ni API key ni conexión a internet para usarlo después de la primera vez.

### Qué se construyó en el #16 (`analytics/sentiment/setup_test.py`)

No es el análisis final — es una **prueba de que toda la cadena funciona**, antes de lanzarla
sobre miles de comentarios. Hace esto:

```
Base de datos (5 comentarios reales al azar) → modelo de Hugging Face → predicción impresa en pantalla
```

Sirvió para comprobar, con datos reales, que: la conexión a la base de datos funciona, el
modelo se descarga y carga bien, y las predicciones tienen sentido (por ejemplo, un comentario
agradeciendo el vídeo salió como `positive` con 0.90 de confianza — un 90%).

Detalle técnico interesante: el ordenador de desarrollo (Mac con chip Apple Silicon) usó su GPU
automáticamente (`mps`) para acelerar el cálculo, sin tener que configurar nada — la misma
librería (`transformers`) detecta sola el mejor hardware disponible.

---

## 4. Issue #17 — Qué es la "inferencia de sentimiento por lotes"

### Qué significa "inferencia"

**Inferencia** es el término técnico para "usar un modelo de IA ya entrenado para hacer una
predicción sobre un dato nuevo" (a diferencia de "entrenamiento", que es el proceso de construir
el modelo desde cero). Aquí, "hacer inferencia de sentimiento" sobre un comentario significa:
pasarle el texto al modelo del #16 y quedarse con la etiqueta que devuelve.

### Qué significa "por lotes" (batch)

En el #16 se probó con solo 5 comentarios, uno a uno. Pero hay **3.100** comentarios reales
guardados. Procesarlos de uno en uno sería lento. **"Por lotes"** significa agrupar varios
comentarios (aquí, de 32 en 32) y pasárselos al modelo juntos de una vez — el modelo puede
procesar un grupo en paralelo casi igual de rápido que uno solo, así que agrupar multiplica la
velocidad por muchas veces.

### Cómo funciona `analytics/sentiment/batch_inference.py`

1. **Limpieza de texto**: antes de analizar cada comentario, se le quitan las URLs (enlaces a
   páginas de reservas, por ejemplo) y los espacios sobrantes — ese tipo de texto no aporta
   información de sentimiento y solo "ensucia" la predicción. Si después de limpiar queda un
   texto demasiado corto (menos de 3 caracteres), se descarta.
2. **Procesa todo lo pendiente**: mira qué comentarios de `raw_data.youtube_comments` todavía no
   tienen un resultado guardado, y solo analiza esos — así, si se ejecuta otra vez en el futuro
   (por ejemplo tras traer más comentarios nuevos con el script del #13), no repite trabajo ya
   hecho.
3. **Guarda el resultado** en una tabla nueva: `processed_data.sentiment_results`, con: de qué
   fuente viene, el texto usado, la etiqueta (positive/neutral/negative), el score de confianza,
   y qué modelo se usó. Esta tabla está diseñada para servir también cuando lleguen los
   comentarios de Reddit (#14) o las reseñas de TripAdvisor (#12) — no hay que crear una tabla
   nueva por cada fuente, todas caben en la misma.

### Resultado real (dato real, no simulado)

De los 3.100 comentarios, **3.071 se procesaron** (29 quedaron vacíos tras limpiar URLs y se
descartaron, no aportaban texto útil):

| Sentimiento | Cantidad | Score medio de confianza |
|---|---|---|
| Positivo | 1.198 (39%) | 0.78 |
| Negativo | 996 (32%) | 0.77 |
| Neutro | 877 (28%) | 0.62 |

Ejemplo de predicción con alta confianza real: el comentario *"Así está quedando benidorm un
auténtico asco"* se clasificó como `negative` con 0.97 de confianza (97%).

Se comprobó también que el script es **verdaderamente incremental**: al volver a ejecutarlo
justo después, detectó que no había nada nuevo que procesar y terminó en menos de 5 segundos,
sin siquiera cargar el modelo de IA (optimización añadida tras detectar que lo cargaba de más).

---

## 5. Cómo encaja esto en el proyecto completo

```
ingestion/scraping/youtube.py   (Issue #13)
        │  guarda texto en bruto
        ▼
raw_data.youtube_comments
        │
        ▼
analytics/sentiment/batch_inference.py   (Issue #17, usa el modelo montado en el #16)
        │  guarda resultado clasificado
        ▼
processed_data.sentiment_results
        │
        ▼
   (pendiente) frontend "Análisis de sentimiento"
```

Ahora mismo el módulo de "Análisis de sentimiento" del dashboard (`frontend/`) todavía usa datos
**simulados** (`frontend/lib/mock-data.ts`) para poder enseñar el diseño sin esperar al backend.
El siguiente paso lógico es conectar ese módulo a `processed_data.sentiment_results`, para que
muestre los 3.071 resultados reales en vez de los inventados.

## 6. Qué queda pendiente (siguientes issues)

- **#18 — Extracción de Aspectos (pyabsa)**: no solo saber si un comentario es positivo o
  negativo, sino **sobre qué** opina (playas, precios, masificación, transporte...).
- **#19 — Modelado de Tópicos (BERTopic)**: agrupar automáticamente los 3.071 comentarios por
  temas recurrentes, sin tener que definirlos a mano.
- **#20 — Georreferenciación de Tópicos y Sentimientos**: cruzar estos resultados con ubicación
  geográfica, para poder verlos en el módulo de Mapa del dashboard.

Ambos (#18 y #19) pueden partir directamente de `processed_data.sentiment_results`, que ya tiene
el texto limpio y evita repetir el trabajo de limpieza.

## 7. Coste total de todo este pipeline

**Cero.** Ni la API de YouTube ni el modelo de Hugging Face requieren pago ni tarjeta de crédito
vinculada en ningún momento. El único "coste" es tiempo de cómputo en el propio ordenador (unos
minutos) y espacio en disco (~1.1GB para el modelo, descargado una sola vez).
