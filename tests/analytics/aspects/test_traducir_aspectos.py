import pytest
from unittest.mock import MagicMock

from analytics.aspects.traducir_aspectos import (
    es_traduccion_valida,
    traducir_aspecto,
    parse_args,
    MARCADORES_ERROR,
)


def test_es_traduccion_valida_correcta():
    assert es_traduccion_valida("limpieza") is True
    assert es_traduccion_valida("atención al cliente") is True


def test_es_traduccion_valida_vacio():
    assert es_traduccion_valida(None) is False
    assert es_traduccion_valida("") is False


def test_es_traduccion_valida_marcadores_error():
    assert es_traduccion_valida("Error 500: Server error") is False
    assert es_traduccion_valida("Please try again later") is False
    assert es_traduccion_valida("too many requests") is False


def test_es_traduccion_valida_muy_largo():
    assert es_traduccion_valida("a" * 205) is False


def test_traducir_aspecto_google_exitoso():
    mock_google = MagicMock()
    mock_google.return_value.translate.return_value = "ubicación"

    res, motor = traducir_aspecto(
        "location",
        google_cls=mock_google,
        mymemory_cls=None,
        detect_fn=None,
        email="test@example.com",
    )
    assert res == "ubicación"
    assert motor == "google"


def test_traducir_aspecto_fallback_mymemory():
    mock_google = MagicMock()
    mock_google.return_value.translate.side_effect = Exception("Rate limit")

    mock_mymemory = MagicMock()
    mock_mymemory.return_value.translate.return_value = "limpieza"

    mock_detect = MagicMock(return_value="en")

    res, motor = traducir_aspecto(
        "cleaning",
        google_cls=mock_google,
        mymemory_cls=mock_mymemory,
        detect_fn=mock_detect,
        email="test@example.com",
    )
    assert res == "limpieza"
    assert motor == "mymemory"


def test_traducir_aspecto_fallback_original():
    mock_google = MagicMock()
    mock_google.return_value.translate.side_effect = Exception("Error")

    mock_mymemory = MagicMock()
    mock_mymemory.return_value.translate.side_effect = Exception("Error")

    res, motor = traducir_aspecto(
        "Tenerife",
        google_cls=mock_google,
        mymemory_cls=mock_mymemory,
        detect_fn=None,
        email="test@example.com",
    )
    assert res == "tenerife"
    assert motor == "original_fallback"


def test_parse_args_defaults():
    import sys
    sys_argv_backup = sys.argv
    sys.argv = ["traducir_aspectos.py"]
    try:
        args = parse_args()
        assert args.limit is None
        assert args.batch_size == 20
        assert args.dry_run is False
    finally:
        sys.argv = sys_argv_backup
