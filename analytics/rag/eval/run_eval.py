"""Fase 5 del RAG (ver plan_rag.md) -- Evaluacion del sistema contra el
conjunto de oro de preguntas.yaml.

Metricas:

  Filtros           De las preguntas con filtros esperados, cuantas los deduce
                    correctamente. Mide la extraccion de analytics/rag/filtros.py.

  Recall@k          De las preguntas normales, en cuantas aparece al menos uno
                    de los terminos esperados entre los fragmentos recuperados.
                    Mide la recuperacion, sin depender del LLM.

  Abstencion        De las preguntas cuya respuesta no esta en el corpus,
                    cuantas se contestan admitiendo que no hay informacion. Un
                    valor bajo significa que el sistema alucina.

  Agregacion        De las preguntas de conteo, cuantas evita responder con una
                    cifra concreta. El RAG solo ve k fragmentos de 87.981: si
                    da un total, se lo esta inventando.

  Fundamentacion    Un LLM juez comprueba si cada afirmacion de la respuesta se
                    apoya en los fragmentos citados. Es la metrica cara (una
                    llamada extra por pregunta), se omite con --rapido.

Compara ademas busqueda hibrida contra puramente vectorial, que es la
justificacion empirica de la decision de la Fase 4.

Uso:
    python analytics/rag/eval/run_eval.py
    python analytics/rag/eval/run_eval.py --rapido        # sin LLM juez
    python analytics/rag/eval/run_eval.py --solo-vectorial
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(RAG_DIR.parent / "llm"))

from filtros import extraer_filtros, relajar_filtros  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from rag_answer import responder  # noqa: E402
from retriever import search  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PREGUNTAS_PATH = Path(__file__).resolve().parent / "preguntas.yaml"
K = 8

# La frase exacta que el prompt de rag_answer.py obliga a usar al abstenerse.
FRASE_ABSTENCION = "no hay informacion suficiente"

PROMPT_JUEZ = """Eres un evaluador estricto de sistemas de respuesta automatica.

Te doy una RESPUESTA generada a partir de unos FRAGMENTOS. Tu tarea es decidir si la respuesta esta fundamentada: cada afirmacion concreta debe poder deducirse de los fragmentos, sin añadir datos externos ni inventar cifras.

Contesta UNICAMENTE con una de estas tres palabras:
FUNDAMENTADA   - todo lo que afirma se apoya en los fragmentos
PARCIAL        - lo esencial se apoya, pero hay algun detalle no respaldado
INVENTADA      - afirma cosas que no estan en los fragmentos

RESPUESTA:
{respuesta}

FRAGMENTOS:
{fragmentos}
"""


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def se_abstiene(respuesta: str) -> bool:
    return FRASE_ABSTENCION in normalizar(respuesta)


def da_cifra_concreta(respuesta: str) -> bool:
    """Busca totales o porcentajes inventados. Se ignoran los numeros entre
    corchetes, que son las citas a los fragmentos."""
    sin_citas = re.sub(r"\[\d+\]", "", respuesta)
    return bool(re.search(r"\b\d{3,}\b|\b\d+([.,]\d+)?\s*%", sin_citas))


def filtros_correctos(esperados: dict, deducidos: dict) -> bool:
    """Los valores de lugar se comparan normalizados porque la BD tiene el
    mismo municipio escrito de varias formas (ver filtros.py)."""
    for clave, esperado in esperados.items():
        obtenido = deducidos.get(clave)
        if obtenido is None:
            return False
        if isinstance(obtenido, list):
            if not any(normalizar(str(v)) == normalizar(str(esperado)) for v in obtenido):
                return False
        elif normalizar(str(obtenido)) != normalizar(str(esperado)):
            return False
    return True


def terminos_encontrados(chunks, terminos: list[str]) -> bool:
    texto = normalizar(" ".join(c.text for c in chunks))
    return any(normalizar(t) in texto for t in terminos)


def juzgar(cliente: LLMClient, respuesta: str, chunks) -> str:
    fragmentos = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
    # max_tokens muy holgado aunque el veredicto sea una sola palabra:
    # gpt-oss-120b razona antes de responder y ese razonamiento cuenta contra el
    # limite. Si se agota ahi, `content` vuelve vacio y el veredicto se pierde.
    # Cuanto mas largos los fragmentos, mas razona: con 500 fallaba justo en los
    # casos reales de 8 fragmentos.
    veredicto = cliente.complete(
        PROMPT_JUEZ.format(respuesta=respuesta, fragmentos=fragmentos),
        temperature=0.0, max_tokens=2000,
    ).strip().upper()
    for etiqueta in ("FUNDAMENTADA", "PARCIAL", "INVENTADA"):
        if etiqueta in veredicto:
            return etiqueta
    return "DESCONOCIDO"


def porcentaje(aciertos: int, total: int) -> str:
    return f"{aciertos}/{total} ({aciertos / total:.0%})" if total else "sin casos"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapido", action="store_true", help="omite el LLM juez")
    parser.add_argument("--solo-vectorial", action="store_true", help="desactiva la busqueda hibrida")
    args = parser.parse_args()

    casos = yaml.safe_load(PREGUNTAS_PATH.read_text(encoding="utf-8"))
    hibrida = not args.solo_vectorial
    cliente = None if args.rapido else LLMClient()

    modo = "HIBRIDA" if hibrida else "SOLO VECTORIAL"
    print(f"\nEvaluando {len(casos)} preguntas -- busqueda {modo}, k={K}\n")

    filtros_ok = filtros_total = 0
    recall_ok = recall_total = 0
    abstencion_ok = abstencion_total = 0
    agregacion_ok = agregacion_total = 0
    veredictos: dict[str, int] = {}
    errores: list[tuple[str, str]] = []

    for caso in casos:
        tipo = caso["tipo"]
        pregunta = caso["pregunta"]
        marcas = []

        if caso.get("filtros_esperados"):
            filtros_total += 1
            acierto = filtros_correctos(caso["filtros_esperados"], extraer_filtros(pregunta))
            filtros_ok += acierto
            marcas.append(f"filtros={'OK' if acierto else 'FALLO'}")

        if tipo == "normal":
            # Misma relajacion que aplica responder(), para que el recall mida
            # lo mismo que luego ve el LLM.
            filtros, _ = relajar_filtros(extraer_filtros(pregunta))
            chunks = search(pregunta, k=K, filters=filtros, hibrida=hibrida)
            if caso.get("terminos_esperados"):
                recall_total += 1
                acierto = terminos_encontrados(chunks, caso["terminos_esperados"])
                recall_ok += acierto
                marcas.append(f"recall={'OK' if acierto else 'FALLO'}")

            if cliente and chunks:
                # El plan gratuito de Groq tiene un tope diario de tokens y una
                # evaluacion completa consume una buena parte: si se agota a
                # mitad, se anota y se sigue en vez de perder todo el resultado.
                try:
                    r = responder(pregunta, k=K, filters=filtros, hibrida=hibrida)
                    veredicto = juzgar(cliente, r.texto, r.chunks)
                    veredictos[veredicto] = veredictos.get(veredicto, 0) + 1
                    marcas.append(veredicto.lower())
                except Exception as e:
                    errores.append((caso["id"], str(e)[:120]))
                    marcas.append("ERROR-LLM")
        elif args.rapido:
            # --rapido no gasta ni una llamada al LLM: abstencion y agregacion
            # necesitan generar respuesta, asi que se dejan sin evaluar. Permite
            # comparar recuperacion (filtros y recall) sin consumir cuota.
            marcas.append("sin evaluar (--rapido)")
        else:
            try:
                respuesta = responder(pregunta, k=K, filters=extraer_filtros(pregunta), hibrida=hibrida).texto
            except Exception as e:
                errores.append((caso["id"], str(e)[:120]))
                print(f"  [{tipo:10s}] {caso['id']:24s} ERROR")
                continue
            if tipo == "abstencion":
                abstencion_total += 1
                acierto = se_abstiene(respuesta)
                abstencion_ok += acierto
                marcas.append(f"abstencion={'OK' if acierto else 'FALLO'}")
            elif tipo == "agregacion":
                agregacion_total += 1
                # Acierta si se abstiene o si al menos no suelta una cifra inventada.
                acierto = se_abstiene(respuesta) or not da_cifra_concreta(respuesta)
                agregacion_ok += acierto
                marcas.append(f"agregacion={'OK' if acierto else 'FALLO'}")

        print(f"  [{tipo:10s}] {caso['id']:24s} {' '.join(marcas)}")

    print("\n" + "=" * 60)
    print(f"Busqueda: {modo}")
    print("=" * 60)
    print(f"  Filtros deducidos correctos : {porcentaje(filtros_ok, filtros_total)}")
    print(f"  Recall@{K} (terminos)        : {porcentaje(recall_ok, recall_total)}")
    print(f"  Abstencion correcta         : {porcentaje(abstencion_ok, abstencion_total)}")
    print(f"  No inventa cifras           : {porcentaje(agregacion_ok, agregacion_total)}")
    if veredictos:
        total = sum(veredictos.values())
        print(f"  Fundamentacion (LLM juez)   : {total} respuestas evaluadas")
        for etiqueta in ("FUNDAMENTADA", "PARCIAL", "INVENTADA", "DESCONOCIDO"):
            if etiqueta in veredictos:
                print(f"      {etiqueta:14s} {porcentaje(veredictos[etiqueta], total)}")
    else:
        print("  Fundamentacion              : omitida (--rapido)")

    if errores:
        print(f"\n  {len(errores)} preguntas no evaluadas por error del LLM:")
        for id_caso, mensaje in errores[:3]:
            print(f"      {id_caso}: {mensaje}")


if __name__ == "__main__":
    main()
