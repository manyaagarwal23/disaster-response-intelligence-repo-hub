import json
import re

import config
import llm as llm_module
from llm import LLMRequestError, get_llm, invoke_with_retry, strip_reasoning


MAX_CONTEXT_CHARS = 4000

# The local CPU model sees less code so it can read the prompt quickly
LOCAL_CONTEXT_CHUNKS = 2

LOCAL_CONTEXT_CHARS = 700


class GenerationError(RuntimeError):
    pass


def build_answer_prompt(question, results):

    prompt = f"""
You are a codebase assistant for the Ushahidi PHP repository.

Answer the user's question using ONLY the provided repository context.

USER QUESTION:
{question}

REPOSITORY CONTEXT:
"""

    for i, r in enumerate(results, 1):

        content = r["content"]

        if len(content) > MAX_CONTEXT_CHARS:

            content = content[:MAX_CONTEXT_CHARS] + "\n...[CONTENT TRUNCATED FOR SIZE]..."

        prompt += f"""
SOURCE {i}
File: {r['source']} (lines {r.get('start_line')}-{r.get('end_line')})
Namespace: {r['namespace']}
Class: {r['class']}
Method: {r['method']}
Type: {r['type']}

CODE:
{content}

"""

    prompt += """
INSTRUCTIONS:
1. Answer the question directly using ONLY evidence from the provided code. Do not invent repository details.
2. If the provided context is insufficient, your explanations must state: "I could not determine this from the retrieved repository context."
3. When you mention code, cite it as SOURCE numbers, e.g. "(SOURCE 2)".
4. You MUST format your entire response as a single, valid JSON object. Do NOT wrap it in markdown code blocks.
5. The JSON object must have exactly these keys:
   - "simple": A beginner-friendly explanation summarizing the answer using simple language and bullet points (Markdown supported).
   - "technical": A highly technical explanation retaining exact class names, methods, and markdown code snippets.
   - "diagram_type": Always "mermaid".
   - "diagram_code": ALWAYS provide raw Mermaid.js flowchart code (start with "graph TD", no markdown wrappers) showing the classes, methods and data flow involved in the answer. Put every node label in double quotes, e.g. A["UpdateUsecase::interact"], and do not use double quotes inside labels.

CRITICAL: Output ONLY valid JSON. No conversational text before or after.
"""

    return prompt


def parse_answer(text):
    """
    Parse the LLM reply into a dict with the keys the frontend
    expects. Falls back to showing the raw text when the model did
    not return valid JSON, instead of failing the whole request.
    """

    text = strip_reasoning(text)

    # Remove markdown code fences the model may add anyway
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)

    try:

        data = json.loads(match.group(0) if match else text)

        if not isinstance(data, dict):

            raise ValueError("answer is not a JSON object")

    except ValueError:

        return {
            "simple": text,
            "technical": "",
            "diagram_type": None,
            "diagram_code": None,
        }

    diagram_code = data.get("diagram_code")

    return {
        "simple": str(data.get("simple") or ""),
        "technical": str(data.get("technical") or ""),
        "diagram_type": "mermaid" if data.get("diagram_type") == "mermaid" and diagram_code else None,
        "diagram_code": str(diagram_code) if diagram_code else None,
    }


def build_local_prompt(question, results):
    """
    Compact prompt for the slow local fallback model: two code chunks,
    a plain-text answer of a few sentences (small models handle plain
    text far more reliably than a JSON schema).
    """

    parts = [
        "You are a codebase assistant for the Ushahidi PHP repository.",
        "Answer the question in 3 to 5 short sentences of plain text, using ONLY the code below.",
        "Name the file and the class or method that answer it. No JSON, no code blocks, no lists.",
        "",
        f"QUESTION: {question}",
        "",
    ]

    for i, r in enumerate(results[:LOCAL_CONTEXT_CHUNKS], 1):

        code = r["content"][:LOCAL_CONTEXT_CHARS]

        where = "::".join(x for x in (r.get("class"), r.get("method")) if x)

        parts += [f"CODE {i}: {r['source']} {where}".rstrip(), code, ""]

    parts.append("ANSWER:")

    return "\n".join(parts)


def looks_degenerate(text):
    """
    True when a reply is junk rather than an answer: too short, mostly
    non-Latin characters, or stuck repeating the same words. Seen once
    on the dev VM right after the local model loaded.
    """

    words = re.findall(r"\w+", text or "")

    if len(words) < 4:

        return True

    letters = [c for c in text if c.isalpha()]

    if letters and sum(1 for c in letters if ord(c) > 0x24F) / len(letters) > 0.1:

        return True

    run = longest = 1

    for previous, current in zip(words, words[1:], strict=False):

        run = run + 1 if current.lower() == previous.lower() else 1

        longest = max(longest, run)

    if longest >= 4:

        return True

    return len(words) >= 30 and len({w.lower() for w in words}) / len(words) < 0.35


def local_answer(text):
    """Wrap the local model's plain text as an answer (diagram comes from the backup)."""

    text = strip_reasoning(text).strip()

    if looks_degenerate(text):

        raise GenerationError(
            "Every Groq key is rate-limited and the local fallback model returned unusable text: "
            "showing search results only. Try again in a minute."
        )

    return {"simple": text, "technical": "", "diagram_type": None, "diagram_code": None}


def generate_answer(question, results):
    """
    Returns the parsed answer dict, or None when no LLM is
    configured. Raises GenerationError when the LLM call fails.
    """

    llm = get_llm()

    if llm is None:

        return None

    try:

        # Waits out short Groq rate-limit pauses (at most ~40 s in total)
        # instead of failing at once; each request holds one worker thread
        reply = invoke_with_retry(
            llm, build_answer_prompt(question, results), attempts=3, max_wait=20,
            local_prompt=build_local_prompt(question, results),
            local_max_tokens=config.OLLAMA_MAX_TOKENS,
        )

    except LLMRequestError as error:

        raise GenerationError(str(error)) from error

    if str(llm_module.last_provider() or "").startswith("ollama"):

        return local_answer(reply)

    return parse_answer(reply)
