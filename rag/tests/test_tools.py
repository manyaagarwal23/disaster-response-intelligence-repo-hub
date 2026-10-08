"""Pure helpers of the AI review and test-generation tools (no LLM calls)."""

from tools import ai_review, generate_tests


DIFF = """diff --git a/rag/a.py b/rag/a.py
--- a/rag/a.py
+++ b/rag/a.py
@@ -1 +1,2 @@
 x = 1
+y = 2
diff --git a/rag/b.py b/rag/b.py
--- a/rag/b.py
+++ b/rag/b.py
@@ -1 +1 @@
-z = 1
+z = 3
"""


def test_split_diff_keeps_whole_files_per_chunk():
    chunks = ai_review.split_diff(DIFF, max_chars=120)

    assert len(chunks) == 2
    assert chunks[0].startswith("diff --git a/rag/a.py")
    assert chunks[1].startswith("diff --git a/rag/b.py")
    assert ai_review.split_diff(DIFF, max_chars=10000) == [DIFF]


def test_split_diff_truncates_a_huge_file():
    huge = "diff --git a/x b/x\n" + "+" + "a" * 500 + "\n"
    chunks = ai_review.split_diff(huge, max_chars=100)

    assert len(chunks) == 1
    assert "[file diff truncated for review]" in chunks[0]


def test_parse_findings_accepts_json_with_reasoning_and_sorts_by_severity():
    reply = '<think>hmm</think>Here you go: [{"file": "a.py", "line": 3, "severity": "low", "issue": "x", "fix": "y"}, {"file": "b.py", "severity": "HIGH", "issue": "boom", "fix": "z"}]'

    findings = ai_review.parse_findings(reply)

    assert [f["severity"] for f in findings] == ["high", "low"]
    assert findings[0]["file"] == "b.py"
    assert ai_review.parse_findings("not json") is None
    assert ai_review.parse_findings("[]") == []


def test_render_review_mentions_every_finding():
    text = ai_review.render(
        [{"file": "a.py", "line": 3, "severity": "high", "issue": "bad", "fix": "good"}], "HEAD", ["a.py"]
    )
    assert "HIGH" in text and "`a.py`:3" in text and "good" in text
    assert "No risky patterns" in ai_review.render([], "HEAD", [])


SOURCE = '''import pytest
import chunking as m


def test_a():
    assert m.f(1) == 1


@pytest.mark.parametrize("x", [1])
def test_b(x):
    assert m.f(x) == x


def helper():
    return 3
'''


def test_drop_tests_removes_named_functions_including_decorators():
    kept = generate_tests.drop_tests(SOURCE, {"test_b"})

    assert "def test_b" not in kept and "parametrize" not in kept
    assert "def test_a" in kept and "def helper" in kept
    assert generate_tests.collected_tests(kept) == ["test_a"]


def test_failing_tests_parses_pytest_output():
    out = "FAILED tests/generated/test_gen_x.py::test_one - AssertionError\nFAILED tests/x.py::test_two\n1 passed"
    assert generate_tests.failing_tests(out) == {"test_one", "test_two"}


def test_safety_problems_blocks_dangerous_or_broken_tests():
    problems = generate_tests.safety_problems

    assert problems("import subprocess\n") == ["import subprocess"]
    assert problems("import subprocess as sp\n") == ["import subprocess"]
    assert problems("from os import system\n") == ["from os import ..."]
    assert problems("import chromadb\nimport torch\n") == ["import chromadb", "import torch"]
    assert problems("x = __import__('os')\n") == ["call to __import__()"]
    assert problems("import retrieval as m\nm.get_retriever()\n") == ["call to get_retriever()", "use of get_retriever"]
    assert any("syntax error" in p for p in problems("def test_(:\n"))
    # The project modules, pytest and the standard helpers are fine
    assert problems("import pytest\nimport re\nimport retrieval as m\nfrom pathlib import Path\n") == []
    assert problems(SOURCE) == []
