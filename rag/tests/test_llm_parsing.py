import generator
import llm
from generator import build_answer_prompt, parse_answer
from llm import build_rerank_prompt, parse_rerank_order, strip_reasoning


RESULT = {
    "source": "src/A.php",
    "namespace": "N",
    "class": "A",
    "method": "run",
    "type": "method",
    "start_line": 3,
    "end_line": 9,
    "content": "x" * 5000,
}


def test_strip_reasoning_removes_think_block():
    assert strip_reasoning("<think>result 7 looks best</think>\n2, 1") == "2, 1"
    assert strip_reasoning("<think>cut off mid thought 4, 5") == ""


def test_rerank_order_ignores_numbers_in_reasoning():
    reply = "<think>Result 7 mentions line 42 but result 2 is better</think>\n2, 1, 3"
    assert parse_rerank_order(reply) == [2, 1, 3]


def test_rerank_order_uses_last_line_only():
    assert parse_rerank_order("Here is the ranking for 10 results:\n4, 1, 7") == [4, 1, 7]
    assert parse_rerank_order("") == []


def test_rerank_prompt_truncates_code():
    prompt = build_rerank_prompt("q", [RESULT])
    assert "RESULT 1" in prompt
    assert "x" * (llm.RERANK_PREVIEW_CHARS + 1) not in prompt


def test_parse_answer_valid_json_with_fences_and_reasoning():
    reply = '<think>hmm</think>```json\n{"simple": "S", "technical": "T", "diagram_type": "mermaid", "diagram_code": "graph TD; A-->B"}\n```'

    answer = parse_answer(reply)

    assert answer == {
        "simple": "S",
        "technical": "T",
        "diagram_type": "mermaid",
        "diagram_code": "graph TD; A-->B",
    }


def test_parse_answer_drops_diagram_type_without_code():
    answer = parse_answer('{"simple": "S", "technical": "T", "diagram_type": "mermaid", "diagram_code": null}')
    assert answer["diagram_type"] is None


def test_parse_answer_falls_back_to_plain_text():
    answer = parse_answer("Sorry, plain text answer.")
    assert answer["simple"] == "Sorry, plain text answer."
    assert answer["diagram_type"] is None


def test_answer_prompt_truncates_and_cites_lines():
    prompt = build_answer_prompt("q", [RESULT])
    assert "src/A.php (lines 3-9)" in prompt
    assert "[CONTENT TRUNCATED FOR SIZE]" in prompt


def test_no_api_key_means_no_llm(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    assert llm.get_llm() is None
    assert llm.rerank("q", [RESULT]) is None
    assert generator.generate_answer("q", [RESULT]) is None
