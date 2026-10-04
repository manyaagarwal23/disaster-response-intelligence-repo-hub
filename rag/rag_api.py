import re
import chromadb
from sentence_transformers import SentenceTransformer
from llm import rerank
from generator import generate_answer

def normalize_identifier(identifier):
    identifier = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', identifier)
    identifier = identifier.replace("_", " ").replace("-", " ")
    return identifier.lower().split()

# Initialize models and DB connection on startup
print("Loading RAG models...")
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection(name="ushahidi_code")
model = SentenceTransformer("BAAI/bge-base-en-v1.5")
print("RAG models loaded successfully!")

STOPWORDS = {"a", "an", "the", "is", "are", "was", "were", "how", "what", "where", "when", "why", "which", "who", "does", "do", "did", "can", "could", "would", "should", "this", "that", "these", "those", "to", "of", "in", "on", "for", "from", "with", "and", "or", "as", "by"}

def get_rag_answer(question: str) -> str:
    filename_match = re.search(r'\b[\w.-]+\.php\b', question, re.IGNORECASE)
    filename = filename_match.group(0) if filename_match else None
    
    question_words = set()
    for word in re.findall(r'[a-zA-Z0-9_]+', question):
        if word.lower() not in STOPWORDS:
            question_words.add(word.lower())
            question_words.update(normalize_identifier(word))
            
    retrieval_query = " ".join(sorted(question_words)) if question_words else question
    question_embedding = model.encode(retrieval_query)
    
    if filename:
        results = collection.query(query_embeddings=[question_embedding.tolist()], n_results=10, where={"filename": filename})
    else:
        results = collection.query(query_embeddings=[question_embedding.tolist()], n_results=10)
        
    scored_results = []
    if not results or not results.get("documents") or not results["documents"][0]:
        return "I could not find any relevant code in the repository."
        
    for i in range(len(results["documents"][0])):
        metadata = results["metadatas"][0][i]
        implementation_score = 1 if metadata.get("abstract") is False else 0
        code = results["documents"][0][i]
        
        identifiers = [metadata.get("filename", ""), metadata.get("class", ""), metadata.get("method", ""), metadata.get("namespace", "")]
        identifier_words = set()
        for identifier in identifiers:
            identifier_words.update(normalize_identifier(identifier))
            
        identifier_matches = question_words & identifier_words
        identifier_score = len(identifier_matches)
        
        exact_identifier_score = 0
        for identifier in identifiers:
            identifier_tokens = normalize_identifier(identifier)
            if identifier_tokens and all(token in question_words for token in identifier_tokens):
                exact_identifier_score += 1
                
        normalized_code = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', code).replace("_", " ").lower()
        code_matches = [word for word in question_words if len(word) >= 3 and word in normalized_code]
        code_score = len(set(code_matches))
        
        distance = results["distances"][0][i]
        
        scored_results.append({
            "distance": distance,
            "implementation_score": implementation_score,
            "code_score": code_score,
            "identifier_score": identifier_score,
            "exact_identifier_score": exact_identifier_score,
            "source": metadata["source"],
            "namespace": metadata["namespace"],
            "class": metadata["class"],
            "method": metadata["method"],
            "type": metadata["type"],
            "content": code
        })
        
    # Rank results
    scored_results.sort(key=lambda x: (-x["exact_identifier_score"], -x["implementation_score"], -x["code_score"], -x["identifier_score"], x["distance"]))
    # Keep top 10 for the LLM reranker to ensure we don't miss the correct file
    top_results = scored_results[:10]
    
    # Rerank with LLM using only a 300-character preview to avoid 413 Payload Too Large
    llm_input = [{"rank": i + 1, "source": r["source"], "namespace": r["namespace"], "class": r["class"], "method": r["method"], "type": r["type"], "content": r["content"][:300] + "..."} for i, r in enumerate(top_results)]
    try:
        reranked = rerank(question, llm_input)
        order = [int(x) for x in re.findall(r'\b\d+\b', reranked) if 1 <= int(x) <= len(top_results)]
        if order:
            top_results = [top_results[i - 1] for i in order]
    except Exception as e:
        print("LLM Reranking skipped/failed:", e)
        
    # Generate Answer
    try:
        # Only pass the top 3 results to the generator to avoid exceeding Groq's payload limit!
        final_results = top_results[:3]
        for r in final_results:
            if len(r["content"]) > 4000:
                r["content"] = r["content"][:4000] + "\n...[CONTENT TRUNCATED FOR SIZE]..."
                
        answer = generate_answer(question, final_results)
    except Exception as e:
        answer = f"Error generating answer: {e}"
        
    return answer
