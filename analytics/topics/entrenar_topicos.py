"""Reentrenamiento local de los temas (modelo A: general, modelo B: geo), sin
Colab ni GPU.

Cambios frente a la version entrenada en Colab (topic_modeling_*_colab.ipynb),
medidos sobre el corpus real:

1. Reutiliza los embeddings de gold.nlp_chunks (mismo modelo,
   paraphrase-multilingual-mpnet-base-v2): un documento = media normalizada de
   sus fragmentos. Solo se recalculan en CPU las reseñas de Booking cuyo titulo
   es la categoria automatica de la nota (unas 31.000; ~20 min la primera vez,
   despues quedan en cache).

2. Quita ese titulo ("Excepcional", "Fantástico"...). Booking lo pone segun la
   nota (Excepcional = 10, Fantástico = 9, ... Pésimo = 1): no aporta nada que
   no este ya en `rating` y empujaba a agrupar por nota.

3. Centra los embeddings por idioma (resta la media de cada idioma) antes de
   agrupar. El modelo multilingue conserva una componente de idioma y la
   version anterior tenia temas enteros en aleman o neerlandes. Dependencia
   entre tema e idioma (NMI): 0,218 antes; 0,031 despues.

4. K-means sobre PCA de 50 dimensiones en lugar de UMAP + HDBSCAN. HDBSCAN dejo
   sin tema al 76,8 % del modelo B, que despues se reasigno por palabras (la
   silueta de ese resultado era negativa, -0,195); con k-means cada documento va
   al centro mas cercano y el numero de temas es manejable para un mapa. UMAP y
   hdbscan, ademas, no se pueden importar en esta maquina (Smart App Control).

5. Nombre legible en español por tema, generado con el LLM (Groq) a partir de
   sus palabras clave, sus textos mas centrales y otros al azar, y la nota media
   del tema. Solo con los centrales, un tema de reseñas breves y variadas salio
   como "Valoracion de ubicacion"; sin la nota, un tema de camas comodas (nota
   8,9) salio como "Camas poco confortables". `topic_label` pasa a ser ese
   nombre y las palabras de c-TF-IDF van a `topic_keywords`.

`probability` pasa a ser la similitud coseno entre el documento y el centro de
su tema. El texto de gold.nlp_topics no se modifica: el titulo solo se quita
para entrenar, asi los fragmentos del RAG y sus embeddings siguen valiendo.

Uso:
    python analytics/topics/entrenar_topicos.py
    python analytics/topics/entrenar_topicos.py --sin-llm         # nombres = palabras clave
    python analytics/topics/entrenar_topicos.py --solo-renombrar  # aplica NOMBRES_REVISADOS sin reentrenar
Despues:
    python analytics/topics/volcar_topicos.py
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import psycopg2
from dotenv import load_dotenv

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "llm"))

from idioma import detectar  # noqa: E402

load_dotenv(override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
MODELOS = {
    "A": {"model_name": f"BERTopic+{EMBEDDING_MODEL_NAME} (modelo A: general)", "k": 20, "min_df": 2,
          "descripcion": "comentarios de YouTube y mensajes de un foro de viajes sin ubicacion concreta"},
    "B": {"model_name": f"BERTopic+{EMBEDDING_MODEL_NAME} (modelo B: geo)", "k": 50, "min_df": 5,
          "descripcion": "reseñas de alojamientos de Booking y TripAdvisor y mensajes de foro sobre lugares concretos"},
}
DIMENSIONES_PCA = 50
SEMILLA = 42
MIN_DOCS_IDIOMA = 30        # idiomas con menos documentos se centran con la media global
TEMAS_POR_LLAMADA = 10

# Nombres revisados a mano tras contrastar cada tema con su nota media y con
# ejemplos al azar (14-09-2026). Cada correccion exige que el tema conserve una
# palabra clave: si al reentrenar cambia la numeracion, no se aplica a otro tema
# y se avisa.
NOMBRES_REVISADOS = {
    ("A", 19): ("página", "Restos de paginación del foro"),
    ("B", 5): ("teide", "Visita al Teide"),
    ("B", 6): ("complex", "Valoración del apartamento y el complejo"),
    ("B", 13): ("room", "Relatos detallados de la estancia"),
    ("B", 18): ("restaurants", "Ubicación céntrica con servicios cerca"),
    ("B", 24): ("cocina", "Equipamiento de la cocina"),
    ("B", 31): ("ducha", "Baño y ducha"),
    ("B", 33): ("aparcamiento", "Aparcamiento y coche"),
    ("B", 40): ("encantó", "Experiencia muy positiva"),
}

EXPORT = AQUI / "export"
CACHE_SIN_TITULO = EXPORT / "embeddings_booking_sin_titulo.npz"
RESULTADOS_CSV = EXPORT / "topicos_v2_resultados.csv"
TEMAS_JSON = EXPORT / "topicos_v2_temas.json"
DIR_MODELOS = EXPORT / "modelos_v2"

# Categorias que Booking pone como titulo segun la nota (verificado contra
# `rating`: cada una corresponde a una nota exacta). Los titulos escritos por el
# cliente ("Excelente", "Perfect"...) se conservan.
TITULOS_NOTA = {"Excepcional", "Fantástico", "Muy bien", "Bien", "Agradable", "Aceptable",
                "Decepcionante", "Mal", "Muy mal", "Pésimo"}

# Palabras vacias por idioma para las palabras clave (c-TF-IDF). Sin ellas las
# etiquetas salen "de, que, la" o "het, een, op" en lugar de contenido.
_STOP = {
    "es": "de la que el en y a los del se las por un para con no una su al lo como mas más pero sus le ya o este si sí "
          "porque esta entre cuando muy sin sobre tambien también me hasta hay donde dónde quien quién desde todo nos "
          "durante todos uno les ni contra otros ese eso ante ellos e esto mi antes algunos unos yo otro otras otra "
          "tanto esa estos mucho quienes nada muchos cual cuál poco ella estar estas algunas algo nosotros mis tu tú "
          "te ti tus ellas nosotras vosotros vosotras os mio mío mia mía tuyo tuya suyo suya es soy eres somos sois "
          "son esté estan están fue ser voy vamos va van puede pueden hace hacer gracias hola saludos pues asi así "
          "aqui aquí alli allí ahi ahí estaba estaban había era eran tiene tienen tenía",
    "de": "der die das und ist war für mit auf sich dem den des ein eine einen einem einer nicht auch aber wie wir ich "
          "du er sie es was wenn dass so noch nur sehr hier sind hat haben wird kann mehr viel alle aus bei nach vor "
          "über unter zwischen um an in im zu zum zur uns euch ihr ihre sein seine diese dieser dieses man waren "
          "wurde werden",
    "it": "il lo la i gli le di a da in con su per tra fra un uno una che non come più anche molto questo questa "
          "questi queste sono era è ha hanno siamo essere avere del della dei delle al alla allo nel nella dal dalla "
          "ma se perché quando dove chi cosa ci si tutto",
    "fr": "le la les de un une du des et à est il elle ils elles on nous vous je tu que qui pour dans avec sur par ce "
          "cette ces se son sa ses ne pas plus très aussi mais ou où comme tout tous toutes être avoir fait sont "
          "était été",
    "pt": "o a os as de do da dos das um uma e é foi ser para com não mais muito mas ou quando onde que se este esta "
          "esses essas isso aqui também já ainda só como sua seu suas seus nos na no em por",
    "ru": "и в не на я быть он с что а по это она этот к но они мы как из у который то за свой весь год от так о для "
          "ты же все тот вы если уже или ни бы себя под будет был была было были есть очень чтобы при без",
    "nl": "de het een en is was zijn niet van op te dat die in voor met er maar ook als aan bij om zo nog wel we wij "
          "ons onze je u ze hij zij heel erg zeer dan of naar uit tot door over kan kunnen hebben heeft had werd",
    "pl": "i w na z do się to że jest było był nie a o ale jak po od za dla tak już co są być bardzo też tylko przez "
          "we ze mi nas my czy jego jej ich",
    "cs": "a je byl bylo byla se na v ve to že s z do o i ale jako po pro by jsme jsou velmi také jen už nás my",
    "ro": "și în la cu de pe a o un este fost era nu foarte pentru care mai din sau am au ne se că ca",
    "hu": "a az és hogy nem is egy volt nagyon de van csak meg már mint el ki be fel még minden ez azt",
    "sc": "og i er var det en et på med til ikke inte jeg vi som for av af de den har hade meget veldig mycket også "
          "också men så",
    # Sin estos, un tema de reseñas breves en varios idiomas salia con palabras
    # clave islandesas ("að, við, ekki") solo porque eran las mas distintivas.
    "fi": "ja on oli ei se että mutta myös kun ole olla olivat meille me minä sinä hän he tämä tuo niin kuin vain",
    "et": "ja on oli ei see et aga ka kui meil me mina sina tema nad seda väga",
    "lt": "ir yra buvo ne tai kad bet taip pat kai mums mes aš tu jis ji jie labai",
    "lv": "un ir bija nav tas ka bet arī kad mums mēs es tu viņš viņa viņi ļoti",
    "is": "og er var ekki það að við en líka þegar okkur ég þú hann hún þeir mjög sem á í um",
}
# Aparecen en casi todas las reseñas de alojamiento y no distinguen ningun tema.
STOP_ALOJAMIENTO = {"hotel", "habitacion", "habitación", "noche", "noches", "estancia"}


def palabras_vacias(clave: str) -> list[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    todas = set(ENGLISH_STOP_WORDS)
    for lista in _STOP.values():
        todas.update(lista.split())
    if clave == "B":
        todas |= STOP_ALOJAMIENTO
    return sorted(todas)


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("AZURE_DB_USER"),
        password=os.getenv("AZURE_DB_PASSWORD"),
        host=os.getenv("AZURE_DB_HOST"),
        database=os.getenv("AZURE_DB_NAME"),
        port="5432",
        sslmode="require",
    )


def texto_para_temas(source: str, text: str) -> str:
    if source == "booking_review":
        partes = text.split(" | ")
        if len(partes) > 1 and partes[0].strip() in TITULOS_NOTA:
            return " | ".join(partes[1:]).strip()
    return text


def cargar_corpus(conn) -> tuple[list[tuple], np.ndarray, np.ndarray]:
    """El corpus es el de gold.nlp_topics (lo definieron export_*_corpus.py), el
    embedding de cada documento (media normalizada de sus fragmentos) y su nota
    (NaN en foro y YouTube)."""
    with conn.cursor() as cur:
        cur.execute("SELECT source, source_id, text, model_name FROM gold.nlp_topics ORDER BY source, source_id")
        docs = cur.fetchall()
    indice = {(s, sid): i for i, (s, sid, _, _) in enumerate(docs)}
    emb = np.zeros((len(docs), 768), dtype=np.float32)
    n = np.zeros(len(docs), dtype=np.int32)
    notas = np.full(len(docs), np.nan, dtype=np.float32)
    with conn.cursor(name="embeddings") as cur:
        cur.itersize = 2000
        cur.execute("SELECT source, source_id, embedding::text, rating FROM gold.nlp_chunks WHERE embedding IS NOT NULL")
        for s, sid, vector, nota in cur:
            i = indice.get((s, sid))
            if i is not None:
                emb[i] += np.array(vector[1:-1].split(","), dtype=np.float32)
                n[i] += 1
                if nota is not None:
                    notas[i] = nota
    if (n == 0).any():
        raise SystemExit(f"{int((n == 0).sum())} documentos sin embedding en gold.nlp_chunks: "
                         "ejecuta antes analytics/rag/build_chunks.py e import_embeddings.py")
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    return docs, emb, notas


def aplicar_embeddings_sin_titulo(docs, textos, emb) -> int:
    """Sustituye el embedding de las reseñas a las que se ha quitado el titulo
    de la nota. Cache por source_id (solo reseñas de Booking, que no repiten id)."""
    pendientes = [i for i, d in enumerate(docs) if textos[i] != d[2]]
    cache: dict[str, np.ndarray] = {}
    if CACHE_SIN_TITULO.exists():
        z = np.load(CACHE_SIN_TITULO)
        cache = dict(zip(z["source_id"].tolist(), z["emb"]))
    faltan = [i for i in pendientes if docs[i][1] not in cache]
    if faltan:
        print(f"Calculando {len(faltan)} embeddings sin titulo en CPU (queda en cache)...", flush=True)
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(os.cpu_count() or 8)
        modelo = SentenceTransformer(EMBEDDING_MODEL_NAME)
        nuevos = modelo.encode([textos[i] for i in faltan], batch_size=64,
                               normalize_embeddings=True, show_progress_bar=True)
        for i, vector in zip(faltan, nuevos):
            cache[docs[i][1]] = vector.astype(np.float32)
        ids = list(cache)
        EXPORT.mkdir(parents=True, exist_ok=True)
        np.savez(CACHE_SIN_TITULO, source_id=np.array(ids), emb=np.stack([cache[k] for k in ids]))
    for i in pendientes:
        emb[i] = cache[docs[i][1]]
    return len(pendientes)


def centrar_por_idioma(emb: np.ndarray, idiomas: np.ndarray) -> tuple[np.ndarray, dict]:
    X = emb.copy()
    media_global = X.mean(axis=0)
    medias = {"_global": media_global}
    for lengua, n in Counter(idiomas.tolist()).items():
        sel = idiomas == lengua
        if n >= MIN_DOCS_IDIOMA and lengua != "unk":
            medias[lengua] = X[sel].mean(axis=0)
            X[sel] -= medias[lengua]
        else:
            X[sel] -= media_global
    return X / np.linalg.norm(X, axis=1, keepdims=True), medias


def entrenar(clave: str, textos: list[str], X: np.ndarray):
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.feature_extraction.text import CountVectorizer

    conf = MODELOS[clave]
    modelo = BERTopic(
        embedding_model=EMBEDDING_MODEL_NAME,
        umap_model=PCA(n_components=DIMENSIONES_PCA, random_state=SEMILLA),
        hdbscan_model=KMeans(n_clusters=conf["k"], n_init=10, random_state=SEMILLA),
        vectorizer_model=CountVectorizer(stop_words=palabras_vacias(clave), ngram_range=(1, 2), min_df=conf["min_df"]),
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        top_n_words=10,
        language="multilingual",
        calculate_probabilities=False,
    )
    temas, _ = modelo.fit_transform(textos, embeddings=X)
    temas = np.asarray(temas)
    centros = np.stack([X[temas == t].mean(axis=0) for t in range(conf["k"])])
    centros /= np.linalg.norm(centros, axis=1, keepdims=True)
    confianza = np.einsum("ij,ij->i", X, centros[temas])
    return modelo, temas, confianza


PROMPT_NOMBRES = """Eres analista de turismo. Te doy temas detectados automaticamente en {descripcion} sobre Tenerife. De cada tema tienes cuantos textos tiene, su nota media (de 1 a 10, cuando la hay), en que idiomas estan, sus palabras clave y ocho textos: los cuatro primeros son los mas centrales del tema y los otros cuatro, elegidos al azar.
{referencia}

Pon a cada tema un nombre corto en español, de 2 a 5 palabras, que diga de que habla, como lo escribiria un analista en un informe. Reglas:
- Nombra lo que tienen en comun los ocho textos, no solo los primeros.
- Nombra el asunto concreto ("Ruido nocturno", "Aparcamiento dificil", "Subida al Teide"), no una valoracion vaga.
- Si los textos son elogios o quejas sin un asunto concreto, dilo asi ("Elogios generales", "Quejas generales").
- Si son muy breves o tratan asuntos variados sin nada en comun, dilo asi ("Reseñas breves sin detalle", "Experiencias variadas").
- Las palabras clave pueden incluir palabras sueltas de idiomas minoritarios que no indican el asunto: guiate sobre todo por los textos.
- Usa la nota para el tono: di "quejas", "problemas" o "deficiente" solo si la nota media del tema esta claramente por debajo de la referencia, y "elogios" o adjetivos positivos solo si esta por encima. Si el asunto aparece de pasada en reseñas buenas, usa un nombre neutro del asunto ("Aparcamiento", "Equipamiento de la cocina").
- No uses la palabra "tema", ni numeros, ni comillas.
- Todos los nombres deben ser distintos entre si y de los ya usados.
{ya_usados}
Responde SOLO con una lista JSON de objetos {{"id": <numero>, "nombre": "<nombre>"}}.

TEMAS:
{temas}
"""


def nombrar_temas(llm, clave: str, palabras: dict[int, list[str]], ejemplos: dict[int, list[str]],
                  contexto: dict[int, str], referencia: str) -> dict[int, str]:
    nombres: dict[int, str] = {}
    ids = sorted(palabras)
    for inicio in range(0, len(ids), TEMAS_POR_LLAMADA):
        lote = ids[inicio:inicio + TEMAS_POR_LLAMADA]
        bloque = "\n\n".join(
            f"[id {t}] {contexto[t]}\npalabras clave: {', '.join(palabras[t])}\n"
            + "\n".join(f"  - {e}" for e in ejemplos[t])
            for t in lote
        )
        ya_usados = f"- Nombres ya usados: {'; '.join(nombres.values())}\n" if nombres else ""
        prompt = PROMPT_NOMBRES.format(descripcion=MODELOS[clave]["descripcion"], temas=bloque,
                                       ya_usados=ya_usados, referencia=referencia)
        for intento in range(1, 5):
            try:
                respuesta = llm.complete(prompt, temperature=0.2, max_tokens=4000) or ""
                lista = json.loads(respuesta[respuesta.find("["):respuesta.rfind("]") + 1])
                nombres.update({int(o["id"]): str(o["nombre"]).strip().strip('"«»') for o in lista if int(o["id"]) in lote})
                break
            except Exception as e:  # cuota o JSON mal formado: se reintenta con espera creciente
                print(f"    lote {lote[0]}-{lote[-1]}, intento {intento}: {str(e)[:120]}", flush=True)
                time.sleep(20 * intento)
        print(f"    nombrados {len(nombres)}/{len(ids)}", flush=True)
    # Lo que no se haya podido nombrar (o nombres repetidos) cae en las palabras clave.
    vistos: set[str] = set()
    for t in ids:
        nombre = nombres.get(t) or ", ".join(palabras[t][:3])
        if nombre.lower() in vistos:
            nombre = f"{nombre} ({palabras[t][0]})"
        vistos.add(nombre.lower())
        nombres[t] = nombre
    return nombres


def aplicar_revisiones(clave: str, nombres: dict[int, str], palabras: dict[int, list[str]]) -> list[str]:
    avisos = []
    for (modelo, t), (palabra, nombre) in NOMBRES_REVISADOS.items():
        if modelo != clave or t not in nombres:
            continue
        if palabra in palabras[t]:
            nombres[t] = nombre
        else:
            avisos.append(f"modelo {modelo}, tema {t}: ya no contiene '{palabra}', revision no aplicada")
    return avisos


def renombrar_resultados():
    """Aplica NOMBRES_REVISADOS a los resultados ya generados (CSV, JSON y
    modelos guardados) sin volver a entrenar."""
    from bertopic import BERTopic

    temas = json.loads(TEMAS_JSON.read_text(encoding="utf-8"))
    for clave in MODELOS:
        nombres = {t["topic_id"]: t["nombre"] for t in temas if t["modelo"] == clave}
        palabras = {t["topic_id"]: t["palabras_clave"] for t in temas if t["modelo"] == clave}
        for aviso in aplicar_revisiones(clave, nombres, palabras):
            print(f"AVISO: {aviso}")
        for t in temas:
            if t["modelo"] == clave:
                t["nombre"] = nombres[t["topic_id"]]
        ruta = DIR_MODELOS / f"modelo_{clave}"
        modelo = BERTopic.load(str(ruta))
        modelo.set_topic_labels(nombres)
        modelo.save(str(ruta), serialization="safetensors", save_ctfidf=True, save_embedding_model=EMBEDDING_MODEL_NAME)
    TEMAS_JSON.write_text(json.dumps(temas, ensure_ascii=False, indent=2), encoding="utf-8")

    clave_de = {conf["model_name"]: clave for clave, conf in MODELOS.items()}
    nombre_de = {(t["modelo"], t["topic_id"]): t["nombre"] for t in temas}
    with open(RESULTADOS_CSV, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas, filas = lector.fieldnames, list(lector)
    for fila in filas:
        fila["topic_label"] = nombre_de[(clave_de[fila["model_name"]], int(fila["topic_id"]))]
    with open(RESULTADOS_CSV, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Nombres revisados aplicados a {RESULTADOS_CSV.name}, {TEMAS_JSON.name} y a los modelos guardados.")


def medir(nombre: str, X, temas, idiomas, titulos, fuentes):
    from sklearn.metrics import normalized_mutual_info_score as nmi, silhouette_score
    rng = np.random.default_rng(SEMILLA)
    muestra = rng.choice(len(X), size=min(8000, len(X)), replace=False)
    con_titulo = titulos != "-"
    tam = np.bincount(temas)
    print(f"  {nombre}: {len(tam)} temas | tamaño min/mediana/max {tam.min()}/{int(np.median(tam))}/{tam.max()} "
          f"| NMI idioma {nmi(idiomas, temas):.3f} "
          f"| NMI titulo-nota {nmi(titulos[con_titulo], temas[con_titulo]) if con_titulo.any() else float('nan'):.3f} "
          f"| NMI fuente {nmi(fuentes, temas):.3f} "
          f"| silueta {silhouette_score(X[muestra], temas[muestra], metric='cosine'):.3f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Reentrena los temas de gold.nlp_topics en local.")
    parser.add_argument("--sin-llm", action="store_true", help="no nombrar temas con el LLM (nombre = palabras clave)")
    parser.add_argument("--solo-renombrar", action="store_true",
                        help="aplicar NOMBRES_REVISADOS a los resultados existentes sin reentrenar")
    args = parser.parse_args()
    if args.solo_renombrar:
        renombrar_resultados()
        return

    t0 = time.time()
    conn = get_db_connection()
    docs, emb, notas = cargar_corpus(conn)
    conn.close()
    print(f"{len(docs)} documentos con embedding ({time.time() - t0:.0f}s)")

    textos = [texto_para_temas(s, t) for s, _, t, _ in docs]
    print(f"{aplicar_embeddings_sin_titulo(docs, textos, emb)} reseñas de Booking sin el titulo de la nota")
    idiomas = np.array([detectar(t) for t in textos])
    fuentes = np.array([d[0] for d in docs])
    titulos = np.array([d[2].split(" | ")[0].strip() if textos[i] != d[2] else "-" for i, d in enumerate(docs)])
    clave_de = np.array(["B" if "(modelo B" in d[3] else "A" for d in docs])

    llm = None
    if not args.sin_llm:
        from llm_client import LLMClient
        llm = LLMClient()

    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    filas, descripcion_temas = [], []
    for clave in ("A", "B"):
        sel = np.where(clave_de == clave)[0]
        conf = MODELOS[clave]
        print(f"\n===== Modelo {clave}: {len(sel)} documentos, k={conf['k']} =====", flush=True)
        X, medias = centrar_por_idioma(emb[sel], idiomas[sel])
        textos_modelo = [textos[i] for i in sel]
        modelo, temas, confianza = entrenar(clave, textos_modelo, X)
        medir("resultado", X, temas, idiomas[sel], titulos[sel], fuentes[sel])

        palabras = {t: [w for w, _ in modelo.get_topic(t)][:10] for t in range(conf["k"])}
        azar = np.random.default_rng(SEMILLA)
        notas_modelo = notas[sel]
        con_nota = notas_modelo[~np.isnan(notas_modelo)]
        referencia = (f"Referencia: en este conjunto la nota media es {con_nota.mean():.1f} y el "
                      f"{np.mean(con_nota <= 6):.0%} de las reseñas tiene nota de 6 o menos." if len(con_nota) else "")
        ejemplos, contexto, breves, nota_media, pct_bajas = {}, {}, {}, {}, {}
        for t in range(conf["k"]):
            miembros = np.where(temas == t)[0]
            cercanos = miembros[np.argsort(-confianza[miembros])[:4]]
            resto = np.setdiff1d(miembros, cercanos)
            al_azar = azar.choice(resto, size=min(4, len(resto)), replace=False)
            ejemplos[t] = [textos_modelo[j].replace("\n", " ")[:220] for j in (*cercanos, *al_azar)]
            breves[t] = float(np.mean([len(textos_modelo[j].split()) < 6 for j in miembros]))
            validas = notas_modelo[miembros][~np.isnan(notas_modelo[miembros])]
            # Por debajo del 30 % con nota el tema es sobre todo foro o YouTube.
            if len(validas) >= 0.3 * len(miembros):
                nota_media[t], pct_bajas[t] = float(validas.mean()), float(np.mean(validas <= 6))
                texto_nota = f"nota media {nota_media[t]:.1f}, {pct_bajas[t]:.0%} con nota de 6 o menos"
            else:
                nota_media[t] = pct_bajas[t] = None
                texto_nota = "casi sin nota (foro o comentarios)"
            lenguas = Counter(idiomas[sel][miembros].tolist()).most_common(3)
            contexto[t] = (f"{len(miembros)} textos, {breves[t]:.0%} con menos de 6 palabras; {texto_nota}; idiomas: "
                           + ", ".join(f"{l} {n / len(miembros):.0%}" for l, n in lenguas))
        nombres = (nombrar_temas(llm, clave, palabras, ejemplos, contexto, referencia) if llm
                   else {t: ", ".join(palabras[t][:3]) for t in palabras})
        for aviso in aplicar_revisiones(clave, nombres, palabras):
            print(f"  AVISO: {aviso}")

        tam = np.bincount(temas, minlength=conf["k"])
        for pos, i in enumerate(sel):
            t = int(temas[pos])
            filas.append((docs[i][0], docs[i][1], t, nombres[t], ", ".join(palabras[t][:6]),
                          int(tam[t]), round(float(confianza[pos]), 4), conf["model_name"]))
        for t in range(conf["k"]):
            miembros = temas == t
            descripcion_temas.append({
                "modelo": clave, "topic_id": t, "nombre": nombres[t], "palabras_clave": palabras[t],
                "tamano": int(tam[t]),
                "fuentes": dict(Counter(fuentes[sel][miembros].tolist())),
                "idiomas": dict(Counter(idiomas[sel][miembros].tolist()).most_common(4)),
                "pct_textos_breves": round(breves[t], 3),
                "nota_media": None if nota_media[t] is None else round(nota_media[t], 2),
                "pct_notas_6_o_menos": None if pct_bajas[t] is None else round(pct_bajas[t], 3),
                "ejemplos": ejemplos[t][:3],
            })
            nota = "  -  " if nota_media[t] is None else f"{nota_media[t]:4.1f} {pct_bajas[t]:>4.0%}"
            print(f"  #{t:>2} {tam[t]:>5}  {nombres[t]:40s} | nota {nota} | {', '.join(palabras[t][:6])}")

        modelo.set_topic_labels(nombres)
        modelo.save(str(DIR_MODELOS / f"modelo_{clave}"), serialization="safetensors",
                    save_ctfidf=True, save_embedding_model=EMBEDDING_MODEL_NAME)
        np.savez(DIR_MODELOS / f"centrado_idioma_{clave}.npz", **medias)

    with open(RESULTADOS_CSV, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["source", "source_id", "topic_id", "topic_label", "topic_keywords",
                           "topic_size", "probability", "model_name"])
        escritor.writerows(filas)
    TEMAS_JSON.write_text(json.dumps(descripcion_temas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados: {RESULTADOS_CSV}\nTemas: {TEMAS_JSON}\nModelos: {DIR_MODELOS}")
    print(f"Tiempo total: {(time.time() - t0) / 60:.1f} min. Siguiente paso: python analytics/topics/volcar_topicos.py")


if __name__ == "__main__":
    main()
