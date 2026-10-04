import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

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
1. Answer the question directly using ONLY evidence from the provided code. Do not invent repository details.
2. If the provided context is insufficient, your explanations must state: "I could not determine this from the retrieved repository context."
3. You MUST format your entire response as a single, valid JSON object. Do NOT wrap it in markdown code blocks. 
4. The JSON object must have exactly these keys:
   - "simple": A beginner-friendly explanation summarizing the answer using simple language and bullet points (Markdown supported).
   - "technical": A highly technical explanation retaining exact class names, methods, and markdown code snippets.
   - "diagram_type": Specify "mermaid" if a visual diagram (flowchart, class, state) would help explain the architecture/flow. Otherwise, use null.
   - "diagram_code": If diagram_type is "mermaid", provide the raw Mermaid.js graph code here (no markdown wrappers). Otherwise, null.
   - "sources": An array of objects, each containing "file" (string path) and "context" (string, e.g., method or class name).

CRITICAL: Output ONLY valid JSON. No conversational text before or after.
"""

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "ERROR: The GROQ_API_KEY is not set in this terminal session! Please stop the server, set your API key using `$env:GROQ_API_KEY='gsk...'`, and start the server again."
        
    try:
        llm = ChatGroq(
            groq_api_key=api_key,
            model_name="qwen/qwen3.8-27b",
            temperature=0
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
    except Exception as e:
        if "429" in str(e):
             print("Groq 429 response:")
             print(e)
             return ""
        raise e
    content = content.strip()
    
    # Clean markdown wrappers if the LLM hallucinated them around the JSON
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()