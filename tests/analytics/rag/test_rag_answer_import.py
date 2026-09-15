import importlib


def test_rag_answer_importable_as_dotted_module():
    # Regression test: analytics/rag/rag_answer.py used to only work when run
    # directly as a script (python analytics/rag/rag_answer.py), because
    # Python auto-adds a script's own directory to sys.path only when it's
    # __main__. Importing it as analytics.rag.rag_answer (the way
    # app/asistente.py needs to) raised ModuleNotFoundError: No module named
    # 'filtros', since filtros.py and retriever.py live next to it in
    # analytics/rag/ and were only reachable via that automatic path.
    modulo = importlib.import_module("analytics.rag.rag_answer")
    assert callable(modulo.responder)
