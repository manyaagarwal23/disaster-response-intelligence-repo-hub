"""
Command-line semantic code search.

Usage:
    python search.py "where is incoming SMS report parsed"
    python search.py --no-llm "where is the map pin logic"
"""

import argparse

from retrieval import get_retriever


def main():

    parser = argparse.ArgumentParser(description="Search the Ushahidi codebase.")

    parser.add_argument("question", nargs="*", help="question to ask")

    parser.add_argument("--no-llm", action="store_true", help="skip the LLM reranker")

    parser.add_argument("-k", type=int, default=5, help="number of results to show")

    args = parser.parse_args()

    question = " ".join(args.question) or input("\nEnter your question: ")

    retrieval = get_retriever().search(question, use_llm=not args.no_llm)

    print(
        "\nRanking:",
        "semantic + hybrid + LLM rerank" if retrieval["llm_used"] else "semantic + hybrid",
    )

    for final_rank, result in enumerate(retrieval["final"][:args.k], 1):

        print("\n" + "=" * 70)
        print(f"Final Rank: {final_rank}   (semantic rank: {result['semantic_rank']})")
        print(f"Source: {result['source']}:{result['start_line']}-{result['end_line']}")
        print("Namespace:", result["namespace"])
        print("Class:", result["class"], f"({result['class_kind']})" if result["class_kind"] else "")
        print("Method:", result["method"])
        print("Type:", result["type"])
        print(f"Score: {result['score']:.4f}   similarity: {result['similarity']:.4f}")
        print("Identifier matches:", result["identifier_matches"])
        print("Code matches:", result["code_matches"])
        print("Structural matches:", result["structural_matches"])
        print("-" * 70)
        print(result["content"])

    print("\nYour question:")
    print(question)


if __name__ == "__main__":

    main()
