"""
Auto-generate regression tests (CodiumAI-style safety net).

For each Python module given, the LLM writes pytest tests for the
module's pure functions. The tests are run immediately; failing tests
are sent back to the LLM once for repair, and anything still failing is
removed. Only tests that pass against the CURRENT code are kept, so they
act as a regression net for future (rushed) changes. Generated files are
written to tests/generated/ and picked up by the normal `pytest` run.

Usage (from rag/):
    python tools/generate_tests.py retrieval.py chunking.py
    python tools/generate_tests.py --changed          # modules changed vs origin/main
    python tools/generate_tests.py --all              # every pure module

Needs GROQ_API_KEY. Without it the script explains and exits 0, so CI
jobs that run it never fail just because the secret is absent.
"""

import argparse
import ast
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(RAG_DIR))

import config  # noqa: E402
from llm import LLMRequestError, get_llm, invoke_with_retry, strip_reasoning  # noqa: E402


OUT_DIR = RAG_DIR / "tests" / "generated"

REPORTS_DIR = config.PROJECT_DIR / "reports"

# Modules whose functions can be tested without ChromaDB, torch or Groq
PURE_MODULES = [
    "php_extractor.py",
    "chunking.py",
    "retrieval.py",
    "llm.py",
    "generator.py",
    "evaluate.py",
    "rag_api.py",
]

# Generated tests must never touch the network, other files or heavy libs:
# only these imports are allowed (checked on the parsed AST, so aliases
# and `from x import y` cannot slip through)
ALLOWED_IMPORTS = {
    "pytest", "re", "json", "math", "datetime", "pathlib", "typing", "collections",
    "itertools", "functools", "string", "textwrap", "copy", "dataclasses", "enum",
    "unittest", "unittest.mock",
    # project modules that are safe to import
    "config", "php_extractor", "chunking", "retrieval", "llm", "generator", "evaluate", "rag_api",
}

# Calls that would let a test escape the sandbox even without an import
FORBIDDEN_CALLS = {"__import__", "exec", "eval", "compile", "open", "getattr", "globals", "vars"}

# Names that must not appear even as attributes (e.g. os.system via a helper)
FORBIDDEN_NAMES = {"get_retriever", "Retriever", "ingestion", "importlib", "subprocess", "socket"}

# Keeps one prompt under Groq's free-tier 7,000 tokens-per-minute budget
MAX_SOURCE_CHARS = 14000


PROMPT = """You are writing pytest regression tests for a Python module in a RAG
code-search project. The tests must pass against the module EXACTLY as it is
now; their purpose is to catch future regressions.

Rules:
- Test only pure functions: no network, no ChromaDB, no torch, no LLM calls,
  no files except pytest's tmp_path. Do not instantiate Retriever or call
  get_retriever / ingestion.
- Import the module as `import {module} as m` (it is on sys.path) and call
  functions through `m.`.
- Each test must assert concrete, correct values derived from the code.
  Do not write tautologies (e.g. `assert f(x) == f(x)`) and do not skip.
- 5 to 8 short, focused tests (the whole file under 70 lines), plain
  functions named test_*, no classes, no fixtures other than tmp_path and
  monkeypatch, no external packages besides pytest.
- Output ONLY the Python file content. No markdown fences, no prose.

MODULE {module}.py:
```python
{source}
```
"""

REPAIR_PROMPT = """The generated tests below were run and some failed. Fix ONLY the failing
tests so that they pass against the module as it is (the module is correct;
the test expectations were wrong). Keep every passing test unchanged. Output
ONLY the complete Python file content, no markdown fences.

PYTEST OUTPUT:
{failures}

TEST FILE:
```python
{tests}
```
"""


def ask(llm, prompt):
    """LLM reply as a Python file body, or None if the request failed."""

    try:

        reply = invoke_with_retry(llm, prompt)

    except LLMRequestError as error:

        print(f"  {error}")

        return None

    text = strip_reasoning(reply)

    text = re.sub(r"^\s*```(?:python)?\s*", "", text)

    return re.sub(r"\s*```\s*$", "", text).strip() + "\n"


def changed_modules(base):

    diff = subprocess.run(
        ["git", "diff", "--name-only", base, "--", "rag/*.py"],
        capture_output=True, text=True, cwd=config.PROJECT_DIR,
    ).stdout.split()

    names = {Path(p).name for p in diff}

    return [m for m in PURE_MODULES if m in names]


def run_pytest(path):

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", "-p", "no:warnings"],
        capture_output=True, text=True, cwd=RAG_DIR, timeout=180,
    )

    return result.returncode == 0, result.stdout + result.stderr


def failing_tests(output):

    return set(re.findall(r"FAILED .*?::(test_\w+)", output))


def collected_tests(source):

    tree = ast.parse(source)

    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


def drop_tests(source, names):
    """Remove the named top-level test functions from a test file."""

    tree = ast.parse(source)

    lines = source.splitlines(keepends=True)

    for node in reversed(tree.body):

        if isinstance(node, ast.FunctionDef) and node.name in names:

            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1

            del lines[start:node.end_lineno]

    return "".join(lines)


def safety_problems(source):
    """
    Reasons a generated test file must be rejected: syntax errors,
    imports outside the allow-list, or calls that could escape the
    sandbox. Works on the AST, so `import subprocess as sp` or
    `__import__("os")` are caught just like plain imports.
    """

    try:

        tree = ast.parse(source)

    except SyntaxError as error:

        return [f"syntax error: {error}"]

    found = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                if alias.name not in ALLOWED_IMPORTS and alias.name.split(".")[0] not in ALLOWED_IMPORTS:

                    found.append(f"import {alias.name}")

        elif isinstance(node, ast.ImportFrom):

            module = node.module or ""

            if module not in ALLOWED_IMPORTS and module.split(".")[0] not in ALLOWED_IMPORTS:

                found.append(f"from {module} import ...")

        elif isinstance(node, ast.Call):

            callee = node.func

            name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")

            if name in FORBIDDEN_CALLS or name in FORBIDDEN_NAMES:

                found.append(f"call to {name}()")

        elif isinstance(node, (ast.Name, ast.Attribute)):

            name = node.id if isinstance(node, ast.Name) else node.attr

            if name in FORBIDDEN_NAMES:

                found.append(f"use of {name}")

    return sorted(set(found))


def generate_for(llm, module, log):

    name = module[:-3]

    source = (RAG_DIR / module).read_text(encoding="utf-8")

    if len(source) > MAX_SOURCE_CHARS:

        # The LLM only sees the first part; tests on unseen functions
        # simply fail at run time and are dropped like any other
        log(f"- `{module}`: {len(source)} chars, only the first {MAX_SOURCE_CHARS} shown to the LLM")

        source = source[:MAX_SOURCE_CHARS]

    tests = ask(llm, PROMPT.format(module=name, source=source))

    if tests is None:

        log(f"- `{module}`: LLM request failed, skipped")

        return 0, 0

    problems = safety_problems(tests)

    if problems:

        log(f"- `{module}`: rejected generated file ({', '.join(problems)})")

        return 0, 0

    path = OUT_DIR / f"test_gen_{name}.py"

    header = (
        f"# AUTO-GENERATED by tools/generate_tests.py from {module}\n"
        f"# on {datetime.date.today()} with {config.GROQ_MODEL}. Regression safety net:\n"
        f"# every test here passed against the code at generation time.\n"
        f"# Review before trusting; regenerate after intentional behaviour changes.\n\n"
    )

    path.write_text(header + tests, encoding="utf-8")

    total = len(collected_tests(tests))

    ok, output = run_pytest(path)

    if not ok:

        # One repair round, then drop whatever still fails
        repaired = ask(llm, REPAIR_PROMPT.format(failures=output[-4000:], tests=tests))

        if repaired is not None and not safety_problems(repaired):

            tests = repaired

            path.write_text(header + tests, encoding="utf-8")

            ok, output = run_pytest(path)

    if not ok:

        bad = failing_tests(output)

        if not bad:

            # Collection error (import/syntax): nothing can be salvaged
            path.unlink(missing_ok=True)

            log(f"- `{module}`: generated file could not be collected, discarded")

            return total, 0

        tests = drop_tests(tests, bad)

        path.write_text(header + tests, encoding="utf-8")

        ok, output = run_pytest(path)

    kept = len(collected_tests(path.read_text(encoding="utf-8"))) if path.exists() else 0

    if not ok or kept == 0:

        path.unlink(missing_ok=True)

        log(f"- `{module}`: no passing tests could be generated, discarded")

        return total, 0

    log(f"- `{module}`: kept **{kept}** of {total} generated tests -> `tests/generated/{path.name}`")

    return total, kept


def main():

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("modules", nargs="*", help="module files in rag/ (e.g. retrieval.py)")

    parser.add_argument("--all", action="store_true", help="generate for every pure module")

    parser.add_argument("--changed", action="store_true", help="only modules changed vs --base")

    parser.add_argument("--base", default="origin/main", help="git ref for --changed (default origin/main)")

    args = parser.parse_args()

    if args.all:

        modules = PURE_MODULES

    elif args.changed:

        modules = changed_modules(args.base)

    else:

        modules = [m for m in args.modules if m in PURE_MODULES]

    if not modules:

        print("No pure modules selected (nothing changed, or unknown module names).")

        return

    # ~900 output tokens keeps each reply inside Groq's free-tier budget
    llm = get_llm(max_tokens=900)

    if llm is None:

        print("GROQ_API_KEY is not set: skipping test generation (nothing to do).")

        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "__init__.py").touch()

    lines = [
        f"# Generated regression tests — {datetime.datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Model `{config.GROQ_MODEL}`. Only tests that pass against the current code are kept.",
        "",
    ]

    def log(line):

        print(line)

        lines.append(line)

    total = kept = 0

    for module in modules:

        t, k = generate_for(llm, module, log)

        total += t

        kept += k

    lines += ["", f"**Total: kept {kept} of {total} generated tests.**", ""]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = REPORTS_DIR / f"generated-tests-{datetime.date.today()}.md"

    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReport written to {report}")

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):

        with open(summary, "a", encoding="utf-8") as file:

            file.write("\n".join(lines))


if __name__ == "__main__":

    main()
