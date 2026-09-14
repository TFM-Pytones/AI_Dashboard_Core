import pandas as pd

from app.temas import (
    fuentes_breakdown,
    get_topicos_row,
    prepare_review_cards,
    sample_chunks,
    selected_topic_from_event,
    top_topicos_dataframe,
)


def _topicos_municipio_df():
    return pd.DataFrame(
        [
            {
                "municipio": "Adeje",
                "n_opiniones": 14973.0,
                "n_topicos_distintos": 439,
                "topic_id_principal": 11,
                "topico_principal": "villa, outdoor, family, drive, kids, seating",
                "n_opiniones_principal": 417,
                "topicos_top3": [
                    {"n": 417, "label": "villa, outdoor, family, drive, kids, seating", "topic_id": 11},
                    {"n": 376, "label": "small, coffee, living room, washing, buy, complex", "topic_id": 12},
                    {
                        "n": 221,
                        "label": "highly, truly, appreciated, incredibly, wonderful, apartment absolutely",
                        "topic_id": 31,
                    },
                ],
                "fuentes": {"booking_review": 13251, "tripadvisor_review": 103, "losviajeros_message": 1619},
            },
            {
                "municipio": "Arona",
                "n_opiniones": 21539.0,
                "n_topicos_distintos": 439,
                "topic_id_principal": 12,
                "topico_principal": "small, coffee, living room, washing, buy, complex",
                "n_opiniones_principal": 321,
                "topicos_top3": [
                    {"n": 321, "label": "small, coffee, living room, washing, buy, complex", "topic_id": 12},
                ],
                "fuentes": {"booking_review": 20616},
            },
        ]
    )


def test_get_topicos_row_returns_matching_row():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    assert row["n_opiniones"] == 14973.0


def test_get_topicos_row_returns_none_for_unknown_municipio():
    assert get_topicos_row(_topicos_municipio_df(), "No Existe") is None


def test_fuentes_breakdown_maps_known_sources_to_display_labels():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    result = fuentes_breakdown(row)
    counts = dict(zip(result["fuente"], result["cantidad"]))
    assert counts == {"Booking": 13251, "TripAdvisor": 103, "Los Viajeros (foro)": 1619}


def test_fuentes_breakdown_falls_back_to_raw_key_for_unknown_source():
    row = pd.Series({"fuentes": {"reddit_post": 5}})
    result = fuentes_breakdown(row)
    assert result["fuente"].tolist() == ["reddit_post"]


def test_top_topicos_dataframe_uses_curated_spanish_labels():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    result = top_topicos_dataframe(row)
    assert result["label_es"].tolist() == [
        "Villas familiares con espacio exterior",
        "Apartamentos pequeños tipo estudio (cocina, lavadora)",
        "Elogios muy positivos al apartamento",
    ]
    assert result["n"].tolist() == [417, 376, 221]
    assert result["topic_id"].tolist() == [11, 12, 31]


def _chunks_df():
    return pd.DataFrame(
        [
            {
                "chunk_id": 1, "source": "booking_review", "text": "Precioso apartamento",
                "topic_id": 11, "municipio": "Adeje", "h3_index": "a",
                "fecha": "2025-01-10", "pais_resenante": "España", "rating": 9.0,
            },
            {
                "chunk_id": 2, "source": "tripadvisor_review", "text": "Great villa",
                "topic_id": 11, "municipio": "Adeje", "h3_index": "b",
                "fecha": "2025-03-01", "pais_resenante": "Reino Unido", "rating": 5.0,
            },
            {
                "chunk_id": 3, "source": "booking_review", "text": "Otro tema",
                "topic_id": 12, "municipio": "Adeje", "h3_index": "c",
                "fecha": "2025-02-15", "pais_resenante": "Francia", "rating": 8.0,
            },
            {
                "chunk_id": 4, "source": "booking_review", "text": "Villa en Arona",
                "topic_id": 11, "municipio": "Arona", "h3_index": "d",
                "fecha": "2025-01-20", "pais_resenante": "Italia", "rating": 10.0,
            },
        ]
    )


def test_sample_chunks_filters_by_municipio_and_topic():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert sorted(result["chunk_id"].tolist()) == [1, 2]


def test_sample_chunks_sorts_by_fecha_descending():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert result["chunk_id"].tolist() == [2, 1]


def test_sample_chunks_respects_n():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=1)
    assert len(result) == 1


def test_sample_chunks_maps_source_to_display_label():
    result = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    assert set(result["fuente"]) == {"Booking", "TripAdvisor"}


def _topicos_df():
    row = get_topicos_row(_topicos_municipio_df(), "Adeje")
    return top_topicos_dataframe(row)


def test_selected_topic_from_event_returns_none_when_no_event():
    assert selected_topic_from_event(None, _topicos_df()) is None


def test_selected_topic_from_event_returns_none_when_no_points():
    assert selected_topic_from_event({"selection": {"points": []}}, _topicos_df()) is None


def test_selected_topic_from_event_maps_clicked_label_to_topic_id():
    event = {"selection": {"points": [{"y": "Apartamentos pequeños tipo estudio (cocina, lavadora)"}]}}
    assert selected_topic_from_event(event, _topicos_df()) == 12


def test_selected_topic_from_event_returns_none_for_unknown_label():
    event = {"selection": {"points": [{"y": "no existe"}]}}
    assert selected_topic_from_event(event, _topicos_df()) is None


def test_prepare_review_cards_maps_source_to_icon_and_formats_fields():
    muestra = sample_chunks(_chunks_df(), "Adeje", 11, n=15)
    cards = prepare_review_cards(muestra)
    booking_card = next(c for c in cards if c["fuente"] == "Booking")
    assert booking_card["icono"] == "🅱️"
    assert booking_card["rating"] == 9.0
    assert booking_card["pais"] == "España"


def test_prepare_review_cards_handles_missing_rating():
    muestra = pd.DataFrame(
        [{"fuente": "Booking", "rating": None, "fecha": "2025-01-01", "pais_resenante": None, "text": "x"}]
    )
    cards = prepare_review_cards(muestra)
    assert cards[0]["rating"] is None
    assert cards[0]["pais"] == "—"
