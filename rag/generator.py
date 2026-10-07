import json
import re

from llm import get_llm, strip_reasoning


MAX_CONTEXT_CHARS = 4000


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


def generate_answer(question, results):
    """
    Returns the parsed answer dict, or None when no LLM is
    configured. Raises GenerationError when the LLM call fails.
    """

    llm = get_llm()

    if llm is None:

        return None

    from langchain_core.messages import HumanMessage

    try:

        response = llm.invoke([
            HumanMessage(content=build_answer_prompt(question, results))
        ])

    except Exception as error:

        if "429" in str(error):

            raise GenerationError(
                "Groq rate limit reached (HTTP 429). Wait a minute and try again."
            ) from error

        raise GenerationError(f"LLM request failed: {error}") from error

    return parse_answer(response.content)
