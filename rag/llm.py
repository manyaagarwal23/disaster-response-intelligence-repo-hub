import os
import re
import time

import config


# Characters of code shown per result to the reranker (keeps the
# request small enough for Groq's payload limit)
RERANK_PREVIEW_CHARS = 600


class LLMRequestError(RuntimeError):
    """The LLM could not be reached or kept refusing the request."""


# ============================================================
# Shared helpers
# ============================================================

def get_llm(max_tokens=None):
    """
    Return a LangChain ChatGroq client, or None when no API key is
    configured. Imported lazily so the rest of the app (and the
    unit tests) work without langchain installed or a key set.
    max_tokens caps the reply; Groq's free tier allows only ~1,000
    output tokens per minute, so tools keep their requests small.
    """

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:

        return None

    from langchain_groq import ChatGroq

    return ChatGroq(
        groq_api_key=api_key,
        model_name=config.GROQ_MODEL,
        temperature=0,
        max_tokens=max_tokens,
    )


def is_rate_limit(message):

    return re.search(r"rate.?limit|\b429\b|\b413\b", message, re.IGNORECASE) is not None


def retry_after_seconds(message):
    """
    Seconds Groq asks us to wait ("Please try again in 2.699s"), or None.
    """

    match = re.search(r"try again in ([\d.]+)\s*(ms|s)", message)

    if not match:

        return None

    value = float(match.group(1))

    return value / 1000 if match.group(2) == "ms" else value


def prompt_too_large(message):
    """
    A single prompt bigger than the per-minute budget never fits, so
    there is no point retrying it.
    """

    budget = re.search(r"Limit (\d+), Requested (\d+)", message)

    return bool(budget) and "Used" not in message and int(budget.group(2)) > int(budget.group(1))


def invoke_with_retry(llm, prompt, attempts=4, max_wait=65):
    """
    Send one prompt and return the reply text.

    Groq's free tier has small per-minute budgets, so a request often
    fails with 429 and a "try again in N s" hint. We wait that long
    (at most max_wait seconds) and retry, up to `attempts` times.
    Raises LLMRequestError when the request keeps failing, the prompt
    is too large for the budget, or any other error occurs.
    """

    last_error = ""

    for attempt in range(1, attempts + 1):

        try:

            # LangChain chat models accept a plain string as the user message
            return llm.invoke(prompt).content

        except Exception as error:

            last_error = str(error)

            if not is_rate_limit(last_error):

                raise LLMRequestError(f"LLM request failed: {last_error[:300]}") from error

            if prompt_too_large(last_error):

                raise LLMRequestError(
                    "Prompt is larger than the model's per-minute token budget; nothing to retry."
                ) from error

            if attempt == attempts:

                break

            # Groq usually says how long to wait; otherwise back off briefly
            wait = min(max_wait, (retry_after_seconds(last_error) or 2.0) + 0.5)

            print(f"LLM rate limit hit, waiting {wait:.1f}s (attempt {attempt}/{attempts})...")

            time.sleep(wait)

    raise LLMRequestError(
        f"Groq rate limit reached (HTTP 429) after {attempts} attempts. Wait a minute and try again."
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

    try:

        # Short waits only (at most ~10 s): reranking must not hold up the answer
        reply = invoke_with_retry(llm, build_rerank_prompt(question, results), attempts=2, max_wait=10)

    except LLMRequestError as error:

        print(f"LLM reranking failed, keeping hybrid order: {error}")

        return None

    order = parse_rerank_order(reply)

    if not order:

        print("LLM reranker returned no usable order, keeping hybrid order.")

        return None

    return order
