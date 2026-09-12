"""Fase 3 del RAG (ver plan_rag.md) -- Responde una pregunta en lenguaje
natural citando opiniones reales del corpus.

Recupera los fragmentos mas cercanos con retriever.search() y se los pasa al
LLM como unica fuente permitida. El prompt es deliberadamente restrictivo: sin
esas reglas el modelo rellena los huecos con conocimiento general sobre
Tenerife y la respuesta deja de ser verificable, que es justo lo que aporta un
RAG frente a preguntarle al LLM a secas.

Limitacion por diseño: el LLM solo ve k fragmentos de los 87.981, asi que NO
puede responder preguntas agregadas ("cuantas reseñas...", "que municipio
tiene mas..."). Esas van al agente Text-to-SQL del Bloque 7. Ver la seccion 2
de plan_rag.md.

Uso:
    python analytics/rag/rag_answer.py "¿de que se quejan en Adeje?"
    python analytics/rag/rag_answer.py "¿que opinan del ruido?" --municipio Arona
    python analytics/rag/rag_answer.py "¿como es la playa?" --source tripadvisor_review --k 12
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))

from llm_client import LLMClient  # noqa: E402
from retriever import Chunk, search  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PROMPT_TEMPLATE = """Eres un analista de turismo de TUI especializado en Tenerife. Responde la pregunta del usuario basandote UNICAMENTE en los fragmentos de opiniones reales que se te dan.

Reglas obligatorias:
1. Usa solo la informacion de los fragmentos. No uses tu conocimiento general sobre Tenerife.
2. Cita entre corchetes el numero de cada fragmento que utilices. Ejemplo: "los clientes se quejan del ruido nocturno [2][5]".
3. Si los fragmentos no contienen informacion suficiente para responder, di exactamente: "No hay informacion suficiente en las opiniones recuperadas para responder a esto."
4. NO des cifras totales, porcentajes ni recuentos. Solo ves una muestra de {k} opiniones de un corpus de casi 88.000: cualquier total que dieras seria inventado. Habla en terminos cualitativos ("varios clientes mencionan...", "aparece de forma recurrente...").
5. Responde en español, en 2 o 3 parrafos, con tono de informe profesional.

PREGUNTA: {pregunta}

FRAGMENTOS RECUPERADOS:
{fragmentos}
"""


def formatear_fragmentos(chunks: list[Chunk]) -> str:
    partes = []
    for i, c in enumerate(chunks, 1):
        meta = [c.source, c.lugar]
        if c.fecha:
            meta.append(str(c.fecha))
        if c.rating is not None:
            meta.append(f"valoracion {c.rating}")
        partes.append(f"[{i}] ({', '.join(meta)})\n{c.text}")
    return "\n\n".join(partes)


def responder(pregunta: str, k: int = 8, filters: dict | None = None) -> tuple[str, list[Chunk]]:
    chunks = search(pregunta, k=k, filters=filters)
    if not chunks:
        return "No se recupero ningun fragmento con esos filtros.", []

    prompt = PROMPT_TEMPLATE.format(
        pregunta=pregunta,
        fragmentos=formatear_fragmentos(chunks),
        k=len(chunks),
    )
    # temperature baja: aqui interesa que se pegue a los fragmentos, no que sea creativo.
    return LLMClient().complete(prompt, temperature=0.2), chunks


def main():
    parser = argparse.ArgumentParser(description="Pregunta al corpus de opiniones de Tenerife.")
    parser.add_argument("pregunta")
    parser.add_argument("--k", type=int, default=8, help="fragmentos a recuperar (por defecto 8)")
    parser.add_argument("--municipio")
    parser.add_argument("--zona")
    parser.add_argument("--source", help="booking_review | tripadvisor_review | losviajeros_message | youtube_comment")
    parser.add_argument("--pais", dest="pais_resenante")
    parser.add_argument("--desde", dest="fecha_desde", help="YYYY-MM-DD")
    parser.add_argument("--hasta", dest="fecha_hasta", help="YYYY-MM-DD")
    args = parser.parse_args()

    filters = {
        clave: getattr(args, clave)
        for clave in ("municipio", "zona", "source", "pais_resenante", "fecha_desde", "fecha_hasta")
        if getattr(args, clave)
    }

    if filters:
        print(f"Filtros: {filters}")
    print(f"Pregunta: {args.pregunta}\n")

    respuesta, chunks = responder(args.pregunta, k=args.k, filters=filters)

    print("=" * 70)
    print(respuesta)
    print("=" * 70)
    print("\nFUENTES:")
    for i, c in enumerate(chunks, 1):
        print(f"  [{i}] {c.source} / {c.lugar} / dist={c.distancia:.3f}")
        print(f"      {c.text[:160]}{'...' if len(c.text) > 160 else ''}")


if __name__ == "__main__":
    main()
