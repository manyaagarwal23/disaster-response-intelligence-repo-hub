import os
import requests
MODEL = os.getenv("LLM_MODEL", "openrouter/free")

def rerank(question, results):
    prompt = f"""
You are a code-retrieval reranker for a PHP repository.

USER QUESTION:
{question}

RETRIEVED RESULTS:
"""

    for r in results:
        prompt += f"""
RESULT {r['rank']}
Source: {r['source']}
Namespace: {r['namespace']}
Class: {r['class']}
Method: {r['method']}
Type: {r['type']}
Code:
{r['content']}
"""

    prompt += """
TASK:
Rank the retrieved results by relevance to the user's question.

Rules:
1. Prefer an exact file, class, interface, contract, method, or identifier mentioned or implied by the question.
2. If the question asks where something is defined, prefer the definition/declaration itself.
3. For a "contract" question, prefer the contract/interface declaration over implementations or unrelated methods.
4. Prefer direct evidence over related callers.
5. Ignore results that are only semantically similar but do not answer the question.
6. Return the most relevant result first.

Return ONLY the result numbers in order, separated by commas.
Example: 4, 1, 7
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }
    )

    response.raise_for_status()

    return (response.json()["choices"][0]["message"].get("content") or "").strip()