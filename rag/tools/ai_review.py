"""
AI review of a change set (Sweep-style safety net for rushed commits).

Reads the git diff, asks the LLM to flag risky patterns a reviewer would
catch - bugs, unhandled errors, security holes, removed tests, blocking
calls, hardcoded paths/secrets - and writes a Markdown report with a
suggested fix for every finding. In CI (`--post`) the report is also
posted as a pull-request comment.

Usage (from anywhere in the repo):
    python rag/tools/ai_review.py                 # working tree vs HEAD
    python rag/tools/ai_review.py --base origin/main
    python rag/tools/ai_review.py --base origin/main --post   # in CI

Advisory by default (exit code 0). Use --fail-on high to block merges
when a high-severity finding is reported. Without GROQ_API_KEY the
script explains and exits 0.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(RAG_DIR))

import config  # noqa: E402
import time  # noqa: E402

from llm import LLMRequestError, get_llm, invoke_with_retry, strip_reasoning  # noqa: E402


REPORTS_DIR = config.PROJECT_DIR / "reports"

REVIEWED_GLOBS = ["*.py", "*.js", "*.html", "*.css", "*.yml", "*.yaml", "*.sh", "Dockerfile"]

# One review request stays under Groq's free-tier 7,000 tokens-per-minute
# budget; bigger diffs are reviewed file by file with a pause in between.
MAX_CHUNK_CHARS = 16000

PAUSE_BETWEEN_CHUNKS = 20

SEVERITIES = ["high", "medium", "low"]


PROMPT = """You are reviewing a code change for an open-source disaster-response
platform tool. Changes here are often made in a hurry during a crisis, so
look specifically for things that would break production or hurt users:

- bugs and logic errors, wrong edge cases
- unhandled exceptions, missing error paths, silent failures
- security: XSS/HTML injection, command or SQL injection, secrets in code,
  unsafe deserialization, path traversal
- blocking or slow calls on hot paths, resource leaks
- tests deleted or weakened, assertions removed
- hardcoded paths, ports or credentials
- behaviour that differs between Windows/Linux

Ignore style, naming and formatting. Only report real risks you can point to
in the diff. If the change looks safe, return an empty list.

Return ONLY a JSON array (no prose, no markdown fences). Each item:
{{"file": "path", "line": <line number in the NEW file or null>,
  "severity": "high" | "medium" | "low",
  "issue": "one or two sentences", "fix": "concrete suggested fix"}}

DIFF:
{diff}
"""


def git(*args):

    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=config.PROJECT_DIR).stdout


def get_diff(base):

    return git("diff", base, "--", *REVIEWED_GLOBS, *[f"**/{g}" for g in REVIEWED_GLOBS])


def split_diff(diff, max_chars=MAX_CHUNK_CHARS):
    """
    Split a unified diff into chunks of whole files that fit the token
    budget. A single file bigger than the budget is truncated.
    """

    files = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)

    chunks, current = [], ""

    for part in files:

        if not part.strip():

            continue

        if len(part) > max_chars:

            part = part[:max_chars] + "\n... [file diff truncated for review] ...\n"

        if current and len(current) + len(part) > max_chars:

            chunks.append(current)

            current = ""

        current += part

    if current:

        chunks.append(current)

    return chunks


def parse_findings(text):

    text = strip_reasoning(text)

    match = re.search(r"\[.*\]", text, re.DOTALL)

    try:

        items = json.loads(match.group(0) if match else text)

    except ValueError:

        return None

    findings = []

    for item in items if isinstance(items, list) else []:

        if not isinstance(item, dict) or not item.get("issue"):

            continue

        severity = str(item.get("severity", "low")).lower()

        findings.append({
            "file": str(item.get("file", "?")),
            "line": item.get("line"),
            "severity": severity if severity in SEVERITIES else "low",
            "issue": str(item["issue"]),
            "fix": str(item.get("fix", "")),
        })

    return sorted(findings, key=lambda f: SEVERITIES.index(f["severity"]))


def render(findings, base, files):

    icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}

    lines = [
        f"## 🤖 AI review of changes vs `{base}`",
        "",
        f"{len(files)} file(s) reviewed with `{config.GROQ_MODEL}` on {datetime.date.today()}. "
        "Advisory: a human still decides.",
        "",
    ]

    if not findings:

        lines.append("No risky patterns found. ✅")

    for f in findings:

        where = f"`{f['file']}`" + (f":{f['line']}" if f["line"] else "")

        lines += [
            f"### {icon[f['severity']]} {f['severity'].upper()} — {where}",
            "",
            f"**Issue:** {f['issue']}",
            "",
            f"**Suggested fix:** {f['fix']}",
            "",
        ]

    return "\n".join(lines) + "\n"


def main():

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--base", default="HEAD", help="git ref to diff the working tree against")

    parser.add_argument("--output", help="markdown report path (default reports/ai-review-<date>.md)")

    parser.add_argument("--post", action="store_true", help="also post as a PR comment (needs gh + GH_TOKEN)")

    parser.add_argument("--fail-on", choices=SEVERITIES, help="exit 1 if a finding of this severity or worse exists")

    args = parser.parse_args()

    diff = get_diff(args.base)

    files = [line[6:] for line in diff.splitlines() if line.startswith("+++ b/")]

    if not diff.strip():

        print(f"No reviewable changes vs {args.base}.")

        return

    llm = get_llm(max_tokens=900)

    if llm is None:

        print("GROQ_API_KEY is not set: skipping AI review.")

        return

    findings = []

    chunks = split_diff(diff)

    for i, chunk in enumerate(chunks, 1):

        if i > 1:

            time.sleep(PAUSE_BETWEEN_CHUNKS)

        print(f"reviewing part {i}/{len(chunks)} ({len(chunk)} chars)...")

        try:

            reply = invoke_with_retry(llm, PROMPT.format(diff=chunk))

        except LLMRequestError as error:

            print(f"  {error}")

            reply = None

        parsed = parse_findings(reply) if reply is not None else None

        if parsed is None:

            print("  no usable review for this part (request failed or reply not JSON)")

            continue

        findings.extend(parsed)

    findings.sort(key=lambda f: SEVERITIES.index(f["severity"]))

    report = render(findings, args.base, files)

    print(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    output = Path(args.output) if args.output else REPORTS_DIR / f"ai-review-{datetime.date.today()}.md"

    output.write_text(report, encoding="utf-8")

    print(f"Report written to {output}")

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):

        with open(summary, "a", encoding="utf-8") as file:

            file.write(report)

    if args.post and os.environ.get("PR_NUMBER"):

        subprocess.run(["gh", "pr", "comment", os.environ["PR_NUMBER"], "--body-file", str(output)], check=False)

    if args.fail_on:

        worst = min((SEVERITIES.index(f["severity"]) for f in findings), default=len(SEVERITIES))

        if worst <= SEVERITIES.index(args.fail_on):

            sys.exit(1)


if __name__ == "__main__":

    main()
