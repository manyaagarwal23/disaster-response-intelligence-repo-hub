import subprocess
import re
import sys

QUESTIONS = [
    # Architecture & Contracts
    "Where is the EntityExists contract defined?",
    "What does EntityExists::exists() define?",
    "Where is verifyEntityLoaded declared abstract and where is it implemented?",
    "What exception is thrown when an entity cannot be found?",
    "How does the system verify that an entity was actually loaded?",
    "Which repository method is used to load an entity before verification?",
    "Where is the actual implementation of verifyEntityLoaded?",
    "Which use cases call verifyEntityLoaded?",
    "Show me how the EntityExists interface is structured.",
    "What happens if the exists() method returns false?",
    
    # Posts & Usecases
    "What happens after an entity is loaded in UpdateUsecase?",
    "Where is verifyEntityLoaded implemented and which parts of the system call it?",
    "Show me the code for the UpdateUsecase class.",
    "What dependencies are injected into the UpdateUsecase?",
    "How does the CreateSetPost usecase work?",
    "Show me how a post is updated in the system.",
    "What methods does the PostRepository provide?",
    "How does the system handle fetching entities from the database?",
    "Which classes implement the EntityExists contract?",
    "Explain what the ReadUsecase does.",
    
    # Security & Permissions
    "How does the system prevent an unauthorized user from creating a post?",
    "Where is the user's role checked when creating a post?",
    "Where is the permission to create a post checked?",
    "How does the system determine which roles can create posts?",
    "How does the system check whether a user has Manage Posts permission?",
    "Show me the code that validates user permissions.",
    "How does the API prevent unauthorized access to usecases?",
    "What happens when a user without permissions tries to update a post?",
    "Explain how roles are assigned to users in the system.",
    "How does the system validate input data before creating a post?"
]

total_queries = 0
baseline_mrr_sum = 0.0
reranked_mrr_sum = 0.0
top1_baseline_hits = 0
top1_reranked_hits = 0

print("Starting Quantitative Evaluation (MRR & Top-1 Accuracy)...\n")

for i, question in enumerate(QUESTIONS, 1):
    print(f"{'=' * 70}")
    print(f"QUESTION {i}: {question}")

    result = subprocess.run(
        [sys.executable, "search.py", question],
        capture_output=True,
        text=True
    )

    match = re.search(r"EVAL_RESULT\|(\d+)\|(\d+)\|(.+)", result.stdout)

    if match:
        original_rank = int(match.group(1))
        final_rank = int(match.group(2))
        source = match.group(3)

        print(f"-> Baseline Rank (Semantic): {original_rank}")
        print(f"-> Reranked Rank (LLM): {final_rank}")
        print(f"-> Source Retrieved: {source}")

        baseline_mrr_sum += 1.0 / original_rank
        reranked_mrr_sum += 1.0 / final_rank

        if original_rank == 1:
            top1_baseline_hits += 1
        if final_rank == 1:
            top1_reranked_hits += 1
            
        total_queries += 1
    else:
        print("EVALUATION FAILED for this query.")
        print(result.stderr[-500:])

print("\n" + "=" * 70)
print("FINAL QUANTITATIVE METRICS")
print("=" * 70)
if total_queries > 0:
    baseline_mrr = baseline_mrr_sum / total_queries
    reranked_mrr = reranked_mrr_sum / total_queries
    baseline_acc = (top1_baseline_hits / total_queries) * 100
    reranked_acc = (top1_reranked_hits / total_queries) * 100

    print(f"Total Evaluated Queries: {total_queries}")
    print(f"Baseline Semantic MRR: {baseline_mrr:.4f}")
    print(f"Hybrid + LLM Reranked MRR: {reranked_mrr:.4f}")
    print(f"Baseline Top-1 Accuracy: {baseline_acc:.2f}%")
    print(f"Hybrid + LLM Top-1 Accuracy: {reranked_acc:.2f}%")
    
    improvement = ((reranked_mrr - baseline_mrr) / baseline_mrr) * 100
    print(f"\nConclusion: LLM Reranking improved accuracy by {improvement:.2f}%.")
else:
    print("No queries evaluated successfully.")