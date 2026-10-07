"""
Shared retrieval logic used by the web API (rag_api.py), the CLI
(search.py) and the evaluation (evaluate.py), so all three measure
and serve exactly the same pipeline.

The scoring helpers at the top are pure functions with no heavy
dependencies, so they can be unit-tested without ChromaDB or torch.
"""

import re

import config


STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "how", "what", "where", "when", "why", "which",
    "who", "does", "do", "did", "can", "could",
    "would", "should", "this", "that", "these",
    "those", "to", "of", "in", "on", "for", "from",
    "with", "and", "or", "as", "by", "me", "show",
    "it", "be", "its", "there", "explain",
}

# Weights of the hybrid score. Semantic similarity (0..1) is the
# base; lexical evidence adds a bonus on top of it. Tuned on the
# evaluation set in evaluate.py - re-run it after changing these.
WEIGHTS = {
    "exact_identifier": 0.10,
    "identifier": 0.03,
    "code": 0.01,
    "structural": 0.01,
    "implementation": 0.02,
}

CANDIDATES = 30

RERANK_TOP_K = 10


# ============================================================
# 1. Question Analysis
# ============================================================

def normalize_identifier(identifier):
    """
    Split a programming identifier into lowercase words:
    "FetchDataSourceQuery" -> ["fetch", "data", "source", "query"]
    """

    identifier = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier or "")

    identifier = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", identifier)

    identifier = re.sub(r"[_\-\\/.:]", " ", identifier)

    return identifier.lower().split()


def extract_question_words(question):

    words = set()

    for word in re.findall(r"[a-zA-Z0-9_]+", question):

        if word.lower() in STOPWORDS:

            continue

        words.add(word.lower())

        words.update(
            token
            for token in normalize_identifier(word)
            if token not in STOPWORDS
        )

    return words


def detect_filename(question):

    match = re.search(r"\b[\w.-]+\.php\b", question, re.IGNORECASE)

    return match.group(0) if match else None


# ============================================================
# 2. Hybrid Scoring
# ============================================================

def normalize_code(text):

    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")

    return text.replace("_", " ").lower()


def score_candidate(question_words, document, metadata, distance):

    identifiers = [
        metadata.get("filename", "").removesuffix(".php"),
        metadata.get("class", ""),
        metadata.get("method", ""),
    ]

    identifier_words = set()

    for identifier in identifiers + [metadata.get("namespace", "")]:

        identifier_words.update(normalize_identifier(identifier))

    identifier_matches = question_words & identifier_words

    # An identifier counts as an exact match when every one of its
    # words appears in the question ("UpdateUsecase" <- "update usecase")
    exact_identifier_score = sum(
        1
        for identifier in identifiers
        if normalize_identifier(identifier)
        and all(
            token in question_words
            for token in normalize_identifier(identifier)
        )
    )

    normalized_code = normalize_code(document)

    code_matches = sorted({
        word
        for word in question_words
        if len(word) >= 3 and word in normalized_code
    })

    normalized_structural = normalize_code(" ".join([
        metadata.get("calls", ""),
        metadata.get("parameter_types", ""),
        metadata.get("assignments", ""),
    ]))

    structural_matches = sorted({
        word
        for word in question_words
        if len(word) >= 3 and word in normalized_structural
    })

    implementation_score = (
        1
        if metadata.get("type") in ("method", "function")
        and metadata.get("abstract") is False
        else 0
    )

    # Cosine distance -> similarity
    similarity = 1.0 - distance

    score = (
        similarity
        + WEIGHTS["exact_identifier"] * exact_identifier_score
        + WEIGHTS["identifier"] * len(identifier_matches)
        + WEIGHTS["code"] * len(code_matches)
        + WEIGHTS["structural"] * len(structural_matches)
        + WEIGHTS["implementation"] * implementation_score
    )

    return {
        "score": score,
        "similarity": similarity,
        "distance": distance,
        "exact_identifier_score": exact_identifier_score,
        "identifier_matches": sorted(identifier_matches),
        "code_matches": code_matches,
        "structural_matches": structural_matches,
        "implementation_score": implementation_score,
    }


def build_result(document, metadata, distance, semantic_rank, question_words):

    result = {
        "semantic_rank": semantic_rank,
        "source": metadata.get("source", ""),
        "filename": metadata.get("filename", ""),
        "namespace": metadata.get("namespace", ""),
        "class": metadata.get("class", ""),
        "class_kind": metadata.get("class_kind", ""),
        "method": metadata.get("method", ""),
        "type": metadata.get("type", ""),
        "start_line": metadata.get("start_line"),
        "end_line": metadata.get("end_line"),
        "content": document,
    }

    result.update(score_candidate(question_words, document, metadata, distance))

    return result


def hybrid_rank(results):

    return sorted(results, key=lambda r: (-r["score"], r["distance"]))


def apply_llm_order(results, order):
    """
    Reorder results by a list of 1-based positions returned by the
    LLM reranker. Positions the LLM forgot keep their hybrid order
    at the end, so a sloppy LLM answer can never drop results.
    """

    seen = []

    for position in order:

        if 1 <= position <= len(results) and position not in seen:

            seen.append(position)

    remaining = [
        position
        for position in range(1, len(results) + 1)
        if position not in seen
    ]

    return [results[position - 1] for position in seen + remaining]


# ============================================================
# 3. Retriever (ChromaDB + embedding model)
# ============================================================

class DatabaseNotReadyError(RuntimeError):
    pass


class Retriever:

    def __init__(self):

        import chromadb
        from sentence_transformers import SentenceTransformer

        self.client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))

        self.connect()

        self.model = SentenceTransformer(config.EMBEDDING_MODEL)

    def connect(self):

        try:

            self.collection = self.client.get_collection(name=config.COLLECTION_NAME)

        except Exception as error:

            raise DatabaseNotReadyError(
                f"Vector database '{config.COLLECTION_NAME}' not found at "
                f"{config.CHROMA_PATH}. Build it with: python ingestion.py"
            ) from error

        if self.collection.count() == 0:

            raise DatabaseNotReadyError(
                "Vector database is empty. Build it with: python ingestion.py"
            )

    def query(self, **kwargs):
        """
        Query the collection. ingestion.py rebuilds the collection, which
        invalidates the handle a running server holds - reconnect once
        instead of failing every request until a restart.
        """

        try:

            return self.collection.query(**kwargs)

        except Exception as error:

            if "does not exist" not in str(error):

                raise

            self.connect()

            return self.collection.query(**kwargs)

    def embed_question(self, question):

        return self.model.encode(
            config.QUERY_INSTRUCTION + question,
            normalize_embeddings=True,
        ).tolist()

    def semantic_search(self, question, n_results=CANDIDATES):
        """
        Pure vector search, ordered by cosine distance.
        A filename mentioned in the question restricts the search
        to that file (falling back to the whole repo if no match).
        """

        question_words = extract_question_words(question)

        embedding = self.embed_question(question)

        filename = detect_filename(question)

        raw = None

        if filename:

            raw = self.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where={"filename": filename},
            )

            if not raw["documents"][0]:

                raw = None

        if raw is None:

            raw = self.query(
                query_embeddings=[embedding],
                n_results=n_results,
            )

        return [
            build_result(document, metadata, distance, rank, question_words)
            for rank, (document, metadata, distance) in enumerate(
                zip(raw["documents"][0], raw["metadatas"][0], raw["distances"][0], strict=True),
                1,
            )
        ]

    def search(self, question, use_llm=True):
        """
        Full pipeline. Returns all three orderings so the evaluation
        can compare them:
          semantic - vector search only
          hybrid   - vector + lexical/structural scoring
          final    - hybrid top-k reordered by the LLM (if available)
        """

        semantic = self.semantic_search(question)

        hybrid = hybrid_rank(semantic)

        final = hybrid

        llm_used = False

        if use_llm:

            from llm import rerank

            top = hybrid[:RERANK_TOP_K]

            order = rerank(question, top)

            if order is not None:

                final = apply_llm_order(top, order) + hybrid[RERANK_TOP_K:]

                llm_used = True

        return {
            "semantic": semantic,
            "hybrid": hybrid,
            "final": final,
            "llm_used": llm_used,
        }


_retriever = None


def get_retriever():
    """Load the database and model once and reuse them."""

    global _retriever

    if _retriever is None:

        _retriever = Retriever()

    return _retriever
