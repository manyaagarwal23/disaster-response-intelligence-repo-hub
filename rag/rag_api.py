from generator import GenerationError, generate_answer
from retrieval import get_retriever


# Number of retrieved chunks passed to the answer generator
ANSWER_CONTEXT_K = 3

# Number of retrieved chunks shown to the user as evidence
EVIDENCE_K = 5


def to_source(result):

    return {
        "file": result["source"],
        "start_line": result["start_line"],
        "end_line": result["end_line"],
        "class": result["class"],
        "method": result["method"],
        "type": result["type"],
        "score": round(result["score"], 4),
        "content": result["content"],
    }


def mermaid_label(text):
    """Make text safe inside a quoted Mermaid node label."""

    text = str(text or "").replace('"', "'").replace("<", "").replace(">", "")

    return text[:60]


def build_fallback_diagram(results):
    """
    Simple diagram built from the retrieved code, used when the LLM
    does not return one: question -> class::method -> file.
    """

    lines = ["graph TD", '    Q["Your question"]']

    for i, r in enumerate(results, 1):

        unit = "::".join(part for part in (r["class"], r["method"]) if part) or r["type"]

        file_name = r["source"].rsplit("/", 1)[-1]

        lines.append(f'    U{i}["{mermaid_label(unit)}"]')
        lines.append(f'    F{i}["{mermaid_label(file_name)}:{r["start_line"]}"]')
        lines.append(f"    Q --> U{i}")
        lines.append(f"    U{i} -. defined in .-> F{i}")

    return "\n".join(lines)


def get_rag_answer(question):
    """
    Run retrieval + generation for one question.

    Returns a dict:
      answer   - parsed LLM answer (or None when no GROQ_API_KEY is set,
                 in which case the response is search results only)
      sources  - the chunks that were ACTUALLY retrieved and given to
                 the LLM (never taken from the LLM's own output)
      llm_used - whether the LLM reranked/answered

      warning  - why the LLM was not used, if it was not

    Raises retrieval.DatabaseNotReadyError if the vector DB is missing.
    """

    retrieval = get_retriever().search(question)

    results = retrieval["final"]

    warning = None

    try:

        answer = generate_answer(question, results[:ANSWER_CONTEXT_K])

    except GenerationError as error:

        # During a crisis, retrieved code is still useful when the
        # LLM is down or rate limited - return it with a warning.
        answer = None

        warning = str(error)

    if answer is not None:

        # Backup diagram built from the retrieved code. The page uses it
        # when the LLM skipped the diagram or its Mermaid code fails to render.
        answer["fallback_diagram_code"] = build_fallback_diagram(results[:ANSWER_CONTEXT_K])

        if not answer.get("diagram_code"):

            answer["diagram_type"] = "mermaid"
            answer["diagram_code"] = answer["fallback_diagram_code"]

    if answer is None and warning is None:

        warning = "GROQ_API_KEY is not set: showing search results only."

    return {
        "answer": answer,
        "sources": [to_source(r) for r in results[:EVIDENCE_K]],
        "llm_used": answer is not None,
        "warning": warning,
    }
