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
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))

from filtros import detectar_perspectiva, extraer_filtros, relajar_filtros, resolver_municipio, resolver_zona  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from retriever import Chunk, search  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PROMPT_TEMPLATE = """Eres un analista de turismo de TUI especializado en Tenerife. Responde la pregunta del usuario basandote UNICAMENTE en los fragmentos de opiniones reales que se te dan.

Reglas obligatorias:
1. Usa solo la informacion de los fragmentos. No uses tu conocimiento general sobre Tenerife.
2. Cita entre corchetes el numero de cada fragmento que utilices. Ejemplo: "los clientes se quejan del ruido nocturno [2][5]".
3. Si los fragmentos no contienen informacion suficiente para responder, di exactamente: "No hay informacion suficiente en las opiniones recuperadas para responder a esto."
4. NO des cifras totales, porcentajes ni recuentos, y no compares cuantas veces aparece algo en unos lugares frente a otros. Solo ves una muestra de {k} opiniones de un corpus de casi 88.000: cualquier recuento o ranking seria inventado. Si la pregunta pide contar o comparar cantidades, di que eso no se puede deducir de una muestra de opiniones.
5. Ajusta las palabras a los fragmentos que lo respaldan: "un cliente" o "un viajero" si es uno solo, "varios" solo si son al menos tres.
6. Fijate en la fecha de cada fragmento. Si los que usas son anteriores a 2022, o de 2020 y 2021 (pandemia), dilo expresamente y no los presentes como la situacion actual.
7. En los mensajes del foro, el lugar indicado es un sitio que el mensaje menciona, no necesariamente de lo que trata: no atribuyas a ese lugar lo que el texto dice de otro sitio.
8. Responde en español, en 2 o 3 parrafos, con tono de informe profesional.

{aviso}PREGUNTA: {pregunta}

FRAGMENTOS RECUPERADOS:
{fragmentos}
"""


# El LLM devuelve cada parrafo como una sola linea de varios cientos de
# caracteres; sin envolver, la terminal la parte a lo bruto y no hay quien lo lea.
ANCHO = 88


def envolver(texto: str, sangria: str = "") -> str:
    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    return "\n\n".join(
        textwrap.fill(p, width=ANCHO, initial_indent=sangria, subsequent_indent=sangria)
        for p in parrafos
    )


TIPO_FUENTE = {
    "booking_review": "reseña de Booking",
    "tripadvisor_review": "reseña de TripAdvisor",
    "losviajeros_message": "mensaje del foro LosViajeros",
    "youtube_comment": "comentario de YouTube",
}


def texto_para_llm(c: Chunk) -> str:
    """Booking guarda cada reseña como 'titulo | lo que gusto | lo que no gusto'
    en un solo texto. Sin marcar las partes, el LLM tomo por queja un aire
    acondicionado que estaba en lo que gusto. Solo se etiquetan las reseñas de
    tres partes: con dos no se sabe si la segunda es elogio o queja."""
    partes = c.text.split(" | ")
    if c.source == "booking_review" and len(partes) == 3:
        titulo, gusto, no_gusto = partes
        return f"Titulo: {titulo}\nLo que le gusto: {gusto}\nLo que no le gusto: {no_gusto}"
    return c.text


def formatear_fragmentos(chunks: list[Chunk]) -> str:
    partes = []
    for i, c in enumerate(chunks, 1):
        lugar = (f"menciona {c.lugar}" if c.source == "losviajeros_message" and c.lugar != "sin ubicacion"
                 else c.lugar)
        meta = [TIPO_FUENTE.get(c.source, c.source), lugar, str(c.fecha) if c.fecha else "sin fecha"]
        if c.rating is not None:
            meta.append(f"nota {c.rating:g}/10")
        partes.append(f"[{i}] ({', '.join(meta)})\n{texto_para_llm(c)}")
    return "\n\n".join(partes)


NOMBRES_FILTRO = {
    "pais_resenante": "pais del reseñante",
    "fecha_desde": "fecha desde",
    "fecha_hasta": "fecha hasta",
    "source": "fuente",
}


def valor_legible(valor):
    return valor[0] if isinstance(valor, list) and len(valor) == 1 else valor


def describir_filtros(filtros: dict) -> str:
    return ", ".join(f"{clave}={valor_legible(v)}" for clave, v in filtros.items())


@dataclass
class Respuesta:
    texto: str
    chunks: list[Chunk]
    # Filtros deducidos que se soltaron porque juntos no dejaban ningun
    # fragmento (ver filtros.relajar_filtros).
    filtros_descartados: dict = field(default_factory=dict)
    # alojamiento | destino | general: decide los topes por fuente (ver retriever.diversificar).
    perspectiva: str = "general"


def responder(pregunta: str, k: int = 8, filters: dict | None = None,
              hibrida: bool = True, fijos=frozenset()) -> Respuesta:
    """`fijos` son las claves de `filters` escritas a mano por el usuario, que
    nunca se relajan."""
    filters, descartados = relajar_filtros(filters or {}, fijos)
    perspectiva = detectar_perspectiva(pregunta)
    chunks = search(pregunta, k=k, filters=filters, hibrida=hibrida, perspectiva=perspectiva)
    if not chunks:
        # Misma frase que usa el LLM al abstenerse: quedarse sin fragmentos es
        # otra forma de no tener informacion, y asi el caso se mide igual en la
        # evaluacion (analytics/rag/eval/run_eval.py).
        return Respuesta("No hay informacion suficiente en las opiniones recuperadas para responder a esto "
                         "(ningun fragmento cumple los filtros aplicados).", [], descartados, perspectiva)

    aviso = ""
    if descartados:
        # Sin avisar, el LLM responderia como si los fragmentos cumplieran toda
        # la pregunta ("los alemanes opinan...") cuando son de cualquier pais.
        ignorados = ", ".join(f"{NOMBRES_FILTRO.get(c, c)} = {valor_legible(v)}" for c, v in descartados.items())
        aviso = (f"AVISO: ninguna opinion cumple a la vez todos los criterios de la pregunta, asi que los "
                 f"fragmentos NO estan filtrados por: {ignorados}. Dilo al principio de la respuesta.\n\n")

    prompt = PROMPT_TEMPLATE.format(
        pregunta=pregunta,
        fragmentos=formatear_fragmentos(chunks),
        k=len(chunks),
        aviso=aviso,
    )
    # temperature baja: aqui interesa que se pegue a los fragmentos, no que sea creativo.
    return Respuesta(LLMClient().complete(prompt, temperature=0.2), chunks, descartados, perspectiva)


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
    parser.add_argument("--sin-auto", action="store_true",
                        help="no deducir filtros de la pregunta")
    parser.add_argument("--solo-vectorial", action="store_true",
                        help="desactiva la busqueda hibrida (util para comparar)")
    args = parser.parse_args()

    explicitos = {
        clave: getattr(args, clave)
        for clave in ("municipio", "zona", "source", "pais_resenante", "fecha_desde", "fecha_hasta")
        if getattr(args, clave)
    }

    # Lo escrito a mano manda sobre lo deducido de la pregunta.
    deducidos = {} if args.sin_auto else extraer_filtros(args.pregunta)
    filters = {**deducidos, **explicitos}

    # Un municipio puede estar escrito de varias formas en la BD: se traduce a
    # todas sus variantes (ver filtros.py).
    if "municipio" in explicitos:
        filters["municipio"] = resolver_municipio(explicitos["municipio"])
    if "zona" in explicitos:
        filters["zona"] = resolver_zona(explicitos["zona"])

    print(f"\nPREGUNTA: {args.pregunta}")
    if filters:
        origen = " (deducidos de la pregunta)" if deducidos and not explicitos else ""
        print(f"FILTROS:  {describir_filtros(filters)}{origen}")

    r = responder(args.pregunta, k=args.k, filters=filters,
                  hibrida=not args.solo_vectorial, fijos=set(explicitos))
    if r.filtros_descartados:
        print(f"IGNORADOS: {describir_filtros(r.filtros_descartados)} "
              "(ninguna opinion cumple todos los filtros a la vez)")
    print(f"PERSPECTIVA: {r.perspectiva}")

    print("\n" + "=" * ANCHO)
    print(envolver(r.texto))
    print("=" * ANCHO)

    print(f"\nFUENTES ({len(r.chunks)} fragmentos recuperados):\n")
    for i, c in enumerate(r.chunks, 1):
        cabecera = f"[{i}] {c.source} · {c.lugar}"
        if c.fecha:
            cabecera += f" · {c.fecha}"
        cabecera += f" · similitud {1 - c.distancia:.0%}"
        print(cabecera)
        print(envolver(c.text[:300] + ("..." if len(c.text) > 300 else ""), sangria="    "))
        print()


if __name__ == "__main__":
    main()
