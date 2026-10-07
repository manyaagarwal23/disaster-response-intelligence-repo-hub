import os
import re

import config


# Characters of code shown per result to the reranker (keeps the
# request small enough for Groq's payload limit)
RERANK_PREVIEW_CHARS = 600


# ============================================================
# Shared helpers
# ============================================================

def get_llm():
    """
    Return a LangChain ChatGroq client, or None when no API key is
    configured. Imported lazily so the rest of the app (and the
    unit tests) work without langchain installed or a key set.
    """

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:

        return None

    from langchain_groq import ChatGroq

    return ChatGroq(
        groq_api_key=api_key,
        model_name=config.GROQ_MODEL,
        temperature=0,
    )


def strip_reasoning(text):
    """
    Reasoning models (e.g. Qwen3) may prefix their answer with a
    <think>...</think> block. Remove it so it is never parsed as
    the answer.
    """

    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)

    # An unterminated <think> block means the answer was cut off
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)

    return text.strip()


def parse_rerank_order(text):
    """
    Turn the LLM reply into a list of 1-based result positions.
    Only the last non-empty line is used, since that is where the
    "4, 1, 7" style answer appears.
    """

    lines = [
        line
        for line in strip_reasoning(text).splitlines()
        if line.strip()
    ]

    if not lines:

        return []

    return [int(x) for x in re.findall(r"\b\d+\b", lines[-1])]


# ============================================================
# Reranker
# ============================================================

def build_rerank_prompt(question, results):

    prompt = f"""
You are a code-retrieval reranker for a PHP repository.

USER QUESTION:
{question}

RETRIEVED RESULTS:
"""

    for rank, r in enumerate(results, 1):

        preview = r["content"][:RERANK_PREVIEW_CHARS]

        if len(r["content"]) > RERANK_PREVIEW_CHARS:

            preview += "\n..."

        prompt += f"""
RESULT {rank}
Source: {r['source']}
Namespace: {r['namespace']}
Class: {r['class']}
Method: {r['method']}
Type: {r['type']}
Code:
{preview}
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

Return ONLY the result numbers in order, separated by commas, on a single line.
Example: 4, 1, 7
"""

    return prompt


def rerank(question, results):
    """
    Ask the LLM to reorder results.
    Returns a list of 1-based positions, or None when the LLM is not
    available or fails (the caller then keeps the hybrid order).
    """

    llm = get_llm()

    if llm is None:

        return None

    from langchain_core.messages import HumanMessage

    try:

        response = llm.invoke([
            HumanMessage(content=build_rerank_prompt(question, results))
        ])

    except Exception as error:

        print(f"LLM reranking failed, keeping hybrid order: {error}")

        return None

    order = parse_rerank_order(response.content)

    if not order:

        print("LLM reranker returned no usable order, keeping hybrid order.")

        return None

    return order
