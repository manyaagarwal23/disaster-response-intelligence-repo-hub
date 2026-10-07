from rag_api import build_fallback_diagram, mermaid_label


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
