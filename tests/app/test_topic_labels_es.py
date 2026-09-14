from app.topic_labels_es import TOPIC_LABELS_ES, topic_label_es


def test_topic_label_es_returns_curated_label_when_known():
    assert topic_label_es(67, "sendero, senderos, teleférico, pico viejo, miradores, pico") == (
        "Senderismo: teleférico del Teide y miradores"
    )


def test_topic_label_es_falls_back_to_raw_label_when_unknown():
    assert topic_label_es(999999, "unknown, raw, keywords") == "unknown, raw, keywords"


def test_topic_labels_es_has_56_curated_entries():
    assert len(TOPIC_LABELS_ES) == 56


def test_topic_labels_es_has_no_empty_values():
    assert all(isinstance(v, str) and v.strip() for v in TOPIC_LABELS_ES.values())
