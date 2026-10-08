import json
import re
import threading
import time
import urllib.error
import urllib.request

import config


# Characters of code shown per result to the reranker (keeps the
# request small enough for Groq's payload limit)
RERANK_PREVIEW_CHARS = config.RERANK_PREVIEW_CHARS

# A key whose "try again in N s" hint is at most this long is worth a
# short wait before falling back to the slow local model
SHORT_WAIT_SECONDS = 10


class LLMRequestError(RuntimeError):
    """The LLM could not be reached or kept refusing the request."""


# ============================================================
# Error classification
# ============================================================

def is_rate_limit(message):

    return re.search(r"rate.?limit|\b429\b|\b413\b", message, re.IGNORECASE) is not None


def is_bad_key(message):

    return re.search(r"\b401\b|\b403\b|invalid.?api.?key|authentication", message, re.IGNORECASE) is not None


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
    there is no point retrying it (with any key).
    """

    budget = re.search(r"Limit (\d+), Requested (\d+)", message)

    return bool(budget) and "Used" not in message and int(budget.group(2)) > int(budget.group(1))


# ============================================================
# Providers
# ============================================================

def make_groq_client(api_key, max_tokens=None):

    from langchain_groq import ChatGroq

    return ChatGroq(
        groq_api_key=api_key,
        model_name=config.GROQ_MODEL,
        temperature=0,
        max_tokens=max_tokens,
    )


def ollama_complete(prompt, max_tokens=None, model=None, host=None, timeout=None):
    """
    Ask the local Ollama server for a completion. Slow on CPU (minutes
    for a long answer), so this is the end of the fallback chain.
    """

    model = model or config.ollama_model()

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_ctx": config.OLLAMA_NUM_CTX,
            "num_predict": max_tokens or 1200,
        },
    }

    request = urllib.request.Request(
        f"{(host or config.OLLAMA_HOST).rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:

        with urllib.request.urlopen(request, timeout=timeout or config.OLLAMA_TIMEOUT) as response:

            body = json.loads(response.read().decode("utf-8"))

    except (urllib.error.URLError, OSError, ValueError) as error:

        raise LLMRequestError(f"Local model {model} unavailable: {error}") from error

    return (body.get("message") or {}).get("content", "")


# Keys rejected with 401/403, shared by every client in this process
# (get_llm() builds a new client per request) and guarded by a lock
_DEAD_KEYS = set()

_dead_keys_lock = threading.Lock()


class LLMClient:
    """
    One LLM entry point with a strict fallback chain:

        Groq key 1 -> key 2 -> ... -> key N -> local Ollama model

    Every request starts at key 1. A key that is rate limited (per minute
    or per day) hands over to the next one immediately; a key that is
    rejected (401/403) is skipped for the rest of the process. When every
    key failed and the shortest "try again in N s" hint is short, the
    keys get one more pass after that wait. Only then does the local
    model answer (if configured and `fallback` is allowed for the call).
    """

    def __init__(self, api_keys, max_tokens=None, ollama_model=""):

        self.api_keys = list(api_keys)

        self.max_tokens = max_tokens

        self.ollama_model = ollama_model

        self.clients = [None] * len(self.api_keys)   # built lazily

        with _dead_keys_lock:

            self.dead = {index for index, key in enumerate(self.api_keys) if key in _DEAD_KEYS}

        self.last_provider = None

    def _client(self, index):

        if self.clients[index] is None:

            self.clients[index] = make_groq_client(self.api_keys[index], self.max_tokens)

        return self.clients[index]

    def _try_keys(self, prompt):
        """One pass over the keys. Returns (text, shortest_wait, errors)."""

        shortest_wait = None

        errors = []

        for index in range(len(self.api_keys)):

            if index in self.dead:

                continue

            try:

                text = self._client(index).invoke(prompt).content

                self.last_provider = f"groq#{index + 1}"

                return text, None, errors

            except Exception as error:

                message = str(error)

                errors.append(f"key {index + 1}: {message[:160]}")

                if prompt_too_large(message):

                    raise LLMRequestError(
                        "Prompt is larger than the model's per-minute token budget; nothing to retry."
                    ) from error

                if is_bad_key(message):

                    self.dead.add(index)

                    with _dead_keys_lock:

                        _DEAD_KEYS.add(self.api_keys[index])

                    print(f"Groq key {index + 1} rejected ({message[:80]}); skipping it from now on.")

                    continue

                if is_rate_limit(message):

                    hint = retry_after_seconds(message)

                    if hint is not None and (shortest_wait is None or hint < shortest_wait):

                        shortest_wait = hint

                    print(f"Groq key {index + 1} rate limited; trying the next key.")

                    continue

                print(f"Groq key {index + 1} failed ({message[:80]}); trying the next key.")

        return None, shortest_wait, errors

    def complete(self, prompt, attempts=2, max_wait=20, fallback=True, local_prompt=None, local_max_tokens=None):
        """
        Text reply for `prompt`. When every key is exhausted and `fallback`
        is allowed, the local model gets `local_prompt` (a smaller prompt
        suited to a slow CPU model) or, if none is given, `prompt`.
        """

        if not self.api_keys and not (fallback and self.ollama_model):

            raise LLMRequestError("No LLM configured.")

        errors = []

        for attempt in range(1, attempts + 1):

            if self.api_keys:

                text, shortest_wait, errors = self._try_keys(prompt)

                if text is not None:

                    return text

                # A short pause may free a key, which beats minutes of CPU inference
                if attempt < attempts and shortest_wait is not None and shortest_wait <= min(max_wait, SHORT_WAIT_SECONDS):

                    print(f"All Groq keys limited; waiting {shortest_wait:.1f}s before the next pass.")

                    time.sleep(shortest_wait + 0.5)

                    continue

            break

        if fallback and self.ollama_model:

            print(f"All Groq keys exhausted; answering with local {self.ollama_model} (slow).")

            text = ollama_complete(local_prompt or prompt, local_max_tokens or self.max_tokens, self.ollama_model)

            self.last_provider = f"ollama:{self.ollama_model}"

            return text

        detail = "; ".join(errors[-2:]) if errors else "no usable key"

        raise LLMRequestError(
            f"Groq rate limit reached on all {len(self.api_keys)} key(s) (HTTP 429). "
            f"Wait a minute and try again. [{detail}]"
        )


# Per thread, because the web server answers several requests at once
_LAST_PROVIDER = threading.local()


def last_provider():
    """Which provider produced this thread's most recent completion (groq#N / ollama:model)."""

    return getattr(_LAST_PROVIDER, "name", None)


def get_llm(max_tokens=None):
    """
    Return an LLMClient (Groq key chain + optional local fallback), or
    None when nothing is configured. Built lazily so the rest of the app
    (and the unit tests) work without langchain installed or a key set.
    max_tokens caps the reply; Groq's free tier allows only ~1,000
    output tokens per minute, so tools keep their requests small.
    """

    keys = config.groq_api_keys()

    model = config.ollama_model()

    if not keys and not model:

        return None

    return LLMClient(keys, max_tokens=max_tokens, ollama_model=model)


def invoke_with_retry(llm, prompt, attempts=4, max_wait=65, fallback=True, local_prompt=None, local_max_tokens=None):
    """
    Send one prompt and return the reply text.

    With an LLMClient this walks the key chain (and the local fallback
    when `fallback` is true). With a plain single-key client it waits out
    Groq's "try again in N s" hints (at most max_wait seconds per try).
    Raises LLMRequestError when the request keeps failing or the prompt
    is too large for the budget.
    """

    if hasattr(llm, "complete"):

        text = llm.complete(
            prompt, attempts=attempts, max_wait=max_wait, fallback=fallback,
            local_prompt=local_prompt, local_max_tokens=local_max_tokens,
        )

        _LAST_PROVIDER.name = llm.last_provider

        return text

    last_error = ""

    for attempt in range(1, attempts + 1):

        try:

            text = llm.invoke(prompt).content

            _LAST_PROVIDER.name = "groq#1"

            return text

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
    Reranking uses the Groq keys only: the local fallback model would
    take minutes on CPU and rank poorly, so the hybrid order is kept
    when every key is exhausted.
    """

    llm = get_llm()

    if llm is None or not getattr(llm, "api_keys", True):

        return None

    try:

        # Short waits only (at most ~10 s): reranking must not hold up the answer
        reply = invoke_with_retry(llm, build_rerank_prompt(question, results), attempts=2, max_wait=10, fallback=False)

    except LLMRequestError as error:

        print(f"LLM reranking failed, keeping hybrid order: {error}")

        return None

    order = parse_rerank_order(reply)

    if not order:

        print("LLM reranker returned no usable order, keeping hybrid order.")

        return None

    return order
