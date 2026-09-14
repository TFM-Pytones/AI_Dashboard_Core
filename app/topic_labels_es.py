"""Curated Spanish labels for the topic clusters produced by the BERTopic
pipeline (gold.nlp_topics / gold.gold_topicos_municipio). BERTopic's raw
labels are keyword lists, often in a single reviewer language (Italian,
German, Russian, Dutch...) or dominated by a specific host's name, rather
than a clean human-readable topic. This module hand-curates a Spanish label
for each topic_id currently seen in gold_topicos_municipio's top-3 breakdown
(56 ids, audited 2026-09-14). A topic_id introduced by a future re-run of
the BERTopic model that isn't in this dict yet falls back to its raw
keyword label via topic_label_es() instead of crashing.
"""

TOPIC_LABELS_ES: dict[int, str] = {
    0: "Buena comida y servicio en restaurantes",
    1: "Guachinches y gastronomía canaria (mojo, papas)",
    3: "Ubicación en el centro de Santa Cruz",
    4: "Quejas sobre pedidos y tiempos de espera en restaurantes",
    7: "Denuncias de estafa con el depósito o reembolso",
    8: "Ubicación en el centro de Puerto de la Cruz",
    9: "Opiniones en italiano sobre la zona de Los Cristianos",
    10: "Personal amable e instalaciones limpias",
    11: "Villas familiares con espacio exterior",
    12: "Apartamentos pequeños tipo estudio (cocina, lavadora)",
    13: "Buena relación calidad-precio",
    21: "Centro histórico de La Laguna",
    23: "Ruta de vinos: Icod de los Vinos y Garachico",
    24: "Buffet y variedad de cenas en hoteles",
    26: "Instalaciones antiguas que necesitan reforma",
    31: "Elogios muy positivos al apartamento",
    35: "Cercanía al aeropuerto (ruido de aviones)",
    44: "Limpieza y detalles cuidados, exterior descuidado",
    56: "Ambiente de hostel: voluntarios, literas, dormitorio compartido",
    66: "Lugar tranquilo para desconectar",
    67: "Senderismo: teleférico del Teide y miradores",
    78: "Casa muy bonita y cómoda",
    80: "Alojamiento limpio y cómodo, con auto check-in",
    86: "Eventos culturales y fiestas locales",
    87: "Senderismo en el Parque Rural de Anaga",
    96: "Ubicación en Candelaria",
    107: "Casa limpia y bien situada",
    110: "Foro: elegir hotel para viajar con niños",
    116: "Alquiler de coche y transporte público",
    120: "Zona tranquila",
    121: "Opiniones en alemán: vistas al mar y buena ubicación",
    124: "Apartamento espacioso bien ubicado (Garachico)",
    140: "Falta de toallas o utensilios, mobiliario antiguo",
    148: "Foro: recomendaciones de hotel antes del viaje",
    161: "Anfitriones muy valorados (caso: Cruzy y Rubén)",
    183: "Anfitriona atenta y casa tranquila (caso: Lourdes)",
    193: "Problemas de instalaciones (baños, insonorización)",
    207: "Vistas a los acantilados de Los Gigantes",
    208: "Opiniones en alemán: clientes recurrentes, buena ubicación",
    216: "Ubicación en La Orotava",
    220: "Zona tranquila y apartamento limpio",
    227: "Opiniones en ruso: personal amable y buena ubicación",
    231: "Presencia o falta de ascensor",
    232: "Foro/blog: recomendaciones de qué visitar",
    249: "Sensación de estar en casa, anfitrión atento (caso: Pedro)",
    250: "Relación calidad-precio, sofá incómodo",
    292: "Opiniones en neerlandés: casa tranquila, poco turística",
    310: "Anfitriona excelente y ubicación céntrica (caso: Maria)",
    313: "Villa con vistas espectaculares",
    318: "Vistas espectaculares",
    351: "Buena ubicación cerca de Playa de las Américas",
    370: "Hotel con encanto en casco histórico",
    382: "Opiniones breves multilingües: buen anfitrión y vistas",
    400: "Foro: dónde comprar cerca de Callao Salvaje",
    414: "Foro: consejos y respuestas sobre excursiones",
    426: "Opiniones en alemán: jardín y casa",
}


def topic_label_es(topic_id: int, fallback_label: str) -> str:
    return TOPIC_LABELS_ES.get(topic_id, fallback_label)
