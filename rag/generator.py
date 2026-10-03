import os
from urllib import response
import requests


def generate_answer(question, results):
    prompt = f"""
You are a codebase assistant for the Ushahidi PHP repository.

Answer the user's question using ONLY the provided repository context.

USER QUESTION:
{question}

REPOSITORY CONTEXT:
"""

    for i, r in enumerate(results, 1):
        prompt += f"""
SOURCE {i}
File: {r['source']}
Namespace: {r['namespace']}
Class: {r['class']}
Method: {r['method']}
Type: {r['type']}

CODE:
{r['content']}

"""

    prompt += """
INSTRUCTIONS:
1. Answer the question directly.
2. Use only evidence from the provided code.
3. Do not invent repository details.
4. Mention the relevant file and method/class.
5. If the provided context is insufficient, say:
   "I could not determine this from the retrieved repository context."
6. Keep the answer concise and technical.

FORMAT:
Answer:
<your answer>

Sources:
- <file> — <method/class>
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
            "Content-Type": "application/json"
        },
        json={
            "model": "openrouter/free",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }
    )

    if response.status_code == 429:
         print("OpenRouter 429 response:")
         print(response.text)
         return ""

    response.raise_for_status()

    content = response.json()["choices"][0]["message"].get("content")

    return (content or "").strip()