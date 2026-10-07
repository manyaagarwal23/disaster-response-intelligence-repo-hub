"""
Retrieval evaluation against a ground-truth dataset (eval/questions.json).

For every question we know which Ushahidi files contain the answer.
We then check where the first correct file appears in each ranking:

  semantic - vector search only (the baseline)
  hybrid   - vector search + identifier/code/structural scoring
  llm      - hybrid + Groq LLM reranking (only when GROQ_API_KEY is set)

Metrics (computed over the top K = 10 results):
  MRR@10 - mean of 1/rank of the first correct result (0 if not found)
  Hit@k  - % of questions with a correct result in the top k

Usage:
    python evaluate.py               # semantic + hybrid (+ llm if key set)
    python evaluate.py --no-llm      # skip the LLM even if a key is set
    python evaluate.py --output eval/results.json
"""

import argparse
import json
import os

import config


K = 10

HIT_LEVELS = (1, 3, 5)

QUESTIONS_FILE = config.RAG_DIR / "eval" / "questions.json"


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


# ============================================================
# Evaluation run
# ============================================================

def main():

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--no-llm", action="store_true", help="do not evaluate LLM reranking")

    parser.add_argument("--output", help="write per-question results to this JSON file")

    args = parser.parse_args()

    from retrieval import get_retriever

    retriever = get_retriever()

    use_llm = not args.no_llm and bool(os.environ.get("GROQ_API_KEY"))

    systems = ["semantic", "hybrid"] + (["llm"] if use_llm else [])

    questions = load_questions()

    ranks = {system: [] for system in systems}

    rows = []

    print(f"Evaluating {len(questions)} questions: {', '.join(systems)}\n")

    for i, item in enumerate(questions, 1):

        retrieval = retriever.search(item["question"], use_llm=use_llm)

        orderings = {
            "semantic": retrieval["semantic"],
            "hybrid": retrieval["hybrid"],
            "llm": retrieval["final"],
        }

        row = {"question": item["question"], "category": item["category"]}

        for system in systems:

            rank = first_relevant_rank(orderings[system], item["relevant"])

            ranks[system].append(rank)

            row[system] = rank

        top = orderings[systems[-1]][0]

        row["top_result"] = f"{top['source']}:{top['start_line']}"

        rows.append(row)

        cells = "  ".join(f"{s}={row[s] or '-':>2}" for s in systems)

        print(f"{i:>2}. {cells}  {item['question']}")

        if use_llm and not retrieval["llm_used"]:

            print("    (LLM rerank unavailable for this query, hybrid order used)")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summaries = {system: summarize(ranks[system]) for system in systems}

    print("\n" + "=" * 70)
    print(f"RESULTS (top {K}, {len(questions)} questions, Ushahidi {config.USHAHIDI_COMMIT[:8]})")
    print("=" * 70)
    print(f"{'system':<10}{'MRR@10':>10}" + "".join(f"{'Hit@' + str(n):>10}" for n in HIT_LEVELS))

    for system, s in summaries.items():

        print(f"{system:<10}{s['mrr']:>10.3f}" + "".join(f"{s[f'hit@{n}']:>9.1f}%" for n in HIT_LEVELS))

    if not use_llm:

        print("\nLLM reranking not evaluated (no GROQ_API_KEY or --no-llm).")

    if args.output:

        with open(args.output, "w", encoding="utf-8") as file:

            json.dump({"summary": summaries, "questions": rows}, file, indent=2)

        print("\nPer-question results written to", args.output)


if __name__ == "__main__":

    main()
