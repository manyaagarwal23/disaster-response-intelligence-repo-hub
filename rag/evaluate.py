"""
Retrieval evaluation against a ground-truth dataset (eval/questions.json).

For every question we know which Ushahidi files contain the answer.
We then check where the first correct file appears in each ranking:

  semantic - vector search only (the baseline)
  hybrid   - vector search + identifier/code/structural scoring
  llm      - hybrid + Groq LLM reranking (only when a Groq key is set)

Metrics (computed over the top K = 10 results):
  MRR@10 - mean of 1/rank of the first correct result (0 if not found)
  Hit@k  - % of questions with a correct result in the top k
  latency - wall-clock seconds per question (the brief asks for < 1 min)

Every run is saved under reports/eval/ (JSON with per-question detail
plus a Markdown summary), so results are never lost.

Usage:
    python evaluate.py               # semantic + hybrid (+ llm if key set)
    python evaluate.py --no-llm      # skip the LLM even if a key is set
    python evaluate.py --output path/to/results.json
"""

import argparse
import datetime
import json
import time
from pathlib import Path

import config


K = 10

HIT_LEVELS = (1, 3, 5)

QUESTIONS_FILE = config.RAG_DIR / "eval" / "questions.json"

REPORTS_DIR = config.PROJECT_DIR / "reports" / "eval"


# ============================================================
# Metric helpers (pure functions, unit-tested)
# ============================================================

def first_relevant_rank(results, relevant, k=K):
    """1-based rank of the first result whose source is relevant, else None."""

    relevant = set(relevant)

    for rank, result in enumerate(results[:k], 1):

        if result["source"] in relevant:

            return rank

    return None


def summarize(ranks):
    """Aggregate a list of ranks (None = not found) into MRR and Hit@k."""

    total = len(ranks)

    if total == 0:

        return {"queries": 0, "mrr": 0.0, **{f"hit@{n}": 0.0 for n in HIT_LEVELS}}

    summary = {
        "queries": total,
        "mrr": sum(1.0 / r for r in ranks if r) / total,
    }

    for n in HIT_LEVELS:

        summary[f"hit@{n}"] = 100.0 * sum(1 for r in ranks if r and r <= n) / total

    return summary


def load_questions(path=QUESTIONS_FILE):

    with open(path, encoding="utf-8") as file:

        return json.load(file)["questions"]


def render_markdown(summaries, latency, rows, systems, when):
    """Human-readable summary of one run."""

    lines = [
        f"# Retrieval evaluation — {when}",
        "",
        f"{len(rows)} questions, top {K}, Ushahidi `{config.USHAHIDI_COMMIT[:8]}`, "
        f"LLM `{config.GROQ_MODEL}`" + ("" if "llm" in systems else " (not used)"),
        "",
        "| system | MRR@10 | " + " | ".join(f"Hit@{n}" for n in HIT_LEVELS) + " |",
        "|---|---|" + "---|" * len(HIT_LEVELS),
    ]

    for system in systems:

        s = summaries[system]

        lines.append(
            f"| {system} | {s['mrr']:.3f} | "
            + " | ".join(f"{s[f'hit@{n}']:.1f}%" for n in HIT_LEVELS) + " |"
        )

    lines += [
        "",
        f"Latency per question: mean {latency['mean_s']:.1f} s, max {latency['max_s']:.1f} s "
        f"(target from the brief: under 60 s).",
        "",
        "## Per question (rank of first correct file; `-` = not in top 10)",
        "",
        "| # | " + " | ".join(systems) + " | question |",
        "|---|" + "---|" * len(systems) + "---|",
    ]

    for i, row in enumerate(rows, 1):

        cells = " | ".join(str(row[s] or "-") for s in systems)

        lines.append(f"| {i} | {cells} | {row['question']} |")

    return "\n".join(lines) + "\n"


# ============================================================
# Evaluation run
# ============================================================

def main():

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--no-llm", action="store_true", help="do not evaluate LLM reranking")

    parser.add_argument("--output", help="write per-question results to this JSON file (default: reports/eval/)")

    parser.add_argument("--questions", help="only these 1-based question numbers, e.g. 23,25,28 (default: all)")

    parser.add_argument("--pause", type=float, default=0.0, help="seconds to wait between questions (keeps LLM runs under Groq's per-minute limits)")

    args = parser.parse_args()

    from retrieval import get_retriever

    retriever = get_retriever()

    use_llm = not args.no_llm and bool(config.groq_api_keys())

    systems = ["semantic", "hybrid"] + (["llm"] if use_llm else [])

    questions = load_questions()

    numbers = [int(n) for n in args.questions.split(",")] if args.questions else list(range(1, len(questions) + 1))

    questions = [(n, questions[n - 1]) for n in numbers]

    ranks = {system: [] for system in systems}

    rows = []

    seconds = []

    print(f"Evaluating {len(questions)} questions: {', '.join(systems)}\n")

    for position, (i, item) in enumerate(questions):

        if args.pause and position:

            time.sleep(args.pause)

        started = time.perf_counter()

        retrieval = retriever.search(item["question"], use_llm=use_llm)

        elapsed = time.perf_counter() - started

        seconds.append(elapsed)

        orderings = {
            "semantic": retrieval["semantic"],
            "hybrid": retrieval["hybrid"],
            "llm": retrieval["final"],
        }

        row = {"number": i, "question": item["question"], "category": item["category"], "seconds": round(elapsed, 2)}

        for system in systems:

            rank = first_relevant_rank(orderings[system], item["relevant"])

            ranks[system].append(rank)

            row[system] = rank

        top = orderings[systems[-1]][0]

        row["top_result"] = f"{top['source']}:{top['start_line']}"

        rows.append(row)

        cells = "  ".join(f"{s}={row[s] or '-':>2}" for s in systems)

        print(f"{i:>2}. {cells}  {elapsed:4.1f}s  {item['question']}")

        if use_llm and not retrieval["llm_used"]:

            print("    (LLM rerank unavailable for this query, hybrid order used)")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summaries = {system: summarize(ranks[system]) for system in systems}

    latency = {"mean_s": sum(seconds) / len(seconds), "max_s": max(seconds)}

    print("\n" + "=" * 70)
    print(f"RESULTS (top {K}, {len(questions)} questions, Ushahidi {config.USHAHIDI_COMMIT[:8]})")
    print("=" * 70)
    print(f"{'system':<10}{'MRR@10':>10}" + "".join(f"{'Hit@' + str(n):>10}" for n in HIT_LEVELS))

    for system, s in summaries.items():

        print(f"{system:<10}{s['mrr']:>10.3f}" + "".join(f"{s[f'hit@{n}']:>9.1f}%" for n in HIT_LEVELS))

    print(f"\nLatency: mean {latency['mean_s']:.1f} s, max {latency['max_s']:.1f} s per question")

    if not use_llm:

        print("LLM reranking not evaluated (no Groq key or --no-llm).")

    # --------------------------------------------------------
    # Persist (never only on screen)
    # --------------------------------------------------------

    when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")

    output = Path(args.output) if args.output else REPORTS_DIR / f"{stamp}-{'-'.join(systems)}.json"

    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as file:

        json.dump({
            "when": when,
            "ushahidi_commit": config.USHAHIDI_COMMIT,
            "llm_model": config.GROQ_MODEL if use_llm else None,
            "summary": summaries,
            "latency": latency,
            "questions": rows,
        }, file, indent=2)

    print("\nResults written to", output)

    if not args.output:

        latest = REPORTS_DIR / "latest.md"

        with open(latest, "w", encoding="utf-8") as file:

            file.write(render_markdown(summaries, latency, rows, systems, when))

        print("Summary written to", latest)


if __name__ == "__main__":

    main()
