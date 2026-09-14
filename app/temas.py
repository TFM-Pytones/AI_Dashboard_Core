import pandas as pd
import plotly.express as px
import streamlit as st

from app.topic_labels_es import topic_label_es
from app.ui_helpers import latest_value, render_footer

SOURCE_LABELS = {
    "booking_review": "Booking",
    "tripadvisor_review": "TripAdvisor",
    "losviajeros_message": "Los Viajeros (foro)",
    "youtube_comment": "YouTube",
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


def sample_chunks(chunks_df: pd.DataFrame, municipio: str, topic_id: int, n: int = 15) -> pd.DataFrame:
    filtered = chunks_df.loc[
        (chunks_df["municipio"] == municipio) & (chunks_df["topic_id"] == topic_id)
    ].copy()
    filtered["fuente"] = filtered["source"].map(lambda s: SOURCE_LABELS.get(s, s))
    return filtered.sort_values("fecha", ascending=False).head(n)


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
        st.metric("💬 Opiniones analizadas", int(row["n_opiniones"]))
    with col2.container(border=True):
        st.metric("🏷️ Temas distintos detectados", int(row["n_topicos_distintos"]))

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
        st.plotly_chart(fig_topicos, use_container_width=True)

    st.subheader("Ver opiniones reales de un tema")
    topico_elegido = st.selectbox("Tema", topicos_df["label_es"].tolist(), key="temas_topico_elegido")
    topic_id_elegido = int(topicos_df.loc[topicos_df["label_es"] == topico_elegido, "topic_id"].iloc[0])

    muestra = sample_chunks(chunks_df, municipio, topic_id_elegido, n=15)
    if muestra.empty:
        st.info("No hay opiniones de muestra para este tema en este municipio.")
    else:
        st.dataframe(
            muestra[["fecha", "pais_resenante", "rating", "fuente", "text"]],
            width="stretch",
        )

    render_footer(
        "gold.gold_topicos_municipio, gold.nlp_chunks (BERTopic)",
        as_of=latest_value(chunks_df["fecha"]),
    )
