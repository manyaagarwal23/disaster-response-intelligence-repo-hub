import json

import pytest
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
    for name in ("GROQ_API_KEY", "GROQ_API_KEYS", "OLLAMA_MODEL"):
        monkeypatch.delenv(name, raising=False)

    assert llm.get_llm() is None
    assert llm.rerank("q", [RESULT]) is None
    assert generator.generate_answer("q", [RESULT]) is None


def test_retry_hint_parsing():
    msg = "Rate limit reached ... Limit 1000, Used 377, Requested 668. Please try again in 2.699999999s. Need more"
    assert llm.retry_after_seconds(msg) == pytest.approx(2.7, abs=0.01)
    assert llm.retry_after_seconds("try again in 350ms") == pytest.approx(0.35)
    assert llm.retry_after_seconds("no hint here") is None
    assert llm.is_rate_limit(msg) and not llm.is_rate_limit("connection refused")
    # Budget partly used: worth retrying. Single prompt over the limit: not.
    assert llm.prompt_too_large(msg) is False
    assert llm.prompt_too_large("413 ... on input tokens per minute (ITPM): Limit 7000, Requested 13209") is True


def test_invoke_with_retry_waits_then_succeeds(monkeypatch):
    class Reply:
        content = "2, 1"

    class FlakyLLM:
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Error code: 429 - rate_limit_exceeded ... Please try again in 0.01s")
            return Reply()

    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    flaky = FlakyLLM()

    assert llm.invoke_with_retry(flaky, "p", attempts=3, max_wait=5) == "2, 1"
    assert flaky.calls == 2


def test_invoke_with_retry_gives_up(monkeypatch):
    class DeadLLM:
        def invoke(self, messages):
            raise RuntimeError("Error code: 429 - rate_limit_exceeded. Please try again in 0.01s")

    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    with pytest.raises(llm.LLMRequestError):
        llm.invoke_with_retry(DeadLLM(), "p", attempts=2)


# ---- key chain + local fallback ------------------------------------------

class _Reply:
    def __init__(self, content):
        self.content = content


class _Key:
    """Fake ChatGroq client: raises the configured error or answers."""

    def __init__(self, error=None, answer="ok"):
        self.error, self.answer, self.calls = error, answer, 0

    def invoke(self, prompt):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return _Reply(self.answer)


RATE_LIMITED = "Error code: 429 - rate_limit_exceeded ... Please try again in 2.5s"


def make_client(*keys, ollama=""):
    client = llm.LLMClient(["k%d" % i for i in range(len(keys))], ollama_model=ollama)
    client.clients = list(keys)
    return client


def test_keys_are_tried_in_order_and_the_first_working_one_answers(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    k1, k2, k3 = _Key(RATE_LIMITED), _Key(answer="from key 2"), _Key(answer="from key 3")
    client = make_client(k1, k2, k3)

    assert client.complete("p") == "from key 2"
    assert client.last_provider == "groq#2"
    assert (k1.calls, k2.calls, k3.calls) == (1, 1, 0)

    # the next request starts again at key 1 (its limit may have cleared)
    k1.error = None
    k1.answer = "from key 1"
    assert client.complete("p") == "from key 1" and client.last_provider == "groq#1"


def test_rejected_key_is_skipped_for_the_rest_of_the_process(monkeypatch):
    k1, k2 = _Key("Error code: 401 - invalid_api_key"), _Key(answer="two")
    client = make_client(k1, k2)

    assert client.complete("p") == "two"
    assert client.complete("p") == "two"
    assert k1.calls == 1 and 0 in client.dead


def test_all_keys_exhausted_falls_back_to_local_model(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(llm, "ollama_complete", lambda prompt, max_tokens=None, model=None, **kw: calls.append((prompt, model)) or "local answer")
    client = make_client(_Key(RATE_LIMITED), _Key(RATE_LIMITED), ollama="llama3.2:3b")

    assert client.complete("p", attempts=2) == "local answer"
    assert client.last_provider == "ollama:llama3.2:3b"
    assert calls == [("p", "llama3.2:3b")]


def test_short_hint_waits_once_before_falling_back(monkeypatch):
    waits = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: waits.append(s))
    k1 = _Key(RATE_LIMITED)
    client = make_client(k1, ollama="llama3.2:3b")
    monkeypatch.setattr(llm, "ollama_complete", lambda *a, **k: "local")

    # first pass limited (hint 2.5 s) -> wait -> second pass: key works again
    def flaky(prompt):
        k1.calls += 1
        if k1.calls == 1:
            raise RuntimeError(RATE_LIMITED)
        return _Reply("groq again")
    k1.invoke = flaky

    assert client.complete("p", attempts=2) == "groq again"
    assert waits == [3.0] and client.last_provider == "groq#1"


def test_rerank_never_uses_the_local_model(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm, "ollama_complete", lambda *a, **k: pytest.fail("local model must not rerank"))
    client = make_client(_Key(RATE_LIMITED), ollama="llama3.2:3b")

    with pytest.raises(llm.LLMRequestError):
        client.complete("p", attempts=1, fallback=False)


def test_no_keys_and_no_local_model_raises():
    with pytest.raises(llm.LLMRequestError):
        llm.LLMClient([], ollama_model="").complete("p")


def test_get_llm_reads_the_ordered_key_list(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEYS", "gsk_a, gsk_b ,gsk_c")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    client = llm.get_llm(max_tokens=50)

    assert client.api_keys == ["gsk_a", "gsk_b", "gsk_c"]
    assert client.ollama_model == "llama3.2:3b" and client.max_tokens == 50


def test_ollama_request_shape(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"message": {"role": "assistant", "content": "hi"}}'

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    assert llm.ollama_complete("hello", max_tokens=77, model="llama3.2:3b", host="http://h:11434/", timeout=9) == "hi"
    assert captured["url"] == "http://h:11434/api/chat" and captured["timeout"] == 9
    assert captured["body"]["model"] == "llama3.2:3b" and captured["body"]["options"]["num_predict"] == 77
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}] and captured["body"]["stream"] is False


# ---- local fallback answers -----------------------------------------------

GARBAGE = "TSA withinphonhaus底 cold ColdColdWithinwithin Within within within within within within within within"


def test_degenerate_local_output_is_detected():
    assert generator.looks_degenerate(GARBAGE)                      # the junk seen on the dev VM
    assert generator.looks_degenerate("ok")                         # too short
    assert generator.looks_degenerate("的的的 这是 一个 测试 句子 很好")    # mostly non-Latin
    assert not generator.looks_degenerate(
        "Incoming SMS reports are parsed in SMSSyncController::incoming, which reads the "
        "message and from fields and hands them to the data source."
    )


def test_local_prompt_is_compact():
    big = dict(RESULT, content="x" * 5000)
    prompt = generator.build_local_prompt("Where is SMS parsed?", [big, big, big])

    assert prompt.count("CODE ") == generator.LOCAL_CONTEXT_CHUNKS
    assert "x" * (generator.LOCAL_CONTEXT_CHARS + 1) not in prompt
    assert len(prompt) < 2500 and "QUESTION: Where is SMS parsed?" in prompt


def test_client_sends_the_local_prompt_to_the_local_model(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    seen = []
    monkeypatch.setattr(llm, "ollama_complete", lambda prompt, max_tokens=None, model=None, **kw: seen.append((prompt, max_tokens)) or "local")
    client = make_client(_Key(RATE_LIMITED), ollama="llama3.2:3b")

    assert client.complete("big prompt", attempts=1, local_prompt="small prompt", local_max_tokens=160) == "local"
    assert seen == [("small prompt", 160)]


def test_generate_answer_wraps_local_text_and_rejects_junk(monkeypatch):
    class LocalOnly:
        api_keys, ollama_model, last_provider = [], "llama3.2:3b", "ollama:llama3.2:3b"

        def __init__(self, text):
            self.text = text

        def complete(self, prompt, **kwargs):
            assert kwargs["local_prompt"].startswith("You are a codebase assistant")
            return self.text

    good = "SMS reports are parsed in SMSSyncController::incoming in the SMSSync data source."
    monkeypatch.setattr(generator, "get_llm", lambda: LocalOnly(good))
    answer = generator.generate_answer("q", [RESULT])
    assert answer == {"simple": good, "technical": "", "diagram_type": None, "diagram_code": None}

    monkeypatch.setattr(generator, "get_llm", lambda: LocalOnly(GARBAGE))
    with pytest.raises(generator.GenerationError, match="unusable text"):
        generator.generate_answer("q", [RESULT])
