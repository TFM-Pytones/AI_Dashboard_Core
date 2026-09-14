import pandas as pd
import plotly.express as px
import streamlit as st

from app.topic_labels_es import topic_label_es
from app.translation import translate_to_spanish
from app.ui_helpers import format_metric, latest_value, render_footer

SOURCE_LABELS = {
    "booking_review": "Booking",
    "tripadvisor_review": "TripAdvisor",
    "losviajeros_message": "Los Viajeros (foro)",
    "youtube_comment": "YouTube",
}

SOURCE_ICONS = {
    "Booking": "🅱️",
    "TripAdvisor": "🦉",
    "Los Viajeros (foro)": "💬",
    "YouTube": "▶️",
}


def get_topicos_row(df: pd.DataFrame, municipio: str) -> pd.Series | None:
    matches = df.loc[df["municipio"] == municipio]
    if matches.empty:
        return None
    return matches.iloc[0]


def fuentes_breakdown(row: pd.Series) -> pd.DataFrame:
    rows = [
        {"fuente": SOURCE_LABELS.get(fuente, fuente), "cantidad": cantidad}
        for fuente, cantidad in row["fuentes"].items()
    ]
    return pd.DataFrame(rows)


def top_topicos_dataframe(row: pd.Series) -> pd.DataFrame:
    rows = [
        {
            "topic_id": t["topic_id"],
            "label_es": topic_label_es(t["topic_id"], t["label"]),
            "n": t["n"],
        }
        for t in row["topicos_top3"]
    ]
    return pd.DataFrame(rows)


def _map_fuente(source_column: pd.Series) -> pd.Series:
    return source_column.map(lambda s: SOURCE_LABELS.get(s, s))


def available_fuentes(chunks_df: pd.DataFrame, municipio: str) -> list[str]:
    subset = chunks_df.loc[chunks_df["municipio"] == municipio]
    return sorted(_map_fuente(subset["source"]).dropna().unique().tolist())


def topics_for_municipio(
    chunks_df: pd.DataFrame, municipio: str, fuentes: list[str] | None = None, n: int = 20
) -> pd.DataFrame:
    # topicos_top3 (top_topicos_dataframe) only ever has 3 entries -- this
    # scans every chunk for the municipio so the dropdown can offer more than
    # just the top 3 topics, and can be narrowed down by fuente.
    subset = chunks_df.loc[chunks_df["municipio"] == municipio].copy()
    subset["fuente"] = _map_fuente(subset["source"])
    if fuentes:
        subset = subset[subset["fuente"].isin(fuentes)]
    counts = (
        subset.groupby("topic_id").agg(n=("topic_id", "size"), label=("topic_label", "first")).reset_index()
    )
    counts["label_es"] = counts.apply(lambda r: topic_label_es(int(r["topic_id"]), r["label"]), axis=1)
    counts["display"] = counts["label_es"] + " (" + counts["n"].astype(str) + ")"
    return counts.sort_values("n", ascending=False).head(n)[["topic_id", "label_es", "display", "n"]]


def sample_chunks(
    chunks_df: pd.DataFrame,
    municipio: str,
    topic_id: int,
    fuentes: list[str] | None = None,
    n: int = 15,
) -> pd.DataFrame:
    filtered = chunks_df.loc[
        (chunks_df["municipio"] == municipio) & (chunks_df["topic_id"] == topic_id)
    ].copy()
    filtered["fuente"] = _map_fuente(filtered["source"])
    if fuentes:
        filtered = filtered[filtered["fuente"].isin(fuentes)]
    return filtered.sort_values("fecha", ascending=False).head(n)


def selected_topic_from_event(event: dict | None, topicos_df: pd.DataFrame) -> int | None:
    if not event:
        return None
    points = event.get("selection", {}).get("points", [])
    if not points:
        return None
    match = topicos_df.loc[topicos_df["label_es"] == points[0].get("y")]
    if match.empty:
        return None
    return int(match["topic_id"].iloc[0])


def prepare_review_cards(muestra: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in muestra.iterrows():
        fuente = row.get("fuente")
        rating = row.get("rating")
        pais = row.get("pais_resenante")
        cards.append(
            {
                "chunk_id": row.get("chunk_id"),
                "icono": SOURCE_ICONS.get(fuente, "💬"),
                "fuente": fuente,
                "rating": None if pd.isna(rating) else float(rating),
                "fecha": row.get("fecha"),
                "pais": "—" if pd.isna(pais) else pais,
                "text": row.get("text"),
            }
        )
    return cards


def render_temas_tab(topicos_municipio_df: pd.DataFrame, chunks_df: pd.DataFrame) -> None:
    municipio = st.selectbox(
        "Municipio", sorted(topicos_municipio_df["municipio"].tolist()), key="temas_municipio"
    )
    row = get_topicos_row(topicos_municipio_df, municipio)
    if row is None:
        st.warning("No hay datos de temas para este municipio.")
        return

    col1, col2 = st.columns(2)
    with col1.container(border=True):
        st.metric(
            "💬 Opiniones analizadas",
            format_metric(row["n_opiniones"], "entero"),
            help="Reseñas, mensajes y comentarios analizados con NLP para este municipio.",
        )
    with col2.container(border=True):
        st.metric(
            "🏷️ Temas distintos detectados",
            format_metric(row["n_topicos_distintos"], "entero"),
            help="Temas distintos identificados mediante topic modeling (BERTopic).",
        )

    fuentes_df = fuentes_breakdown(row)
    topicos_df = top_topicos_dataframe(row)

    col_fuentes, col_topicos = st.columns(2)
    with col_fuentes:
        fig_fuentes = px.pie(
            fuentes_df,
            names="fuente",
            values="cantidad",
            title="Origen de las opiniones",
            color_discrete_sequence=["#1e3a8a", "#eb6834", "#6b7280", "#f3f4f6"],
        )
        st.plotly_chart(fig_fuentes, use_container_width=True)
    with col_topicos:
        fig_topicos = px.bar(
            topicos_df.sort_values("n"),
            x="n",
            y="label_es",
            orientation="h",
            title="Temas más mencionados",
        )
        fig_topicos.update_traces(marker_color="#1e3a8a")
        st.plotly_chart(
            fig_topicos,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="temas_topicos_chart",
        )

    st.subheader("Ver opiniones reales de un tema")
    st.caption(
        "Combina los filtros de fuente y tema, o haz clic directamente en una barra del "
        "gráfico de arriba."
    )

    filtro_tema_col, filtro_fuente_col = st.columns([2, 2])

    fuente_options = available_fuentes(chunks_df, municipio)
    if "temas_fuentes_filtro" not in st.session_state or not set(
        st.session_state["temas_fuentes_filtro"]
    ).issubset(set(fuente_options)):
        st.session_state["temas_fuentes_filtro"] = fuente_options
    fuentes_seleccionadas = filtro_fuente_col.multiselect(
        "Fuente", fuente_options, key="temas_fuentes_filtro"
    )

    if not fuentes_seleccionadas:
        st.info("Selecciona al menos una fuente para ver los temas y las opiniones.")
    else:
        topics_df = topics_for_municipio(chunks_df, municipio, fuentes=fuentes_seleccionadas, n=20)
        topic_options = topics_df["display"].tolist()

        # A chart click pushes its display string into the selectbox's own
        # state *before* the widget is created, so it wins this rerun without
        # fighting the selectbox's normal key-based state on later reruns.
        event = st.session_state.get("temas_topicos_chart")
        clicked_topic_id = selected_topic_from_event(event, topicos_df)
        if clicked_topic_id is not None:
            clicked_match = topics_df.loc[topics_df["topic_id"] == clicked_topic_id]
            if not clicked_match.empty:
                st.session_state["temas_topico_elegido"] = clicked_match["display"].iloc[0]

        if st.session_state.get("temas_topico_elegido") not in topic_options:
            st.session_state["temas_topico_elegido"] = topic_options[0]

        topico_elegido_display = filtro_tema_col.selectbox(
            "Tema", topic_options, key="temas_topico_elegido"
        )
        topic_id_elegido = int(
            topics_df.loc[topics_df["display"] == topico_elegido_display, "topic_id"].iloc[0]
        )

        muestra = sample_chunks(chunks_df, municipio, topic_id_elegido, fuentes=fuentes_seleccionadas, n=15)
        if muestra.empty:
            st.info("No hay opiniones de muestra para esta combinación de tema y fuente.")
        else:
            for card in prepare_review_cards(muestra):
                with st.container(border=True):
                    meta_cols = st.columns([2, 1, 1, 2])
                    meta_cols[0].markdown(f"{card['icono']} **{card['fuente']}**")
                    meta_cols[1].markdown(
                        f"⭐ {card['rating']:.1f}" if card["rating"] is not None else "⭐ —"
                    )
                    meta_cols[2].markdown(f"📅 {card['fecha']}")
                    meta_cols[3].markdown(f"🌍 {card['pais']}")
                    st.write(card["text"])

                    traduccion_key = f"temas_traduccion_{card['chunk_id']}"
                    if st.button("🌐 Traducir", key=f"temas_traducir_{card['chunk_id']}"):
                        with st.spinner("Traduciendo..."):
                            try:
                                st.session_state[traduccion_key] = translate_to_spanish(card["text"])
                            except Exception:
                                st.error("No se pudo traducir esta opinión. Inténtalo de nuevo.")
                    if st.session_state.get(traduccion_key):
                        st.markdown(f"🌐 *{st.session_state[traduccion_key]}*")

    render_footer(
        "gold.gold_topicos_municipio, gold.nlp_chunks (BERTopic)",
        as_of=latest_value(chunks_df["fecha"]),
    )
