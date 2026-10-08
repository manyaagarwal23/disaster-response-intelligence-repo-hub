"""
End-to-end test: build a real ChromaDB from the fixture repository
with the real embedding model, then query it.

Needs chromadb + sentence-transformers + the BGE model, so it is
skipped by default and runs inside the Docker image in CI:
    pytest -m integration
"""

import pytest

import config


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def retriever(tmp_path_factory, request):
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")

    import ingestion
    import retrieval

    patch = pytest.MonkeyPatch()
    patch.setattr(config, "REPO_PATH", request.config.rootpath / "tests" / "fixtures" / "sample_repo")
    patch.setattr(config, "CHROMA_PATH", tmp_path_factory.mktemp("chroma"))
    for name in ("GROQ_API_KEY", "GROQ_API_KEYS", "OLLAMA_MODEL"):
        patch.delenv(name, raising=False)
    patch.setattr(retrieval, "_retriever", None)

    ingestion.main()

    yield retrieval.get_retriever()

    patch.undo()


def test_database_contains_code_routes_and_docs(retriever):
    metadata = retriever.collection.get(include=["metadatas"])["metadatas"]
    types = {m["type"] for m in metadata}

    assert {"method", "file", "doc"} <= types
    assert retriever.collection.metadata["hnsw:space"] == "cosine"


def test_reingestion_does_not_duplicate_or_break_running_server(retriever):
    import ingestion

    before = retriever.collection.count()
    ingestion.main()

    # The already-running retriever must reconnect to the rebuilt
    # collection instead of failing every request until a restart
    results = retriever.search("EntityExists contract", use_llm=False)

    assert results["final"]
    assert retriever.collection.count() == before


@pytest.mark.parametrize("question, expected_source", [
    ("Where is the EntityExists contract defined?", "src/Ushahidi/Contracts/EntityExists.php"),
    ("Where is an incoming SMS from Twilio handled?", "src/Ushahidi/DataSource/Twilio/TwilioController.php"),
    ("Which API route updates a post?", "routes/api.php"),
    ("What exception is thrown when an entity cannot be found?",
     "src/Ushahidi/Core/Usecase/Concerns/VerifyEntityLoaded.php"),
])
def test_questions_retrieve_the_right_file(retriever, question, expected_source):
    result = retriever.search(question, use_llm=False)

    top_sources = [r["source"] for r in result["final"][:2]]

    assert expected_source in top_sources
    assert result["llm_used"] is False


def test_instant_code_search_and_stats(retriever):
    from rag_api import get_stats, search_code

    result = search_code("twilio sms webhook", k=3)

    assert len(result["results"]) == 3
    # Both the controller and the doc section describing the webhook are
    # correct hits; the controller must be near the top either way.
    files = [r["file"] for r in result["results"]]
    assert "src/Ushahidi/DataSource/Twilio/TwilioController.php" in files
    assert result["timings"]["rerank_ms"] == 0          # no LLM involved
    assert result["timings"]["retrieval_ms"] < 5000

    stats = get_stats()
    assert stats["chunks"] == retriever.collection.count()
    assert {"method", "file", "doc"} <= set(stats["by_type"])
    assert stats["llm_configured"] is False


def test_rag_answer_without_llm_returns_real_sources(retriever):
    from rag_api import get_rag_answer

    response = get_rag_answer("Where is the EntityExists contract defined?")

    assert response["answer"] is None
    assert response["llm_used"] is False
    assert "GROQ_API_KEY" in response["warning"]
    assert response["sources"][0]["file"] == "src/Ushahidi/Contracts/EntityExists.php"
    assert response["sources"][0]["start_line"] >= 1
