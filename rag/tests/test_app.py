import sys
import types

import pytest
from fastapi.testclient import TestClient

import app as app_module


class DatabaseNotReadyError(RuntimeError):
    pass


@pytest.fixture
def client():
    return TestClient(app_module.app)


@pytest.fixture
def fake_pipeline(monkeypatch):
    """
    Replace the heavy modules (chromadb + torch) that /api/ask imports
    lazily, so the API contract can be tested quickly.
    """

    rag_api = types.ModuleType("rag_api")
    retrieval = types.ModuleType("retrieval")
    retrieval.DatabaseNotReadyError = DatabaseNotReadyError

    monkeypatch.setitem(sys.modules, "rag_api", rag_api)
    monkeypatch.setitem(sys.modules, "retrieval", retrieval)

    return rag_api


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Disaster Response" in response.text


def test_static_files_are_served(client):
    assert client.get("/static/js/script.js").status_code == 200


def test_browsers_never_run_a_stale_script(client):
    # The script URL carries a version that changes with the file, and the
    # page + static files must be re-checked on every load
    page = client.get("/")
    version = app_module.asset_version()

    assert f"/static/js/script.js?v={version}" in page.text
    assert f"/static/css/style.css?v={version}" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert client.get("/static/js/script.js").headers["cache-control"] == "no-cache"


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_returns_pipeline_result(client, fake_pipeline):
    fake_pipeline.get_rag_answer = lambda question: {
        "answer": {"simple": f"echo: {question}"},
        "sources": [],
        "llm_used": True,
        "warning": None,
    }

    response = client.post("/api/ask", json={"question": "where is SMS parsed"})

    assert response.status_code == 200
    assert response.json()["answer"]["simple"] == "echo: where is SMS parsed"


def test_ask_reports_missing_database_as_503(client, fake_pipeline):
    def missing(question):
        raise DatabaseNotReadyError("Vector database not found. Build it with: python ingestion.py")

    fake_pipeline.get_rag_answer = missing

    response = client.post("/api/ask", json={"question": "anything"})

    assert response.status_code == 503
    assert "ingestion.py" in response.json()["error"]


def test_ask_reports_unexpected_errors_as_500(client, fake_pipeline):
    def broken(question):
        raise ValueError("boom")

    fake_pipeline.get_rag_answer = broken

    response = client.post("/api/ask", json={"question": "anything"})

    assert response.status_code == 500
    assert "boom" in response.json()["error"]


def test_ask_rejects_empty_question(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
