import rag_api
from rag_api import build_fallback_diagram, mermaid_label, search_code


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, question, use_llm=True):
        self.calls.append((question, use_llm))
        hit = {
            "source": "src/A.php", "start_line": 1, "end_line": 9, "class": "A",
            "method": "run", "type": "method", "score": 0.91, "content": "code",
        }
        return {"semantic": [hit], "hybrid": [hit] * 3, "final": [hit],
                "llm_used": False, "timings": {"retrieval_ms": 12, "rerank_ms": 0}}


def test_search_code_skips_llm_and_limits_results(monkeypatch):
    fake = FakeRetriever()
    monkeypatch.setattr(rag_api, "get_retriever", lambda: fake)

    out = search_code("where is sms parsed", k=2)

    assert fake.calls == [("where is sms parsed", False)]
    assert len(out["results"]) == 2
    assert out["results"][0]["file"] == "src/A.php"
    assert out["timings"]["retrieval_ms"] == 12

    # k is clamped to the allowed range
    assert len(search_code("x", k=0)["results"]) == 1


RESULTS = [
    {"class": "TwilioController", "method": "handleRequest", "type": "method",
     "source": "src/Ushahidi/DataSource/Twilio/TwilioController.php", "start_line": 17},
    {"class": "", "method": "", "type": "file", "source": "routes/api.php", "start_line": 1},
]


def test_fallback_diagram_lists_retrieved_units_and_files():
    code = build_fallback_diagram(RESULTS)

    assert code.startswith("graph TD")
    assert '["TwilioController::handleRequest"]' in code
    assert '["TwilioController.php:17"]' in code
    # A whole-file chunk has no class/method, so its type is used
    assert '["file"]' in code
    assert '["api.php:1"]' in code


def test_mermaid_label_removes_characters_that_break_quoted_labels():
    assert mermaid_label('say "hi" <b>') == "say 'hi' b"
    assert len(mermaid_label("x" * 200)) == 60
    assert mermaid_label(None) == ""
